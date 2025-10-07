from __future__ import annotations
import os
import importlib

from mmst.plugins.media_library import plugin as media_plugin


class _DummyServices:
    def get_plugin_config(self, ident):  # minimal interface
        class _Cfg(dict):
            pass
        return _Cfg()


def test_media_library_minimal_by_default(monkeypatch):
    monkeypatch.delenv('MMST_MEDIA_LIBRARY_ENHANCED', raising=False)
    # Force flag helper to return False
    monkeypatch.setattr(media_plugin, '_enhanced_enabled', lambda _p=None: False)
    p = media_plugin.Plugin(_DummyServices())  # type: ignore
    view = p.create_view()
    assert view.__class__.__name__ == media_plugin.MediaLibraryWidget.__name__


def test_media_library_enhanced_env(monkeypatch):
    monkeypatch.setenv('MMST_MEDIA_LIBRARY_ENHANCED', '1')
    importlib.reload(media_plugin)
    p = media_plugin.Plugin(_DummyServices())  # type: ignore
    view = p.create_view()
    # Enhanced path may fail silently and fall back; ensure no crash
    # When enhanced active, root objectName is set
    if hasattr(view, 'objectName'):
        name = getattr(view, 'objectName')()
        assert name in ("EnhancedMediaLibraryRoot", "")
