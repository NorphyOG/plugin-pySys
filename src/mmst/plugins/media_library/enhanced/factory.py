from __future__ import annotations
from typing import Any
import os

ENHANCED_ENV_FLAG = "MMST_MEDIA_LIBRARY_ENHANCED"


def is_enhanced_mode_enabled(plugin: Any) -> bool:
    # Order: explicit env var > plugin config > plugin attribute fallback
    if os.environ.get(ENHANCED_ENV_FLAG) in {"1", "true", "TRUE", "yes"}:
        return True
    try:
        cfg = plugin.load_config()  # plugin should provide load_config
        return bool(cfg.get("enhanced_enabled", False))
    except Exception:
        return False


def create_enhanced_widget(plugin: Any):
    try:
        from .base import EnhancedRootWidget  # local import to avoid heavy cost if not used
        widget = EnhancedRootWidget(plugin)
        # Ensure the widget is properly initialized
        if hasattr(widget, '_load_initial_entries') and callable(widget._load_initial_entries):
            widget._load_initial_entries()
        return widget
    except Exception as e:
        import logging
        logger = logging.getLogger("mmst.media_library")
        logger.error(f"Error creating enhanced widget: {e}")
        # Return a basic placeholder widget with error message
        try:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            error_label = QLabel(f"Enhanced view initialization failed: {e}")
            layout.addWidget(error_label)
            return placeholder
        except Exception:
            # If PySide6 is not available, return None and let plugin handle fallback
            return None
