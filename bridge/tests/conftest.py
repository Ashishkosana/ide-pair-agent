from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pair_bridge.app import create_app
from pair_bridge.config import Settings
from pair_bridge.outbound.mailbox import MailboxWriter
from pair_bridge.outbound.webhook import WebhookAdapter
from pair_bridge.store import EventStore


@pytest.fixture
def mailbox_dir(tmp_path: Path) -> Path:
    path = tmp_path / "mailbox"
    path.mkdir()
    return path


@pytest.fixture
def settings(mailbox_dir: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8765,
        mailbox_dir=str(mailbox_dir),
        assistant_webhook_url=None,
    )


@pytest.fixture
def store() -> EventStore:
    return EventStore()


@pytest.fixture
def client(settings: Settings, store: EventStore, mailbox_dir: Path) -> TestClient:
    app = create_app(
        settings=settings,
        store=store,
        mailbox=MailboxWriter(mailbox_dir),
        webhook=WebhookAdapter(None),
    )
    return TestClient(app)


@pytest.fixture
def make_context():
    return sample_context


def sample_context(**overrides):
    body = {
        "schema_version": "1",
        "intent": "share_selection",
        "prompt": None,
        "workspace": {"folder": "/tmp/demo", "git_branch": "main"},
        "file": {
            "path": "src/app.py",
            "language_id": "python",
            "content": None,
            "selection": {
                "text": "print('hello')\n",
                "start_line": 1,
                "end_line": 1,
            },
        },
        "diagnostics": [],
        "client": {"name": "ide-pair-agent-extension", "version": "0.1.0"},
    }
    body.update(overrides)
    return body
