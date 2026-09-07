from __future__ import annotations

import json
from pathlib import Path

from pair_bridge.outbound.mailbox import MailboxWriter


def test_mailbox_appends_jsonl(tmp_path: Path) -> None:
    writer = MailboxWriter(tmp_path / "box")
    path = writer.write({"kind": "context", "context_id": "a", "n": 1})
    writer.write({"kind": "context", "context_id": "b", "n": 2})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["context_id"] == "a"
    assert second["n"] == 2
    assert path.name == "events.jsonl"


def test_mailbox_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "nested"
    writer = MailboxWriter(target)
    writer.write({"ok": True})
    assert (target / "events.jsonl").is_file()
