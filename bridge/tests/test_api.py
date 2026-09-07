from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from pair_bridge.app import create_app
from pair_bridge.config import Settings
from pair_bridge.outbound.mailbox import MailboxWriter
from pair_bridge.outbound.webhook import WebhookAdapter
from pair_bridge.store import EventStore


def test_health(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "pair-bridge"
    assert body["webhook_configured"] is False


def test_post_context_persists_and_mailbox(
    client: TestClient, mailbox_dir: Path, store: EventStore, make_context
) -> None:
    response = client.post("/v1/context", json=make_context())
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["policy"]["mode"] == "m1-default"
    assert "mailbox" in body["channels"]
    assert body["mailbox_path"]
    assert store.get_event(body["context_id"]) is not None

    events_file = mailbox_dir / "events.jsonl"
    assert events_file.exists()
    line = events_file.read_text(encoding="utf-8").strip()
    assert '"kind":"context"' in line
    assert body["context_id"] in line

    listed = client.get("/v1/events")
    assert listed.status_code == 200
    assert len(listed.json()["events"]) == 1


def test_webhook_called_when_configured(mailbox_dir: Path, make_context) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = WebhookAdapter(
        "https://assistant.example/hook",
        client=http,
    )
    settings = Settings(
        mailbox_dir=str(mailbox_dir),
        assistant_webhook_url="https://assistant.example/hook",
    )
    app = create_app(
        settings=settings,
        store=EventStore(),
        mailbox=MailboxWriter(mailbox_dir),
        webhook=adapter,
    )
    client = TestClient(app)
    response = client.post("/v1/context", json=make_context())
    assert response.status_code == 200
    assert response.json()["webhook"]["attempted"] is True
    assert response.json()["webhook"]["ok"] is True
    assert seen, "webhook adapter should have POSTed"
    assert seen[0].headers.get("x-pair-agent-event") == "ide.context"
    http.close()


def test_webhook_skipped_when_not_configured(client: TestClient, make_context) -> None:
    response = client.post("/v1/context", json=make_context())
    assert response.status_code == 200
    webhook = response.json()["webhook"]
    assert webhook["skipped"] is True
    assert webhook["attempted"] is False


def test_assistant_reply_round_trip(
    client: TestClient, mailbox_dir: Path, make_context
) -> None:
    created = client.post("/v1/context", json=make_context()).json()
    context_id = created["context_id"]

    empty = client.get("/v1/replies/latest", params={"context_id": context_id})
    assert empty.json()["reply"] is None

    posted = client.post(
        "/v1/assistant-reply",
        json={
            "context_id": context_id,
            "text": "Looks good — add a type hint.",
            "source": "desktop-assistant",
        },
    )
    assert posted.status_code == 200
    latest = client.get("/v1/replies/latest", params={"context_id": context_id})
    reply = latest.json()["reply"]
    assert reply["text"] == "Looks good — add a type hint."
    assert reply["context_id"] == context_id

    mailbox_text = (mailbox_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "assistant_reply" in mailbox_text


def test_reply_unknown_context_id(client: TestClient) -> None:
    response = client.post(
        "/v1/assistant-reply",
        json={"context_id": "does-not-exist", "text": "hi", "source": "test"},
    )
    assert response.status_code == 404


def test_webhook_failure_does_not_fail_request(mailbox_dir: Path, make_context) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        mailbox_dir=str(mailbox_dir),
        assistant_webhook_url="https://assistant.example/hook",
    )
    app = create_app(
        settings=settings,
        store=EventStore(),
        mailbox=MailboxWriter(mailbox_dir),
        webhook=WebhookAdapter("https://assistant.example/hook", client=http),
    )
    response = TestClient(app).post("/v1/context", json=make_context())
    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["webhook"]["ok"] is False
    http.close()


def test_ask_intent_accepted(client: TestClient, make_context) -> None:
    body = make_context(intent="ask", prompt="Why is this unused?")
    response = client.post("/v1/context", json=body)
    assert response.status_code == 200
    assert response.json()["accepted"] is True
