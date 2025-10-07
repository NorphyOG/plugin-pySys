from __future__ import annotations

"""Temporary Files Cleaner backend logic.

Provides scanning & deletion helpers for grouped categories of temporary
files. The design mirrors other SystemTools backends: a thin, testable
pure-Python core (no Qt) that returns structured dataclasses which the
UI layer renders and manipulates.

Key goals:
 - Cross-platform (Windows & Linux)
 - Non-destructive dry-run support
 - Configurable categories with pluggable resolvers
 - Size aggregation & per-file metadata
 - Safe deletion (skip symlinks outside temp roots, ignore permission errors)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
import os
import stat
import time
import shutil

__all__ = [
    "TempFileEntry",
    "TempCategoryResult",
    "ScanResult",
    "TempCleaner",
]


@dataclass
class TempFileEntry:
    path: Path
    size: int
    mtime: float
    category: str
    removable: bool = True
    is_directory: bool = False

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.mtime)


@dataclass
class TempCategoryResult:
    name: str
    display: str
    total_size: int = 0
    files: List[TempFileEntry] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add(self, entry: TempFileEntry) -> None:
        self.files.append(entry)
        self.total_size += entry.size


@dataclass
class ScanResult:
    categories: Dict[str, TempCategoryResult]
    duration_seconds: float
    total_size: int
    total_files: int

    def summary(self) -> Dict[str, int]:
        return {
            "total_files": self.total_files,
            "total_size": self.total_size,
            "categories": len(self.categories),
        }


class TempCleaner:
    """Core scanner & deletion helper for temporary files.

    Usage pattern:
        cleaner = TempCleaner()
        result = cleaner.scan(selected_categories=[...])
        deletion_report = cleaner.delete(result, dry_run=True, min_age_seconds=3600)
    """

    # Default category resolvers: mapping id -> (display name, call -> iterable[Path])
    def __init__(self, extra_categories: Optional[Dict[str, Tuple[str, Iterable[Path]]]] = None) -> None:
        self._categories: Dict[str, Tuple[str, Iterable[Path]]] = {}
        for key, value in self._default_categories().items():
            self._categories[key] = value
        if extra_categories:
            self._categories.update(extra_categories)

    # Platform specific default category roots
    def _default_categories(self) -> Dict[str, Tuple[str, Iterable[Path]]]:
        import sys
        tmp = Path(os.environ.get("TMP") or os.environ.get("TEMP") or "/tmp").expanduser()
        cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        categories: Dict[str, Tuple[str, Iterable[Path]]] = {
            "system_tmp": ("System Temp", [tmp]),
        }
        if sys.platform.startswith("win"):
            # Browser caches simplified (user can extend later)
            appdata = Path(os.environ.get("LOCALAPPDATA", tmp))
            edge_cache = appdata / "Microsoft/Edge/User Data/Default/Cache"
            chrome_cache = appdata / "Google/Chrome/User Data/Default/Cache"
            categories.update({
                "browser_edge": ("Edge Cache", [edge_cache]),
                "browser_chrome": ("Chrome Cache", [chrome_cache]),
            })
        else:
            # Linux: user cache directory
            categories["user_cache"] = ("User Cache (~/.cache)", [cache_home])
        return categories

    # Public API ---------------------------------------------------------
    def list_categories(self) -> List[Tuple[str, str]]:
        return [(key, meta[0]) for key, meta in self._categories.items()]

    def scan(
        self,
        selected_categories: Optional[Iterable[str]] = None,
        max_files_per_category: int = 25_000,
        follow_symlinks: bool = False,
    ) -> ScanResult:
        start = time.time()
        cats: Dict[str, TempCategoryResult] = {}
        selected = set(selected_categories) if selected_categories else set(self._categories.keys())

        for key in selected:
            meta = self._categories.get(key)
            if not meta:
                continue
            display, roots = meta
            cat_res = TempCategoryResult(name=key, display=display)
            seen = 0
            for root in roots:
                if not root.exists():
                    continue
                try:
                    # First add files
                    for path in self._iter_files(root, follow_symlinks=follow_symlinks):
                        try:
                            st = path.stat()
                        except (FileNotFoundError, PermissionError, OSError) as exc:
                            cat_res.errors.append(f"{path}: {exc}")
                            continue
                        # Basic filters: skip dirs (iter_files yields only files), sockets, etc.
                        size = st.st_size
                        entry = TempFileEntry(path=path, size=size, mtime=st.st_mtime, category=key)
                        cat_res.add(entry)
                        seen += 1
                        if seen >= max_files_per_category:
                            break
                    
                    # Then add directories (if we haven't hit the limit)
                    if seen < max_files_per_category:
                        for path in self._iter_dirs(root, follow_symlinks=follow_symlinks):
                            try:
                                st = path.stat()
                                # Directories typically report their own size, not contents
                                # We'll use 0 to avoid double-counting space
                                size = 0
                                entry = TempFileEntry(path=path, size=size, mtime=st.st_mtime, 
                                                   category=key, is_directory=True)
                                cat_res.add(entry)
                                seen += 1
                                if seen >= max_files_per_category:
                                    break
                            except (FileNotFoundError, PermissionError, OSError) as exc:
                                cat_res.errors.append(f"{path}: {exc}")
                                continue
                except Exception as exc:  # broad: protect scanning loop
                    cat_res.errors.append(f"Root {root} scan error: {exc}")
            cats[key] = cat_res

        total_size = sum(c.total_size for c in cats.values())
        total_files = sum(len(c.files) for c in cats.values())
        duration = time.time() - start
        return ScanResult(categories=cats, duration_seconds=duration, total_size=total_size, total_files=total_files)

    def delete(
        self,
        scan: ScanResult,
        *,
        dry_run: bool = True,
        min_age_seconds: int = 0,
        categories: Optional[Iterable[str]] = None,
    ) -> Dict[str, Dict]:
        """Delete files matching criteria.

        Returns per-category dict with counts, size removed, and lists of deleted files and directories.
        """
        selected = set(categories) if categories else set(scan.categories.keys())
        report: Dict[str, Dict] = {}
        now = time.time()
        for key in selected:
            cat = scan.categories.get(key)
            if not cat:
                continue
            removed_files = 0
            removed_dirs = 0
            removed_size = 0
            deleted_files = []  # Track which files were deleted
            deleted_dirs = []   # Track which directories were deleted
            
            # First process all entries - we need to track both files and directories
            for entry in cat.files:
                if not entry.removable:
                    continue
                if min_age_seconds and (now - entry.mtime) < min_age_seconds:
                    continue
                    
                try:
                    if not dry_run:
                        if entry.is_directory:
                            # For directories, we'll just track them for now
                            # Since directories are sorted in reverse depth order
                            # we can safely remove them after processing all files
                            if entry.path.is_dir() and not entry.path.is_symlink():
                                removed_dirs += 1
                                deleted_dirs.append(str(entry.path))
                        else:
                            # For files, remove immediately
                            if entry.path.is_file():
                                entry.path.unlink(missing_ok=True)  # type: ignore[arg-type]
                                removed_files += 1
                                removed_size += entry.size
                                deleted_files.append(str(entry.path))
                    else:
                        # In dry run, just track everything
                        if entry.is_directory:
                            removed_dirs += 1
                            deleted_dirs.append(str(entry.path))
                        else:
                            removed_files += 1
                            removed_size += entry.size
                            deleted_files.append(str(entry.path))
                except Exception:
                    # best-effort; ignore individual delete failures
                    pass
            
            # Now remove the directories if not in dry run mode
            # We do this after processing all files to ensure directories are empty
            if not dry_run:
                for dir_path in deleted_dirs:
                    try:
                        Path(dir_path).rmdir()
                    except (OSError, PermissionError):
                        # Directory might not be empty or might be locked
                        # We'll keep it in the list anyway to show the attempt
                        pass
                        
            report[key] = {
                "files": removed_files,
                "dirs": removed_dirs,
                "size": removed_size,
                "dry_run": 1 if dry_run else 0,
                "deleted_files": deleted_files,  # Files
                "deleted_dirs": deleted_dirs     # Directories
            }
        return report

    # Internal helpers ---------------------------------------------------
    def _iter_files(self, root: Path, follow_symlinks: bool = False) -> Iterator[Path]:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Prune extremely deep trees defensively
                if dirpath.count(os.sep) - str(root).count(os.sep) > 12:
                    del dirnames[:]
                    continue
                for name in filenames:
                    p = Path(dirpath) / name
                    try:
                        if not follow_symlinks and p.is_symlink():
                            continue
                    except OSError:
                        continue
                    yield p
        except Exception:
            return
            
    def _iter_dirs(self, root: Path, follow_symlinks: bool = False) -> Iterator[Path]:
        """Similar to _iter_files but yields directories in reverse depth order (deepest first).
        This ensures proper directory deletion (must delete contents before parent).
        """
        try:
            # First collect all directories
            all_dirs = []
            for dirpath, dirnames, _ in os.walk(root):
                # Prune extremely deep trees defensively
                if dirpath.count(os.sep) - str(root).count(os.sep) > 12:
                    del dirnames[:]
                    continue
                for name in dirnames:
                    p = Path(dirpath) / name
                    try:
                        if not follow_symlinks and p.is_symlink():
                            continue
                        all_dirs.append(p)
                    except OSError:
                        continue
            
            # Sort by depth (deepest first) for proper deletion order
            all_dirs.sort(key=lambda p: -str(p).count(os.sep))
            yield from all_dirs
        except Exception:
            return
