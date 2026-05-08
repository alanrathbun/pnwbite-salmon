"""Storage abstraction.

v1: file-based. v2 (Railway): swap implementation for Postgres/volume without
touching callers. Atomic writes via tempfile + os.replace.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Keys that map to specific filenames rather than the default `.<key>.json` pattern.
SPECIAL_PATHS = {
    "report_html": "report.html",
}


class FileStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str, *, json_ext: bool = False) -> Path:
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
