import hashlib
import json
import os
import time


class JsonCache:
    def __init__(self, path="weather_cache.json"):
        self.path = path
        self._data = None

    def _load(self):
        if self._data is not None:
            return self._data
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._data = data
                        return data
        except Exception:
            pass
        self._data = {}
        return self._data

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data or {}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def key(value):
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key, ttl_seconds):
        data = self._load()
        item = data.get(key)
        if not isinstance(item, dict):
            return None
        if time.time() - float(item.get("time", 0)) > ttl_seconds:
            return None
        return item.get("value")

    def get_stale(self, key, max_age_seconds=86400):
        data = self._load()
        item = data.get(key)
        if not isinstance(item, dict):
            return None
        if time.time() - float(item.get("time", 0)) > max_age_seconds:
            return None
        return item.get("value")

    def prune(self, max_age_seconds=30 * 86400):
        data = self._load()
        now = time.time()
        dead = [k for k, v in data.items() if not isinstance(v, dict) or now - float(v.get("time", 0)) > max_age_seconds]
        for key in dead:
            data.pop(key, None)
        if dead:
            self._save()

    def set(self, key, value):
        data = self._load()
        data[key] = {"time": time.time(), "value": value}
        if len(data) > 500:
            self.prune()
        self._save()
