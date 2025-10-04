from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, List, Sequence, Dict, Optional
import json
import operator
import re
import time

__all__ = [
    "Rule",
    "RuleGroup",
    "SmartPlaylist",
    "load_smart_playlists",
    "save_smart_playlists",
    "evaluate_smart_playlist",
]


# Supported operators mapping (symbol -> callable)
_OPS: Dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": lambda a, b: (a is not None and b is not None and a > b),
    ">=": lambda a, b: (a is not None and b is not None and a >= b),
    "<": lambda a, b: (a is not None and b is not None and a < b),
    "<=": lambda a, b: (a is not None and b is not None and a <= b),
    "contains": lambda a, b: (isinstance(a, str) and isinstance(b, str) and b.lower() in a.lower()),
    "not_contains": lambda a, b: (isinstance(a, str) and isinstance(b, str) and b.lower() not in a.lower()),
    "icontains": lambda a, b: (isinstance(a, str) and isinstance(b, str) and b.lower() in a.lower()),
    "startswith": lambda a, b: (isinstance(a, str) and isinstance(b, str) and a.lower().startswith(b.lower())),
    "endswith": lambda a, b: (isinstance(a, str) and isinstance(b, str) and a.lower().endswith(b.lower())),
    "in": lambda a, b: (a in b) if isinstance(b, (list, tuple, set)) else False,
    "between": lambda a, b: (
        a is not None
        and isinstance(b, (list, tuple))
        and len(b) == 2
        and b[0] is not None
        and b[1] is not None
        and b[0] <= a <= b[1]
    ),
    "regex": lambda a, b: bool(re.search(b, a)) if isinstance(a, str) and isinstance(b, str) else False,
    "has_tag": lambda a, b: (isinstance(a, (list, tuple)) and isinstance(b, str) and any(t.lower() == b.lower() for t in a)),
    "within_days": lambda a, b: (
        a is not None and isinstance(b, (int, float)) and b >= 0 and _coerce_epoch(a) >= (time.time() - (b * 86400))
    ),
}

# Fields allowed from MediaFile + metadata
_ALLOWED_FIELDS = {
    "path",
    "kind",
    "size",
    "mtime",
    # metadata overlay fields
    "title",
    "album",
    "artist",
    "genre",
    "year",
    "duration",
    "rating",
    "resolution",
    "bitrate",
    "tags",
}


@dataclass
class Rule:
    field: str
    op: str
    value: Any

    def matches(self, value_provider: Callable[[str], Any]) -> bool:
        if self.field not in _ALLOWED_FIELDS:
            return False
        left = value_provider(self.field)
        func = _OPS.get(self.op)
        if not func:
            return False
        # Attempt light type coercion for numeric comparisons
        numeric_ops = {">", ">=", "<", "<=", "between"}
        if self.op in numeric_ops:
            try:
                if isinstance(left, str) and left.replace(".", "", 1).isdigit():
                    left = float(left)
                if self.op == "between":
                    if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                        low, high = self.value
                        if isinstance(low, str) and low.replace(".", "", 1).isdigit():
                            low = float(low)
                        if isinstance(high, str) and high.replace(".", "", 1).isdigit():
                            high = float(high)
                        self_value = (low, high)
                    else:
                        return False
                else:
                    self_value = self.value
                    if isinstance(self_value, str) and self_value.replace(".", "", 1).isdigit():
                        self_value = float(self_value)
                # Overwrite value used in func call if we coerced
                if self.op == "between":
                    return bool(func(left, (self_value[0], self_value[1])))  # type: ignore[index]
                else:
                    return bool(func(left, self_value))
            except Exception:
                return False
        try:
            return bool(func(left, self.value))
        except Exception:
            return False


def _coerce_epoch(value: Any) -> float:
    try:
        if isinstance(value, (int, float)):
            # assume already epoch-ish (seconds)
            # guard against small numbers (e.g., year)
            if value > 10_000_000:  # ~1970-04-26 in seconds
                return float(value)
            return 0.0
        # attempt str -> float
        if isinstance(value, str) and value.replace('.', '', 1).isdigit():
            v = float(value)
            if v > 10_000_000:
                return v
        return 0.0
    except Exception:
        return 0.0


@dataclass
class RuleGroup:
    """A logical group of rules and/or subgroups.

    match: 'all' -> AND, 'any' -> OR
    negate: when True, the result of the group is inverted.
    """
    match: str = "all"
    negate: bool = False
    rules: List[Rule] = field(default_factory=list)
    groups: List["RuleGroup"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match": self.match,
            "negate": self.negate or False,
            "rules": [r.__dict__ for r in self.rules],
            "groups": [g.to_dict() for g in self.groups] if self.groups else [],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RuleGroup":
        rules = [Rule(**rd) for rd in data.get("rules", []) if isinstance(rd, dict)]
        groups = [RuleGroup.from_dict(gd) for gd in data.get("groups", []) if isinstance(gd, dict)]
        return RuleGroup(
            match=data.get("match", "all"),
            negate=bool(data.get("negate", False)),
            rules=rules,
            groups=groups,
        )

    def evaluate(self, value_provider: Callable[[str], Any]) -> bool:
        rule_results = [r.matches(value_provider) for r in self.rules]
        group_results = [g.evaluate(value_provider) for g in self.groups]
        # If both empty -> neutral True (so parent can still AND)
        combined = rule_results + group_results
        if not combined:
            result = True
        else:
            if self.match == "any":
                result = any(combined)
            else:
                result = all(combined)
        return (not result) if self.negate else result


@dataclass
class SmartPlaylist:
    name: str
    rules: List[Rule] = field(default_factory=list)  # legacy flat rules
    match: str = "all"  # legacy top-level match for flat rules
    limit: Optional[int] = None
    sort: Optional[str] = None  # reuse existing sort keys if provided
    description: str | None = None
    group: Optional[RuleGroup] = None  # new nested structure root

    def ensure_group(self) -> RuleGroup:
        """Return a root group; if absent create from legacy flat rules."""
        if self.group is None:
            # migrate in-memory
            self.group = RuleGroup(match=self.match, rules=list(self.rules))
        return self.group

    def to_dict(self) -> Dict[str, Any]:  # for persistence
        payload: Dict[str, Any] = {
            "name": self.name,
            "limit": self.limit,
            "sort": self.sort,
            "description": self.description,
        }
        # If group exists we persist only group (and ignore legacy fields)
        if self.group is not None:
            payload["group"] = self.group.to_dict()
        else:
            payload["match"] = self.match
            payload["rules"] = [r.__dict__ for r in self.rules]
        return payload

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SmartPlaylist":
        group_data = data.get("group")
        if isinstance(group_data, dict):  # new format
            sp = SmartPlaylist(
                name=data.get("name", "Unnamed"),
                limit=data.get("limit"),
                sort=data.get("sort"),
                description=data.get("description"),
            )
            sp.group = RuleGroup.from_dict(group_data)
            return sp
        # legacy
        rules = [Rule(**rd) for rd in data.get("rules", []) if isinstance(rd, dict)]
        return SmartPlaylist(
            name=data.get("name", "Unnamed"),
            rules=rules,
            match=data.get("match", "all"),
            limit=data.get("limit"),
            sort=data.get("sort"),
            description=data.get("description"),
        )


def load_smart_playlists(path: Path) -> List[SmartPlaylist]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            return []
        return [SmartPlaylist.from_dict(obj) for obj in raw if isinstance(obj, dict)]
    except Exception:
        return []


def save_smart_playlists(path: Path, playlists: Sequence[SmartPlaylist]) -> bool:
    """Persist playlists to JSON. Returns True on success."""
    try:
        payload = [sp.to_dict() for sp in playlists]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
        return True
    except Exception:
        return False


def evaluate_smart_playlist(
    playlist: SmartPlaylist,
    entries: Sequence[tuple[Any, Path]],
    metadata_provider: Callable[[Path], Any],
) -> List[tuple[Any, Path]]:
    # Determine evaluation mode (group vs legacy rules)
    use_group = playlist.group is not None or bool(playlist.rules)
    if not use_group:
        return list(entries)

    def entry_matches(entry: tuple[Any, Path]) -> bool:
        media, source_path = entry
        abs_path = (source_path / Path(media.path)).resolve(False)
        metadata = metadata_provider(abs_path)

        def value_provider(field: str) -> Any:
            if hasattr(media, field):
                return getattr(media, field)
            if hasattr(metadata, field):
                return getattr(metadata, field)
            if field == "path":
                return str(abs_path)
            return None

        if playlist.group is not None:
            root = playlist.group
        else:
            # On-the-fly virtual group from legacy rules
            root = RuleGroup(match=playlist.match, rules=playlist.rules)
        return root.evaluate(value_provider)

    filtered = [e for e in entries if entry_matches(e)]

    if playlist.sort:
        # defer sorting to caller if they reuse existing widget mechanism; leave unsorted here
        pass

    if playlist.limit is not None and playlist.limit >= 0:
        filtered = filtered[: playlist.limit]
    return filtered
