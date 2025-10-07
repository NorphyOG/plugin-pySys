from __future__ import annotations

"""Explorer plugin search engine.

This module implements the full-text search functionality for the Explorer plugin,
allowing users to search for text within files in the current directory.
"""

import concurrent.futures
import logging
import mimetypes
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Callable

# Define binary file detection
BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.pyc', '.obj', '.bin', '.dat', '.db', '.sqlite',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.tiff', '.webp',
    '.mp3', '.wav', '.mp4', '.avi', '.mov', '.mkv', '.flac', '.ogg',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}

# Maximum file size for full content search (in bytes)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Default supported text file extensions (can be customized)
DEFAULT_TEXT_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
    '.yml', '.yaml', '.ini', '.cfg', '.conf', '.log',
    '.c', '.cpp', '.h', '.hpp', '.java', '.ts', '.cs', '.go',
    '.php', '.rb', '.pl', '.sh', '.bat', '.ps1', '.sql'
}


class SearchMode(Enum):
    """Search mode options."""
    PLAIN_TEXT = "plain"
    REGEX = "regex"
    CASE_SENSITIVE = "case_sensitive"


@dataclass
class SearchMatch:
    """Represents a single search match in a file."""
    file_path: Path
    line_number: int
    line_text: str
    start_pos: int
    end_pos: int


@dataclass
class SearchResult:
    """Represents the search results for a single file."""
    file_path: Path
    matches: List[SearchMatch]
    
    @property
    def match_count(self) -> int:
        """Get the number of matches in this file."""
        return len(self.matches)


class SearchEngine:
    """Engine for searching text within files.
    
    This class implements the core search functionality for the Explorer plugin,
    allowing users to search for text within files in the current directory.
    """
    
    def __init__(self, plugin_services=None):
        """Initialize the search engine.
        
        Args:
            plugin_services: Optional services from the plugin for notifications and logging
        """
        self._services = plugin_services
        self._logger = logging.getLogger("mmst.explorer.search")
        self._text_extensions = DEFAULT_TEXT_EXTENSIONS
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._current_search = None
        
    def set_text_extensions(self, extensions: Set[str]) -> None:
        """Set custom text file extensions.
        
        Args:
            extensions: Set of file extensions (with dot, e.g. '.txt')
        """
        self._text_extensions = extensions
    
    def is_text_file(self, path: Path) -> bool:
        """Check if a file is likely to be a text file.
        
        Args:
            path: Path to the file
            
        Returns:
            True if the file is likely to be a text file
        """
        # Check extension first (fastest)
        suffix = path.suffix.lower()
        if suffix in BINARY_EXTENSIONS:
            return False
        if suffix in self._text_extensions:
            return True
            
        # Try to detect using mimetypes
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type and mime_type.startswith('text/'):
            return True
            
        # As a last resort, check the first few bytes
        try:
            with open(path, 'rb') as f:
                content = f.read(1024)
                # Check for common binary file markers
                if b'\x00' in content:
                    return False
                # Try to decode as text
                try:
                    content.decode('utf-8')
                    return True
                except UnicodeDecodeError:
                    try:
                        content.decode('latin-1')
                        return True
                    except UnicodeDecodeError:
                        return False
        except (IOError, PermissionError):
            return False
        
        # Default to assuming text
        return True
    
    def cancel_search(self) -> None:
        """Cancel any ongoing search operation."""
        if self._current_search:
            self._current_search.cancel()
            self._current_search = None
            self._logger.debug("Search operation canceled")
    
    def search_directory(self, 
                         directory: Path, 
                         search_term: str,
                         mode: SearchMode = SearchMode.PLAIN_TEXT,
                         max_results: int = 1000,
                         file_filter: Optional[Callable[[Path], bool]] = None,
                         progress_callback: Optional[Callable[[int, int], None]] = None
                         ) -> List[SearchResult]:
        """Search for text within files in a directory.
        
        Args:
            directory: Directory to search
            search_term: Text to search for
            mode: Search mode (plain text, regex, case sensitive)
            max_results: Maximum number of results to return
            file_filter: Optional function to filter files
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of search results
        """
        if not directory.is_dir():
            self._logger.error(f"Cannot search in non-directory path: {directory}")
            return []
            
        self._logger.info(f"Searching for '{search_term}' in {directory}")
        
        # Compile regex if needed
        pattern = None
        if mode == SearchMode.REGEX or mode == SearchMode.CASE_SENSITIVE:
            try:
                flags = 0 if mode == SearchMode.CASE_SENSITIVE else re.IGNORECASE
                pattern = re.compile(search_term, flags)
            except re.error as e:
                self._logger.error(f"Invalid regex pattern: {e}")
                return []
        
        # Get all files recursively
        all_files = list(self._get_all_files(directory, file_filter))
        total_files = len(all_files)
        
        if progress_callback:
            progress_callback(0, total_files)
            
        # Start the search operation
        results = []
        files_processed = 0
        
        try:
            # Submit search tasks to the executor
            futures = []
            for file_path in all_files:
                if not self.is_text_file(file_path):
                    files_processed += 1
                    if progress_callback and files_processed % 10 == 0:
                        progress_callback(files_processed, total_files)
                    continue
                    
                future = self._executor.submit(
                    self._search_file, 
                    file_path, 
                    search_term, 
                    mode, 
                    pattern
                )
                futures.append(future)
                
            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    files_processed += 1
                    
                    if progress_callback and files_processed % 10 == 0:
                        progress_callback(files_processed, total_files)
                        
                    if result and result.matches:
                        results.append(result)
                        if len(results) >= max_results:
                            break
                except Exception as e:
                    self._logger.error(f"Error during search: {e}")
                
        except Exception as e:
            self._logger.error(f"Search operation failed: {e}")
            
        # Final progress update
        if progress_callback:
            progress_callback(total_files, total_files)
            
        return results
    
    def _get_all_files(self, directory: Path, file_filter: Optional[Callable[[Path], bool]] = None) -> List[Path]:
        """Get all files in a directory recursively.
        
        Args:
            directory: Directory to scan
            file_filter: Optional function to filter files
            
        Returns:
            List of file paths
        """
        files = []
        try:
            for path in directory.rglob('*'):
                if path.is_file():
                    if file_filter and not file_filter(path):
                        continue
                    files.append(path)
        except (PermissionError, OSError) as e:
            self._logger.warning(f"Error accessing path: {e}")
            
        return files
    
    def _search_file(self, file_path: Path, search_term: str, mode: SearchMode, pattern=None) -> Optional[SearchResult]:
        """Search for text within a single file.
        
        Args:
            file_path: Path to the file
            search_term: Text to search for
            mode: Search mode
            pattern: Compiled regex pattern (if applicable)
            
        Returns:
            SearchResult with matches or None if error/no matches
        """
        if file_path.stat().st_size > MAX_FILE_SIZE:
            self._logger.debug(f"Skipping large file: {file_path} ({file_path.stat().st_size} bytes)")
            return None
            
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                for i, line in enumerate(file, 1):
                    if mode == SearchMode.PLAIN_TEXT:
                        # Simple case-insensitive substring search
                        line_lower = line.lower()
                        search_lower = search_term.lower()
                        start_idx = line_lower.find(search_lower)
                        while start_idx != -1:
                            end_idx = start_idx + len(search_term)
                            matches.append(SearchMatch(
                                file_path=file_path,
                                line_number=i,
                                line_text=line.rstrip('\n'),
                                start_pos=start_idx,
                                end_pos=end_idx
                            ))
                            # Look for next occurrence in the same line
                            start_idx = line_lower.find(search_lower, end_idx)
                    else:
                        # Regex search
                        for match in pattern.finditer(line):
                            matches.append(SearchMatch(
                                file_path=file_path,
                                line_number=i,
                                line_text=line.rstrip('\n'),
                                start_pos=match.start(),
                                end_pos=match.end()
                            ))
                            
            if matches:
                return SearchResult(file_path=file_path, matches=matches)
                
        except (UnicodeDecodeError, PermissionError, OSError) as e:
            self._logger.debug(f"Error searching file {file_path}: {e}")
            
        return None
    
    def get_context_lines(self, file_path: Path, line_number: int, context_lines: int = 2) -> List[Tuple[int, str]]:
        """Get lines before and after a match for context.
        
        Args:
            file_path: Path to the file
            line_number: Line number of the match
            context_lines: Number of lines before and after to include
            
        Returns:
            List of (line_number, line_text) tuples
        """
        if not file_path.exists() or not file_path.is_file():
            return []
            
        try:
            # Calculate line range
            start_line = max(1, line_number - context_lines)
            end_line = line_number + context_lines
            
            result = []
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                for i, line in enumerate(file, 1):
                    if start_line <= i <= end_line:
                        result.append((i, line.rstrip('\n')))
                    if i > end_line:
                        break
                        
            return result
            
        except (UnicodeDecodeError, PermissionError, OSError) as e:
            self._logger.debug(f"Error getting context lines from {file_path}: {e}")
            return []