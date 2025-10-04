"""
Tests for the EventBus system.

Tests cover:
- Basic pub/sub functionality
- Subscribe/unsubscribe lifecycle
- Thread safety with concurrent access
- Error isolation (bad subscribers don't affect others)
"""

import pytest
import threading
from mmst.core.events import EventBus


def test_event_bus_basic_subscribe_emit():
    """Test basic subscribe and emit functionality."""
    bus = EventBus()
    received = []

    def handler(event_name, data):
        received.append((event_name, data))

    bus.subscribe("test.event", handler)
    bus.emit("test.event", {"message": "hello"})

    assert len(received) == 1
    assert received[0][0] == "test.event"
    assert received[0][1]["message"] == "hello"


def test_event_bus_multiple_subscribers():
    """Test that multiple subscribers all receive events."""
    bus = EventBus()
    received_1 = []
    received_2 = []

    def handler_1(event_name, data):
        received_1.append(data)

    def handler_2(event_name, data):
        received_2.append(data)

    bus.subscribe("test.event", handler_1)
    bus.subscribe("test.event", handler_2)
    bus.emit("test.event", {"value": 42})

    assert len(received_1) == 1
    assert len(received_2) == 1
    assert received_1[0]["value"] == 42
    assert received_2[0]["value"] == 42


def test_event_bus_unsubscribe():
    """Test that unsubscribe removes a handler."""
    bus = EventBus()
    received = []

    def handler(event_name, data):
        received.append(data)

    bus.subscribe("test.event", handler)
    bus.emit("test.event", {"first": True})
    
    bus.unsubscribe("test.event", handler)
    bus.emit("test.event", {"second": True})

    # Should only receive the first event
    assert len(received) == 1
    assert received[0]["first"] is True


def test_event_bus_different_topics():
    """Test that events are isolated by topic."""
    bus = EventBus()
    received_a = []
    received_b = []

    def handler_a(event_name, data):
        received_a.append(data)

    def handler_b(event_name, data):
        received_b.append(data)

    bus.subscribe("topic.a", handler_a)
    bus.subscribe("topic.b", handler_b)
    
    bus.emit("topic.a", {"data": "A"})
    bus.emit("topic.b", {"data": "B"})

    assert len(received_a) == 1
    assert len(received_b) == 1
    assert received_a[0]["data"] == "A"
    assert received_b[0]["data"] == "B"


def test_event_bus_error_isolation():
    """Test that a failing subscriber doesn't affect others."""
    bus = EventBus()
    received_good = []

    def bad_handler(event_name, data):
        raise ValueError("I'm broken!")

    def good_handler(event_name, data):
        received_good.append(data)

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)
    
    # Should not raise, and good_handler should still receive
    bus.emit("test.event", {"message": "test"})

    assert len(received_good) == 1
    assert received_good[0]["message"] == "test"


def test_event_bus_thread_safety():
    """Test that EventBus is thread-safe with concurrent access."""
    bus = EventBus()
    received = []
    lock = threading.Lock()

    def handler(event_name, data):
        with lock:
            received.append(data)

    bus.subscribe("test.event", handler)

    # Emit events from multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=bus.emit, args=("test.event", {"id": i}))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # All events should be received
    assert len(received) == 10
    ids = sorted([item["id"] for item in received])
    assert ids == list(range(10))


def test_event_bus_no_subscribers():
    """Test that emitting to a topic with no subscribers doesn't error."""
    bus = EventBus()
    
    # Should not raise
    bus.emit("nonexistent.event", {"data": "test"})


def test_event_bus_unsubscribe_nonexistent():
    """Test that unsubscribing a handler that doesn't exist is safe."""
    bus = EventBus()

    def handler(event_name, data):
        pass

    # Should not raise
    bus.unsubscribe("nonexistent.event", handler)


def test_event_bus_subscribe_same_handler_multiple_times():
    """Test that subscribing the same handler multiple times works."""
    bus = EventBus()
    received = []

    def handler(event_name, data):
        received.append(data)

    # Subscribe twice
    bus.subscribe("test.event", handler)
    bus.subscribe("test.event", handler)
    
    bus.emit("test.event", {"message": "test"})

    # Handler should be called only once (deduplication)
    assert len(received) == 1


def test_event_bus_with_empty_data():
    """Test that emitting without data parameter defaults to empty dict."""
    bus = EventBus()
    received = []

    def handler(event_name, data):
        received.append(data)

    bus.subscribe("test.event", handler)
    bus.emit("test.event")  # No data parameter

    assert len(received) == 1
    assert received[0] == {}
