import json
import os
import threading
from typing import Any, Dict, List, Optional


class Store:
    """Thread-safe JSON document store with atomic persistence."""

    COLLECTIONS = ("ideas", "plans", "artifacts")

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = {c: {} for c in self.COLLECTIONS}
        if os.path.exists(path):
            self._load()

    def _load(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in self.COLLECTIONS:
            self._data[c] = data.get(c, {})

    def _persist(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)

    def put(self, collection: str, obj: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._data[collection][obj["id"]] = obj
            self._persist()
            return obj

    def get(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._data[collection].get(id)

    def list(self, collection: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data[collection].values())

    def update(self, collection: str, id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            obj = self._data[collection].get(id)
            if obj is None:
                return None
            obj.update(fields)
            self._persist()
            return obj
