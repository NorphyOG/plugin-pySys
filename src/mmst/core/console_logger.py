from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Dict, List, Optional, TextIO, Callable, Any
from pathlib import Path
import os
import re

# Constants for formatting
LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",  # Cyan
    logging.INFO: "\033[32m",   # Green
    logging.WARNING: "\033[33m", # Yellow
    logging.ERROR: "\033[31m",  # Red
    logging.CRITICAL: "\033[35m" # Magenta
}
RESET_COLOR = "\033[0m"

# Named log levels for configuration
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL
}

class ConsoleLogHandler(logging.Handler):
    """Enhanced console log handler with colored output and message buffering."""
    
    def __init__(
        self,
        stream: TextIO = sys.stdout,
        use_colors: bool = True,
        buffer_size: int = 1000,
        formatter: Optional[logging.Formatter] = None
    ):
        """Initialize the console log handler.
        
        Args:
            stream: The stream to write logs to
            use_colors: Whether to use colored output
            buffer_size: Maximum number of log messages to buffer
            formatter: Log formatter to use
        """
        super().__init__()
        self.stream = stream
        self.use_colors = use_colors
        self.buffer_size = buffer_size
        
        if formatter:
            self.setFormatter(formatter)
        else:
            default_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            self.setFormatter(default_formatter)
        
        self._buffer: List[str] = []
        self._buffer_lock = threading.RLock()
        
        # Initialize debug file for persistent logging
        self._debug_file: Optional[TextIO] = None
        try:
            log_dir = Path.home() / ".mmst" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            current_date = datetime.now().strftime("%Y-%m-%d")
            log_path = log_dir / f"mmst-{current_date}.log"
            self._debug_file = open(log_path, "a", encoding="utf-8")
            
            # Write startup separator
            startup_message = f"\n{'-'*80}\nApplication started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'-'*80}\n"
            self._debug_file.write(startup_message)
            self._debug_file.flush()
        except Exception:
            pass  # Silently continue if we can't create the debug file

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        try:
            # Format the message
            msg = self.format(record)
            
            # Write to console with colors if enabled
            if self.use_colors and record.levelno in LEVEL_COLORS:
                color = LEVEL_COLORS[record.levelno]
                console_msg = f"{color}{msg}{RESET_COLOR}"
            else:
                console_msg = msg
                
            # Output to console
            self.stream.write(console_msg + "\n")
            self.stream.flush()
            
            # Store in buffer with lock
            with self._buffer_lock:
                self._buffer.append(msg)
                if len(self._buffer) > self.buffer_size:
                    self._buffer = self._buffer[-self.buffer_size:]
            
            # Also write to debug file if available
            if self._debug_file:
                try:
                    self._debug_file.write(msg + "\n")
                    self._debug_file.flush()
                except Exception:
                    pass  # Don't fail if debug file becomes unavailable
                
        except Exception:
            self.handleError(record)
    
    def get_buffer(self) -> List[str]:
        """Get a copy of the current log buffer."""
        with self._buffer_lock:
            return list(self._buffer)
    
    def close(self) -> None:
        """Close the handler and release resources."""
        if self._debug_file:
            try:
                shutdown_message = f"\n{'-'*80}\nApplication shutdown at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'-'*80}\n"
                self._debug_file.write(shutdown_message)
                self._debug_file.close()
            except Exception:
                pass
        super().close()


class ConsoleLogger:
    """Main console logger manager for MMST."""
    
    _instance: Optional[ConsoleLogger] = None
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls) -> ConsoleLogger:
        """Get singleton instance of the console logger."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = ConsoleLogger()
            return cls._instance
    
    def __init__(self):
        """Initialize the console logger.
        
        Note: This should generally not be called directly. Use get_instance() instead.
        """
        self.handler = ConsoleLogHandler()
        self.root_logger = logging.getLogger()
        
        # Remove any existing handlers to prevent duplicate logs
        for handler in list(self.root_logger.handlers):
            self.root_logger.removeHandler(handler)
        
        # Add our handler
        self.root_logger.addHandler(self.handler)
        
        # Create file handler for all logs
        try:
            log_dir = Path.home() / ".mmst" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Rotate old logs if needed
            self._rotate_logs(log_dir)
            
            # Create new file handler
            current_date = datetime.now().strftime("%Y-%m-%d")
            log_path = log_dir / f"mmst-{current_date}.log"
            
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file
            self.root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to set up file logging: {e}")
        
        # Set default level
        self.set_level(logging.INFO)
        
        # Track registered loggers
        self._registered_loggers: Dict[str, logging.Logger] = {}
    
    def _rotate_logs(self, log_dir: Path, max_logs: int = 30) -> None:
        """Rotate logs to prevent excessive disk usage.
        
        Args:
            log_dir: Directory containing logs
            max_logs: Maximum number of logs to keep
        """
        try:
            # Get list of log files
            pattern = re.compile(r"mmst-\d{4}-\d{2}-\d{2}\.log")
            log_files = [f for f in log_dir.glob("*.log") if pattern.match(f.name)]
            
            # Sort by modification time (oldest first)
            log_files.sort(key=lambda f: f.stat().st_mtime)
            
            # Delete oldest files if we have more than the maximum
            if len(log_files) > max_logs:
                for old_file in log_files[:-max_logs]:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass  # Ignore errors deleting old logs
        except Exception:
            pass  # Don't let log rotation failures affect application
    
    def set_level(self, level: int) -> None:
        """Set the root logger level.
        
        Args:
            level: The logging level to set
        """
        self.root_logger.setLevel(level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the given name.
        
        Args:
            name: The logger name
            
        Returns:
            A Logger instance with the given name
        """
        if name in self._registered_loggers:
            return self._registered_loggers[name]
        
        logger = logging.getLogger(name)
        self._registered_loggers[name] = logger
        return logger
    
    def get_buffer(self) -> List[str]:
        """Get the current log buffer."""
        return self.handler.get_buffer()
    
    def register_excepthook(self) -> None:
        """Register a global exception handler to log unhandled exceptions."""
        original_excepthook = sys.excepthook
        
        def excepthook(exctype, value, tb):
            # First call the original excepthook
            original_excepthook(exctype, value, tb)
            
            # Format the exception details with improved diagnostics
            exception_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_header = f"UNHANDLED EXCEPTION AT {exception_time}"
            error_separator = "=" * 80
            
            # Get the traceback
            traceback_details = ''.join(traceback.format_exception(exctype, value, tb))
            
            # Include extra diagnostics
            import platform
            diagnostic_info = (
                f"Python Version: {platform.python_version()}\n"
                f"Platform: {platform.system()} {platform.release()} ({platform.version()})\n"
                f"Exception Type: {exctype.__name__}\n"
                f"Exception Message: {value}\n"
            )
            
            # Format the complete error message
            error_message = f"\n{error_separator}\n{error_header}\n{error_separator}\n{diagnostic_info}\n{traceback_details}\n{error_separator}\n"
            
            # Log the exception
            self.root_logger.critical(
                "Unhandled exception: %s", 
                value
            )
            
            # Also log the full details at debug level
            self.root_logger.debug(error_message)
            
        # Register our custom excepthook
        sys.excepthook = excepthook
    
    def get_log_file_path(self) -> Optional[str]:
        """Get the path to the current log file.
        
        Returns:
            Path to the current log file or None if not available
        """
        try:
            log_dir = Path.home() / ".mmst" / "logs"
            current_date = datetime.now().strftime("%Y-%m-%d")
            log_path = log_dir / f"mmst-{current_date}.log"
            if log_path.exists():
                return str(log_path)
        except Exception:
            pass
        return None
    
    def get_all_log_files(self) -> List[str]:
        """Get a list of all available log files.
        
        Returns:
            List of paths to log files
        """
        try:
            log_dir = Path.home() / ".mmst" / "logs"
            if log_dir.exists():
                return [str(f) for f in log_dir.glob("mmst-*.log") if f.is_file()]
        except Exception:
            pass
        return []


def setup_logging(app_name: str = "MMST", level: str = "info") -> ConsoleLogger:
    """Set up logging for the application.
    
    Args:
        app_name: Name of the application for logging
        level: Logging level to use ("debug", "info", "warning", "error", or "critical")
        
    Returns:
        Configured ConsoleLogger instance
    """
    console_logger = ConsoleLogger.get_instance()
    
    # Set level based on string value
    log_level = LOG_LEVELS.get(level.lower(), logging.INFO)
    console_logger.set_level(log_level)
    
    # Register exception handler
    console_logger.register_excepthook()
    
    return console_logger