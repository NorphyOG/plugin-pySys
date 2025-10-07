from __future__ import annotations

"""Enhanced Media Library modular implementation (phase 1 scaffold).

Exposes a factory `create_enhanced_widget(plugin)` that returns the root
`EnhancedRootWidget` if all required GUI dependencies are available.
Falls back by raising an ImportError which the caller must catch.
"""
from .factory import create_enhanced_widget  # noqa: F401
