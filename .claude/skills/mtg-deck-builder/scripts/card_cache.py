"""Persistent on-disk cache for Scryfall card data.

A CardCache is bound to a specific directory; the module owns no global state,
so different callers can share or partition cache locations as they choose.

Cards are stored as individual JSON files keyed by a normalized form of the
card name. Each entry wraps the Scryfall response with a _cached_at timestamp
so callers can evict by age.

Usage:
    cache = CardCache(Path.home() / ".mtg" / "cache" / "scryfall" / "cards")
    card = cache.get("Sol Ring")
    if card is None:
        card = fetch_from_api("Sol Ring")
        cache.put("Sol Ring", card)

Module also exposes parse_duration(s) for callers that need to convert
strings like "30d" into seconds for max_age / eviction.
"""

import json
import re
import time
from pathlib import Path

_KEY_RE = re.compile(r"[^a-z0-9]+")
_DURATION_RE = re.compile(r"^(\d+)\s*([smhdw]?)$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "": 1}


def parse_duration(s):
    """Parse a duration like '30d', '12h', '300s' (bare digits = seconds)."""
    m = _DURATION_RE.match(s.strip().lower())
    if not m:
        raise ValueError(f"Invalid duration: {s!r} (use forms like 30d, 12h, 300s)")
    return int(m.group(1)) * _DURATION_UNITS[m.group(2)]


class CardCache:
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)

    def _key(self, name):
        return _KEY_RE.sub("_", name.lower()).strip("_")

    def _path(self, name):
        return self.cache_dir / f"{self._key(name)}.json"

    def get(self, name, max_age_sec=None):
        """Return cached card data, or None if missing/expired/corrupt."""
        path = self._path(name)
        if not path.exists():
            return None
        try:
            with path.open() as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if max_age_sec is not None:
            age = time.time() - entry.get("_cached_at", 0)
            if age > max_age_sec:
                return None
        return entry.get("card")

    def put(self, name, card):
        """Persist a card under the requested name and its canonical name."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"_cached_at": time.time(), "card": card})
        paths = {self._path(name)}
        canonical = card.get("name")
        if canonical:
            paths.add(self._path(canonical))
        for p in paths:
            try:
                p.write_text(payload)
            except OSError:
                pass

    def evict_name(self, name):
        """Remove one cached entry. Returns True if a file was deleted."""
        path = self._path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def evict_older_than(self, age_sec):
        """Remove entries older than age_sec (or corrupt). Returns count removed."""
        if not self.cache_dir.exists():
            return 0
        cutoff = time.time() - age_sec
        removed = 0
        for p in self.cache_dir.glob("*.json"):
            try:
                with p.open() as f:
                    ts = json.load(f).get("_cached_at", 0)
            except (json.JSONDecodeError, OSError):
                p.unlink(missing_ok=True)
                removed += 1
                continue
            if ts < cutoff:
                p.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear(self):
        """Remove all cache entries. Returns count removed."""
        if not self.cache_dir.exists():
            return 0
        removed = 0
        for p in self.cache_dir.glob("*.json"):
            p.unlink(missing_ok=True)
            removed += 1
        return removed

    def stats(self):
        """Return {count, bytes, oldest, newest} for the cache."""
        result = {"count": 0, "bytes": 0, "oldest": None, "newest": None}
        if not self.cache_dir.exists():
            return result
        for p in self.cache_dir.glob("*.json"):
            result["count"] += 1
            result["bytes"] += p.stat().st_size
            try:
                with p.open() as f:
                    ts = json.load(f).get("_cached_at", 0)
            except (json.JSONDecodeError, OSError):
                continue
            if result["oldest"] is None or ts < result["oldest"]:
                result["oldest"] = ts
            if result["newest"] is None or ts > result["newest"]:
                result["newest"] = ts
        return result
