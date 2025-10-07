"""Temporary placeholder for future PlayerPanel extraction.

This file was introduced during refactor planning. Actual integration of a
standalone player panel is deferred; existing inline player logic in
`plugin.py` remains authoritative to avoid regression risk while tests rely
on those attributes. Once stabilized, this module will host the real
`PlayerPanel` class and `plugin.py` will delegate to it.
"""

class PlayerPanel:  # type: ignore[misc]
    def __init__(self) -> None:  # noqa: D401
        self.available = False
        self.widget = None
        self.video_widget = None
        self.group_box = None
    def load_media(self, *_, **__): pass
    def clear(self): pass
    def play_pause(self): pass
    def stop(self): pass
    def set_volume(self, *_, **__): pass
    def set_position(self, *_, **__): pass
    def current_state(self) -> str: return "unavailable"


__all__ = ["PlayerPanel"]
