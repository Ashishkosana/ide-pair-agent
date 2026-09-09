from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

def test_secrets_redacted_in_mailbox(
    client: TestClient, mailbox_dir: Path, make_context
) -> None:
    body = make_context(
        prompt="rotate this api_key=supersecretvalueNOW",
        file={
            "path": "src/app.py",
            "language_id": "python",
            "content": None,
            "selection": {
                "text": (
                    "TOKEN = 'sk-abcdefghijklmnopqrstuvwxyz123456'\n"
                    "def greet(name: str) -> str:\n"
                    "    return f'hello {name}'\n"
                ),
                "start_line": 1,
                "end_line": 3,
            },
        },
    )
    response = client.post("/v1/context", json=body)
    assert response.status_code == 200
    assert response.json()["redacted"] is True
    mailbox = (mailbox_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "supersecretvalueNOW" not in mailbox
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in mailbox
    assert "[REDACTED]" in mailbox
