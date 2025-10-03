from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, MutableMapping, Optional


class ConfigStore:
    """Thread-safe JSON-backed configuration store."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._data = {}
            return
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._data = {}
            return
        if isinstance(raw, dict):
            self._data = {key.lower(): value for key, value in raw.items() if isinstance(value, dict)}
        else:
            self._data = {}

    def save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, sort_keys=True)

    def get_plugin(self, identifier: str) -> "PluginConfig":
        identifier = identifier.lower()
        with self._lock:
            bucket = self._data.setdefault(identifier, {})
            snapshot = dict(bucket)
        return PluginConfig(self, identifier, snapshot)

    def _get_bucket(self, identifier: str) -> Dict[str, Any]:
        identifier = identifier.lower()
        with self._lock:
            return self._data.setdefault(identifier, {})

    def update_plugin(self, identifier: str, values: Dict[str, Any]) -> None:
        identifier = identifier.lower()
        with self._lock:
            bucket = self._data.setdefault(identifier, {})
            bucket.update(values)
            self.save()

    def set_plugin_value(self, identifier: str, key: str, value: Any) -> None:
        self.update_plugin(identifier, {key: value})

    def write_plugin(self, identifier: str, values: Dict[str, Any]) -> None:
        identifier = identifier.lower()
        with self._lock:
            self._data[identifier] = dict(values)
            self.save()

    def remove_plugin(self, identifier: str) -> None:
        identifier = identifier.lower()
        with self._lock:
            if identifier in self._data:
                del self._data[identifier]
                self.save()

    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._data))


class PluginConfig(MutableMapping[str, Any]):
    """Mapping view over a plugin's configuration bucket."""

    def __init__(self, store: ConfigStore, identifier: str, cache: Optional[Dict[str, Any]] = None) -> None:
        self._store = store
        self._identifier = identifier
        self._cache = cache or {}

    def __getitem__(self, key: str) -> Any:
        return self._cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._store.set_plugin_value(self._identifier, key, value)

    def __delitem__(self, key: str) -> None:
        if key not in self._cache:
            raise KeyError(key)
        del self._cache[key]
        self._store.write_plugin(self._identifier, self._cache)

    def __iter__(self) -> Iterator[str]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)

    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(key, default)

    def update(self, other: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:  # type: ignore[override]
        payload: Dict[str, Any] = {}
        if other:
            payload.update(other)
        if kwargs:
            payload.update(kwargs)
        if not payload:
            return
        self._cache.update(payload)
        self._store.update_plugin(self._identifier, payload)

    def clear(self) -> None:  # type: ignore[override]
        if not self._cache:
            return
        self._cache.clear()
        self._store.write_plugin(self._identifier, self._cache)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._cache)

    def refresh(self) -> None:
        latest = self._store._get_bucket(self._identifier)
        self._cache = dict(latest)