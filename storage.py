"""Storage abstraction.

v1: file-based. v2 (Railway): swap implementation for Postgres/volume without
touching callers. Atomic writes via tempfile + os.replace.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Protocol


class Storage(Protocol):
    """Storage interface — file-based v1, Postgres or volume-backed v2.

    Implementations must provide atomic writes for both text and JSON.
    """

    def read(self, key: str) -> str | None: ...
    def write(self, key: str, content: str) -> None: ...
    def read_json(self, key: str) -> Any | None: ...
    def write_json(self, key: str, obj: Any) -> None: ...
    def update_json(self, key: str, mutator: Callable[[Any], Any]) -> Any: ...


# Keys that map to specific filenames rather than the default `.<key>.json` pattern.
SPECIAL_PATHS = {
    "report_html": "report.html",
    "report_data": ".report_data.json",
}


class FileStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        # Single RLock guards all read-modify-write paths against concurrent
        # mutation. Background callers (ThreadPoolExecutor in fetch_all)
        # frequently update the same JSON cache keys (nws_grid, dart_runtiming);
        # without this lock concurrent read-then-write loses entries.
        self._lock = threading.RLock()

    def _path(self, key: str, *, json_ext: bool = False) -> Path:
        """Return the filesystem path for *key*.

        SPECIAL_PATHS entries override both the json_ext branch and the plain
        text branch, so the caller never needs to know about the suffix rules.
        """
        if key in SPECIAL_PATHS:
            return self.root / SPECIAL_PATHS[key]
        if json_ext:
            return self.root / f".{key}_cache.json"
        return self.root / f".{key}"

    def read(self, key: str) -> str | None:
        p = self._path(key)
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")

    def write(self, key: str, content: str) -> None:
        p = self._path(key)
        self._atomic_write(p, content)

    def read_json(self, key: str) -> Any | None:
        p = self._path(key, json_ext=True)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def write_json(self, key: str, obj: Any) -> None:
        p = self._path(key, json_ext=True)
        self._atomic_write(p, json.dumps(obj, indent=2, sort_keys=True))

    def update_json(self, key: str, mutator: Callable[[Any], Any]) -> Any:
        """Atomic read-modify-write of a JSON cache.

        ``mutator`` receives the current value (or ``None`` if no cache entry
        exists) and returns the new value to persist. The whole read/mutate/
        write cycle runs inside ``self._lock`` so concurrent callers under a
        ThreadPoolExecutor never lose updates to the same key.

        The mutator should be cheap; do any expensive I/O (e.g. fetching the
        URL to insert) *before* calling ``update_json``.
        """
        with self._lock:
            current = self.read_json(key)
            updated = mutator(current)
            self.write_json(key, updated)
            return updated

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=target.name + ".",
            suffix=".tmp",
            dir=target.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def default_root() -> Path:
    """Return DATA_DIR env var if set, otherwise the project root.

    On Railway, DATA_DIR is set to /data (a mounted volume). Locally, falls
    back to the directory containing this storage.py file.
    """
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent
