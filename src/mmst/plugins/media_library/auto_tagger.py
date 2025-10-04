"""Automatic tag generation from folder structure patterns.

This module provides pattern-based metadata extraction from file paths,
allowing users to automatically populate tags like artist, album, title,
track number, etc. from folder structure.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

from .metadata import MediaMetadata


@dataclass
class PatternMatch:
    """Result of pattern matching against a file path."""
    pattern_name: str
    matched: bool
    extracted: Dict[str, str]
    confidence: float  # 0.0-1.0


class PathPattern:
    """A pattern for extracting metadata from file paths.
    
    Patterns use placeholders like {artist}, {album}, {title}, {track}, {year}
    that get compiled into regex patterns for matching.
    
    Example patterns:
    - "{artist}/{album}/{track} - {title}.{ext}"
    - "Music/{artist} - {album}/{track:02d}. {title}.{ext}"
    - "{artist}/{year} - {album}/{title}.{ext}"
    """
    
    PLACEHOLDERS = {
        "artist": r"(?P<artist>[^/\\]+?)",
        "album": r"(?P<album>[^/\\]+?)",
        "title": r"(?P<title>[^/\\]+?)",
        "track": r"(?P<track>\d+)",
        "year": r"(?P<year>\d{4})",
        "genre": r"(?P<genre>[^/\\]+?)",
        "disc": r"(?P<disc>\d+)",
        "ext": r"(?P<ext>\w+)",
    }
    
    def __init__(self, name: str, pattern: str, enabled: bool = True) -> None:
        self.name = name
        self.pattern = pattern
        self.enabled = enabled
        self._regex: Optional[Pattern[str]] = None
        self._placeholders: List[str] = []
        self._compile()
    
    def _compile(self) -> None:
        """Compile pattern into regex, extracting placeholder names."""
        # Find all placeholders
        placeholder_pattern = r'\{(\w+)(?::[^}]+)?\}'
        self._placeholders = re.findall(placeholder_pattern, self.pattern)
        
        # Build regex by replacing placeholders
        regex_pattern = self.pattern
        
        # Escape regex special chars except our placeholders
        for char in r'.^$*+?[]{}()|\\':
            if char not in '{}':
                regex_pattern = regex_pattern.replace(char, '\\' + char)
        
        # Replace placeholders with regex groups using string replacement
        # (avoid re.sub to prevent issues with backslashes in replacement)
        for placeholder in self._placeholders:
            if placeholder in self.PLACEHOLDERS:
                # Handle format specifiers like {track:02d} - replace with just {placeholder}
                # First normalize all variations to {placeholder}
                import re as _re_module
                placeholder_variations = _re_module.compile(r'\{' + placeholder + r'(?::[^}]+)?\}')
                regex_pattern = placeholder_variations.sub('{' + placeholder + '}', regex_pattern)
                
                # Now replace {placeholder} with the regex group
                regex_pattern = regex_pattern.replace(
                    '{' + placeholder + '}',
                    self.PLACEHOLDERS[placeholder]
                )
        
        # Allow flexible path separators
        regex_pattern = regex_pattern.replace(r'\/', r'[\\/]')
        
        try:
            self._regex = re.compile(regex_pattern, re.IGNORECASE)
        except re.error:
            self._regex = None
    
    def match(self, path: Path) -> PatternMatch:
        """Try to match this pattern against a file path."""
        if not self.enabled or self._regex is None:
            return PatternMatch(
                pattern_name=self.name,
                matched=False,
                extracted={},
                confidence=0.0
            )
        
        # Try to match from the end of the path (most specific)
        path_str = str(path)
        match = self._regex.search(path_str)
        
        if not match:
            return PatternMatch(
                pattern_name=self.name,
                matched=False,
                extracted={},
                confidence=0.0
            )
        
        # Extract matched groups
        extracted = {
            key: value.strip()
            for key, value in match.groupdict().items()
            if value is not None
        }
        
        # Calculate confidence based on how many placeholders matched
        confidence = len(extracted) / max(len(self._placeholders), 1)
        
        return PatternMatch(
            pattern_name=self.name,
            matched=True,
            extracted=extracted,
            confidence=confidence
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize pattern to dictionary."""
        return {
            "name": self.name,
            "pattern": self.pattern,
            "enabled": self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PathPattern":
        """Deserialize pattern from dictionary."""
        return cls(
            name=data.get("name", "Unnamed"),
            pattern=data.get("pattern", ""),
            enabled=data.get("enabled", True)
        )


class AutoTagger:
    """Manages automatic tag generation from file paths."""
    
    DEFAULT_PATTERNS = [
        PathPattern(
            "Artist/Album/Track - Title",
            "{artist}/{album}/{track} - {title}.{ext}",
            enabled=True
        ),
        PathPattern(
            "Artist - Album/Track. Title",
            "{artist} - {album}/{track}. {title}.{ext}",
            enabled=True
        ),
        PathPattern(
            "Artist/Year - Album/Title",
            "{artist}/{year} - {album}/{title}.{ext}",
            enabled=True
        ),
        PathPattern(
            "Genre/Artist/Album/Title",
            "{genre}/{artist}/{album}/{title}.{ext}",
            enabled=True
        ),
        PathPattern(
            "Music/Artist/Album/Track - Title",
            "Music/{artist}/{album}/{track} - {title}.{ext}",
            enabled=True
        ),
    ]
    
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("MMST.MediaLibrary.AutoTagger")
        self._patterns: List[PathPattern] = []
        self._load_default_patterns()
    
    def _load_default_patterns(self) -> None:
        """Load default pattern set."""
        self._patterns = [
            PathPattern(p.name, p.pattern, p.enabled)
            for p in self.DEFAULT_PATTERNS
        ]
    
    def add_pattern(self, pattern: PathPattern) -> None:
        """Add a new pattern."""
        self._patterns.append(pattern)
    
    def remove_pattern(self, name: str) -> bool:
        """Remove a pattern by name. Returns True if found and removed."""
        for i, pattern in enumerate(self._patterns):
            if pattern.name == name:
                self._patterns.pop(i)
                return True
        return False
    
    def get_patterns(self) -> List[PathPattern]:
        """Get all configured patterns."""
        return list(self._patterns)
    
    def set_pattern_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a pattern. Returns True if found."""
        for pattern in self._patterns:
            if pattern.name == name:
                pattern.enabled = enabled
                return True
        return False
    
    def analyze_path(self, path: Path, library_root: Optional[Path] = None) -> List[PatternMatch]:
        """Try to match path against all enabled patterns.
        
        Args:
            path: File path to analyze
            library_root: If provided, makes path relative to this root
        
        Returns:
            List of pattern matches, sorted by confidence (best first)
        """
        # Make path relative to library root if provided
        if library_root:
            try:
                path = path.relative_to(library_root)
            except ValueError:
                pass  # Not relative, use full path
        
        matches = []
        for pattern in self._patterns:
            if pattern.enabled:
                match = pattern.match(path)
                if match.matched:
                    matches.append(match)
        
        # Sort by confidence (best first)
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
    
    def extract_metadata(
        self,
        path: Path,
        library_root: Optional[Path] = None,
        existing_metadata: Optional[MediaMetadata] = None
    ) -> Tuple[Dict[str, str], Optional[str]]:
        """Extract metadata from path using best matching pattern.
        
        Args:
            path: File path to analyze
            library_root: If provided, makes path relative to this root
            existing_metadata: Existing metadata to preserve if present
        
        Returns:
            Tuple of (extracted_tags, pattern_name_used)
            Returns empty dict and None if no pattern matched
        """
        matches = self.analyze_path(path, library_root)
        
        if not matches:
            return {}, None
        
        # Use best match
        best_match = matches[0]
        extracted = dict(best_match.extracted)
        
        # Remove 'ext' as it's not a metadata field
        extracted.pop('ext', None)
        
        # Convert track number to integer string
        if 'track' in extracted:
            try:
                extracted['track'] = str(int(extracted['track']))
            except ValueError:
                pass
        
        # Don't override existing metadata unless it's empty
        if existing_metadata:
            result = {}
            for key, value in extracted.items():
                existing_value = getattr(existing_metadata, key, None)
                if not existing_value or existing_value.strip() == "":
                    result[key] = value
            return result, best_match.pattern_name
        
        return extracted, best_match.pattern_name
    
    def batch_extract(
        self,
        paths: List[Path],
        library_root: Optional[Path] = None
    ) -> List[Tuple[Path, Dict[str, str], Optional[str]]]:
        """Extract metadata for multiple files.
        
        Returns:
            List of tuples (path, extracted_tags, pattern_name)
        """
        results = []
        for path in paths:
            tags, pattern = self.extract_metadata(path, library_root)
            results.append((path, tags, pattern))
        return results
    
    def save_patterns(self) -> List[Dict[str, Any]]:
        """Serialize patterns to list of dictionaries."""
        return [p.to_dict() for p in self._patterns]
    
    def load_patterns(self, data: List[Dict[str, Any]]) -> None:
        """Load patterns from list of dictionaries."""
        self._patterns = []
        for item in data:
            try:
                pattern = PathPattern.from_dict(item)
                self._patterns.append(pattern)
            except Exception as e:
                self._logger.warning(f"Failed to load pattern: {e}")
        
        # Ensure at least default patterns exist
        if not self._patterns:
            self._load_default_patterns()
