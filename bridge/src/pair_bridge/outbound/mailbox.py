"""Append-only JSONL mailbox. An assistant (or a human) can tail this file."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class MailboxWriter:
    def __init__(self, directory: str | Path, filename: str = "events.jsonl") -> None:
        self.directory = Path(directory)
        self.path = self.directory / filename
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        return self.path
