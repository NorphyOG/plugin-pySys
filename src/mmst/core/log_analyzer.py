from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from collections import Counter
import time
from datetime import datetime, timedelta


class LogEntry:
    """Represents a parsed log entry with its components."""
    
    def __init__(
        self, 
        timestamp: datetime,
        level: str,
        component: str,
        message: str,
        original_text: str
    ):
        """Initialize a log entry.
        
        Args:
            timestamp: The log entry timestamp
            level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: The component or logger name
            message: The log message
            original_text: The original log text
        """
        self.timestamp = timestamp
        self.level = level
        self.component = component
        self.message = message
        self.original_text = original_text


class LogAnalyzer:
    """Analyzes log entries for patterns, errors, and statistics."""
    
    # Regular expression to parse log entries with the format:
    # 2023-04-05 12:34:56 [LEVEL] component: message
    LOG_PATTERN = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]\s+([^:]+):\s*(.*)'
    )
    
    def __init__(self):
        """Initialize the log analyzer."""
        self._entries: List[LogEntry] = []
    
    def parse_logs(self, log_text: str) -> List[LogEntry]:
        """Parse log text into structured log entries.
        
        Args:
            log_text: The log text to parse
            
        Returns:
            List of parsed LogEntry objects
        """
        self._entries = []
        
        for line in log_text.splitlines():
            line = line.strip()
            if not line:
                continue
                
            match = self.LOG_PATTERN.match(line)
            if match:
                try:
                    timestamp_str, level, component, message = match.groups()
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    
                    entry = LogEntry(
                        timestamp=timestamp,
                        level=level,
                        component=component,
                        message=message,
                        original_text=line
                    )
                    self._entries.append(entry)
                except Exception:
                    # If we can't parse the timestamp, skip this entry
                    pass
        
        return self._entries
    
    def count_by_level(self) -> Dict[str, int]:
        """Count log entries by level.
        
        Returns:
            Dictionary of log levels and their counts
        """
        return Counter(entry.level for entry in self._entries)
    
    def count_by_component(self) -> Dict[str, int]:
        """Count log entries by component.
        
        Returns:
            Dictionary of components and their counts
        """
        return Counter(entry.component for entry in self._entries)
    
    def get_error_entries(self) -> List[LogEntry]:
        """Get all error and critical entries.
        
        Returns:
            List of error and critical log entries
        """
        return [entry for entry in self._entries 
                if entry.level in ('ERROR', 'CRITICAL')]
    
    def get_top_error_components(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Get components with the most errors.
        
        Args:
            limit: Maximum number of components to return
            
        Returns:
            List of (component, error_count) tuples
        """
        error_components = Counter()
        for entry in self._entries:
            if entry.level in ('ERROR', 'CRITICAL'):
                error_components[entry.component] += 1
        
        return error_components.most_common(limit)
    
    def get_time_distribution(self, interval_minutes: int = 5) -> Dict[datetime, int]:
        """Get distribution of log entries over time.
        
        Args:
            interval_minutes: Size of time intervals in minutes
            
        Returns:
            Dictionary mapping interval start times to entry counts
        """
        if not self._entries:
            return {}
            
        # Find min and max timestamps
        min_time = min(entry.timestamp for entry in self._entries)
        max_time = max(entry.timestamp for entry in self._entries)
        
        # Round down to nearest interval
        interval = timedelta(minutes=interval_minutes)
        min_time = min_time.replace(
            minute=(min_time.minute // interval_minutes) * interval_minutes,
            second=0,
            microsecond=0
        )
        
        # Create intervals
        intervals = {}
        current = min_time
        while current <= max_time:
            intervals[current] = 0
            current += interval
        
        # Count entries in each interval
        for entry in self._entries:
            interval_start = entry.timestamp.replace(
                minute=(entry.timestamp.minute // interval_minutes) * interval_minutes,
                second=0,
                microsecond=0
            )
            intervals[interval_start] += 1
        
        return intervals
    
    def get_common_patterns(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Find common message patterns.
        
        Args:
            limit: Maximum number of patterns to return
            
        Returns:
            List of (pattern, count) tuples
        """
        # Simplify messages by removing specific values like timestamps, IDs, paths
        patterns = []
        for entry in self._entries:
            # Replace numbers, UUIDs, paths, etc. with placeholders
            simplified = re.sub(r'\d+', 'N', entry.message)
            simplified = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', simplified)
            simplified = re.sub(r'[/\\][^\s/\\]+', '/PATH', simplified)
            patterns.append(simplified)
        
        return Counter(patterns).most_common(limit)
    
    def get_error_rate(self, interval_minutes: int = 5) -> Dict[datetime, float]:
        """Calculate error rate over time.
        
        Args:
            interval_minutes: Size of time intervals in minutes
            
        Returns:
            Dictionary mapping interval start times to error rates
        """
        if not self._entries:
            return {}
            
        # Get time distribution for all entries
        all_entries = self.get_time_distribution(interval_minutes)
        
        # Get time distribution for error entries
        error_entries = {}
        for entry in self._entries:
            if entry.level in ('ERROR', 'CRITICAL'):
                interval_start = entry.timestamp.replace(
                    minute=(entry.timestamp.minute // interval_minutes) * interval_minutes,
                    second=0,
                    microsecond=0
                )
                error_entries[interval_start] = error_entries.get(interval_start, 0) + 1
        
        # Calculate error rates
        error_rates = {}
        for interval, count in all_entries.items():
            if count > 0:
                error_count = error_entries.get(interval, 0)
                error_rates[interval] = error_count / count
            else:
                error_rates[interval] = 0.0
        
        return error_rates