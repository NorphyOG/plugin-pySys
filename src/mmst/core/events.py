"""Plugin event system for inter-plugin communication.

This module provides a simple pub/sub event system that allows plugins to communicate
with each other without tight coupling. Plugins can emit events and subscribe to events
from other plugins.

Example usage:
    # In FileManager plugin after deleting files
    services.event_bus.emit('files.deleted', {'paths': deleted_paths})
    
    # In MediaLibrary plugin to listen for file deletions
    services.event_bus.subscribe('files.deleted', self._handle_deleted_files)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List
import threading


EventCallback = Callable[[str, Dict[str, Any]], None]


class EventBus:
    """Central event bus for plugin communication."""
    
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventCallback]] = {}
        self._lock = threading.RLock()
    
    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """Subscribe to an event.
        
        Args:
            event_name: Name of the event to listen for (e.g., 'files.deleted')
            callback: Function to call when event is emitted. 
                     Receives (event_name, data) as arguments.
        """
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
    
    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        """Unsubscribe from an event.
        
        Args:
            event_name: Name of the event
            callback: Previously registered callback to remove
        """
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(callback)
                except ValueError:
                    pass
    
    def unsubscribe_all(self, callback: EventCallback) -> None:
        """Unsubscribe a callback from all events.
        
        Args:
            callback: Previously registered callback to remove from all events
        """
        with self._lock:
            for subscribers in self._subscribers.values():
                try:
                    subscribers.remove(callback)
                except ValueError:
                    pass
    
    def emit(self, event_name: str, data: Dict[str, Any] = None) -> None:
        """Emit an event to all subscribers.
        
        Args:
            event_name: Name of the event to emit
            data: Optional dictionary of event data
        """
        if data is None:
            data = {}
        
        with self._lock:
            callbacks = self._subscribers.get(event_name, []).copy()
        
        # Call callbacks outside the lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(event_name, data)
            except Exception:
                # Silently ignore callback errors to prevent one bad subscriber
                # from affecting others
                pass
    
    def clear(self) -> None:
        """Clear all event subscriptions. Useful for testing."""
        with self._lock:
            self._subscribers.clear()
    
    def get_event_names(self) -> List[str]:
        """Get a list of all event names that have subscribers."""
        with self._lock:
            return list(self._subscribers.keys())
    
    def subscriber_count(self, event_name: str) -> int:
        """Get the number of subscribers for an event."""
        with self._lock:
            return len(self._subscribers.get(event_name, []))
