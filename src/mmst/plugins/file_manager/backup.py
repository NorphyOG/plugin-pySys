from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import send2trash


@dataclass
class BackupResult:
    copied_files: int
    skipped_files: int
    removed_files: int
    total_bytes_copied: int
    duration_seconds: float


ProgressCallback = Callable[[str], None]


def perform_backup(source: Path, target: Path, mirror: bool, progress: ProgressCallback, dry_run: bool = False) -> BackupResult:
    """Copy ``source`` into ``target`` while preserving directory structure.

    The implementation performs an incremental copy and optionally mirrors the target by
    deleting files or directories that no longer exist in the source tree.
    
    If dry_run is True, simulates the backup without actually copying or deleting files.
    """

    if not source.exists() or not source.is_dir():
        raise ValueError("Das Quellverzeichnis ist ungültig.")
    if source == target:
        raise ValueError("Quelle und Ziel dürfen nicht identisch sein.")
    try:
        target.relative_to(source)
        raise ValueError("Das Ziel darf nicht innerhalb der Quelle liegen.")
    except ValueError:
        pass

    start_time = time.time()
    copied = skipped = removed = 0
    total_bytes = 0

    target.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(source):
        root_path = Path(root)
        rel_path = root_path.relative_to(source)
        target_root = target / rel_path
        target_root.mkdir(parents=True, exist_ok=True)

        for directory in dirs:
            (target_root / directory).mkdir(exist_ok=True)

        for filename in files:
            src_file = root_path / filename
            dst_file = target_root / filename
            try:
                if dst_file.exists():
                    src_stat = src_file.stat()
                    dst_stat = dst_file.stat()
                    if dst_stat.st_mtime >= src_stat.st_mtime and dst_stat.st_size == src_stat.st_size:
                        skipped += 1
                        progress(f"Übersprungen: {dst_file} (unverändert)")
                        continue
                
                if dry_run:
                    # Simulation: count as copied but don't actually copy
                    copied += 1
                    total_bytes += src_file.stat().st_size
                    progress(f"[DRY RUN] Würde kopieren: {dst_file}")
                else:
                    shutil.copy2(src_file, dst_file)
                    copied += 1
                    total_bytes += dst_file.stat().st_size
                    progress(f"Kopiert: {dst_file}")
            except Exception as exc:  # pragma: no cover - runtime failure surface
                progress(f"Fehler beim Kopieren von {src_file}: {exc}")

    if mirror:
        removed += _mirror_cleanup(source, target, progress, dry_run)

    duration = time.time() - start_time
    return BackupResult(
        copied_files=copied,
        skipped_files=skipped,
        removed_files=removed,
        total_bytes_copied=total_bytes,
        duration_seconds=duration,
    )


def _mirror_cleanup(source: Path, target: Path, progress: ProgressCallback, dry_run: bool = False) -> int:
    removed = 0
    for root, dirs, files in os.walk(target, topdown=False):
        root_path = Path(root)
        rel_path = root_path.relative_to(target)
        source_root = source / rel_path

        for filename in files:
            target_file = root_path / filename
            if not (source_root / filename).exists():
                try:
                    if dry_run:
                        removed += 1
                        progress(f"[DRY RUN] Würde löschen: {target_file}")
                    else:
                        send2trash.send2trash(target_file)
                        removed += 1
                        progress(f"Gelöscht: {target_file}")
                except Exception as exc:  # pragma: no cover - runtime failure surface
                    progress(f"Fehler beim Löschen von {target_file}: {exc}")

        for directory in dirs:
            target_dir = root_path / directory
            if not (source_root / directory).exists():
                try:
                    if dry_run:
                        removed += 1
                        progress(f"[DRY RUN] Würde entfernen: {target_dir}")
                    else:
                        send2trash.send2trash(target_dir)
                        removed += 1
                        progress(f"Verzeichnis entfernt: {target_dir}")
                except Exception as exc:  # pragma: no cover - runtime failure surface
                    progress(f"Fehler beim Entfernen von {target_dir}: {exc}")

    return removed
