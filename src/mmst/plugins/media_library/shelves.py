from __future__ import annotations
"""Shelf (carousel) + simple settings helpers for Media Library plugin.

This module isolates persistence + enhanced dashboard construction so that the
main plugin file can shrink and stay readable.
"""
from typing import Any, Dict, List, Tuple, Optional, Callable

from .views.enhanced.dashboard import enhanced_dashboard_enabled, EnhancedDashboard  # type: ignore
from .queries import query_top_rated  # type: ignore

# ---------------- Persistence helpers -----------------

def _config_bucket(plugin: Any) -> Dict[str, Any]:
    try:
        return plugin.services.get_plugin_config(plugin.manifest.identifier) or {}
    except Exception:
        return {}

def merge_and_save(plugin: Any, updated: Dict[str, Any]) -> None:
    try:
        current = _config_bucket(plugin)
        current.update(updated)
        plugin.services.save_plugin_config(plugin.manifest.identifier, current)
    except Exception:
        pass

def load_persistent_simple_settings(plugin: Any) -> Tuple[str, List[str]]:
    """Return (view_mode, shelf_order). Falls back to defaults on errors."""
    view_mode = "enhanced"
    shelf_order: List[str] = ["recent", "top_rated"]
    cfg = _config_bucket(plugin)
    try:
        view_mode = str(cfg.get("view_mode", view_mode))
    except Exception:
        view_mode = "enhanced"
    try:
        shelf_order = validate_shelf_order(cfg.get("shelf_order", shelf_order))  # type: ignore[arg-type]
    except Exception:
        shelf_order = ["recent", "top_rated"]
    return view_mode, shelf_order

# ---------------- Shelf logic -----------------

def validate_shelf_order(order: List[str]) -> List[str]:
    allowed = {"recent", "top_rated"}
    seen: List[str] = []
    for sid in order:
        if sid in allowed and sid not in seen:
            seen.append(sid)
    for sid in ["recent", "top_rated"]:
        if sid not in seen:
            seen.append(sid)
    return seen

def shelf_title(shelf_id: str) -> str:
    return {"recent": "Zuletzt hinzugefügt", "top_rated": "Top bewertet"}.get(shelf_id, shelf_id)

def shelf_provider(plugin: Any, shelf_id: str) -> Callable[[], List[Any]]:
    index = plugin.get_library_index()
    if shelf_id == "recent":
        return lambda: plugin.list_recent_detailed(limit=30)
    if shelf_id == "top_rated":
        return lambda: query_top_rated(index, limit=30)
    return lambda: []

def build_shelf_definitions(plugin: Any, shelf_order: List[str]) -> List[Tuple[str, str, Callable[[], List[Any]]]]:
    defs: List[Tuple[str, str, Callable[[], List[Any]]]] = []
    for sid in shelf_order:
        defs.append((sid, shelf_title(sid), shelf_provider(plugin, sid)))
    return defs

# ---------------- Dashboard construction -----------------

def build_enhanced_dashboard(plugin: Any) -> Optional[EnhancedDashboard]:
    if not enhanced_dashboard_enabled():
        return None
    try:
        shelves = build_shelf_definitions(plugin, getattr(plugin, "_shelf_order", ["recent", "top_rated"]))
        hero_provider = lambda: plugin.list_recent_detailed(limit=30)  # noqa: E731
        return EnhancedDashboard(shelves, hero_provider=hero_provider, plugin=plugin)
    except Exception:
        return None

__all__ = [
    "build_enhanced_dashboard",
    "validate_shelf_order",
    "merge_and_save",
    "load_persistent_simple_settings",
]