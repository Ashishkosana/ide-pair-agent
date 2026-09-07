"""FastAPI application: context in, replies in, latest reply out."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from pair_bridge import __version__
from pair_bridge.agent.policy import PolicyDecision, resolve_decision
from pair_bridge.config import Settings
from pair_bridge.models import (
    AssistantReply,
    AssistantReplyIn,
    ContextAccepted,
    HealthOut,
    IdeContextIn,
    PolicyInfo,
    StoredEvent,
    utcnow,
)
from pair_bridge.outbound.mailbox import MailboxWriter
from pair_bridge.outbound.webhook import WebhookAdapter
from pair_bridge.redact import redact_context
from pair_bridge.store import EventStore


@dataclass
class Runtime:
    settings: Settings
    store: EventStore
    mailbox: MailboxWriter
    webhook: WebhookAdapter


def _truncate(payload: IdeContextIn, limit: int) -> tuple[IdeContextIn, bool]:
    """Cap large text fields so M1 cannot be used as a dump hose."""
    truncated = False
    data = payload.model_dump()
    file_data = data.get("file") or {}
    for key in ("content",):
        value = file_data.get(key)
        if isinstance(value, str) and len(value) > limit:
            file_data[key] = value[:limit] + "\n…[truncated]"
            truncated = True
    selection = file_data.get("selection") or {}
    text = selection.get("text")
    if isinstance(text, str) and len(text) > limit:
        selection["text"] = text[:limit] + "\n…[truncated]"
        file_data["selection"] = selection
        truncated = True
    prompt = data.get("prompt")
    if isinstance(prompt, str) and len(prompt) > limit:
        data["prompt"] = prompt[:limit] + "\n…[truncated]"
        truncated = True
    data["file"] = file_data
    return IdeContextIn.model_validate(data), truncated


def _envelope(
    *,
    context_id: str,
    payload: IdeContextIn,
    policy: PolicyDecision,
    reply_to: str,
) -> dict[str, Any]:
    return {
        "type": "ide.context",
        "schema_version": payload.schema_version,
        "context_id": context_id,
        "created_at": utcnow().isoformat(),
        "intent": payload.intent,
        "policy": {
            "mode": policy.mode,
            "reason": policy.reason,
            "summarize": policy.summarize,
        },
        "payload": payload.model_dump(),
        "reply_to": reply_to,
    }


def create_app(
    settings: Settings | None = None,
    store: EventStore | None = None,
    mailbox: MailboxWriter | None = None,
    webhook: WebhookAdapter | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = store or EventStore()
    mailbox = mailbox or MailboxWriter(settings.mailbox_dir)
    webhook = webhook or WebhookAdapter(
        settings.assistant_webhook_url,
        timeout_seconds=settings.webhook_timeout_seconds,
    )
    runtime = Runtime(
        settings=settings, store=store, mailbox=mailbox, webhook=webhook
    )

    app = FastAPI(
        title="IDE Pair Agent Bridge",
        version=__version__,
        description=(
            "Local M1 bridge: persist IDE context, redact obvious secrets, "
            "drop JSONL for an assistant, optionally POST a user-configured "
            "webhook, and accept replies back. Not a finished LLM."
        ),
    )
    app.state.runtime = runtime

    @app.get("/v1/health", response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(
            version=__version__,
            webhook_configured=runtime.settings.webhook_configured,
            mailbox_dir=str(runtime.mailbox.directory),
        )

    @app.post("/v1/context", response_model=ContextAccepted)
    def post_context(body: IdeContextIn) -> ContextAccepted:
        trimmed, truncated = _truncate(body, runtime.settings.max_payload_chars)
        redacted, hits = redact_context(trimmed)
        decision = resolve_decision(
            redacted, webhook_configured=runtime.settings.webhook_configured
        )
        context_id = str(uuid.uuid4())
        policy = PolicyInfo(
            mode=decision.mode,
            reason=decision.reason,
            forward=decision.forward,
            summarize=decision.summarize,
            channels=list(decision.channels),
        )
        event = StoredEvent(
            context_id=context_id,
            created_at=utcnow(),
            payload=redacted,
            policy=policy,
            redaction_hits=hits,
            truncated=truncated,
            channels=list(decision.channels),
        )
        runtime.store.put_event(event)

        mailbox_path = None
        webhook_result: dict[str, Any] = {
            "attempted": False,
            "ok": True,
            "skipped": True,
        }
        if decision.forward:
            reply_to = (
                f"http://127.0.0.1:{runtime.settings.port}/v1/assistant-reply"
            )
            envelope = _envelope(
                context_id=context_id,
                payload=redacted,
                policy=decision,
                reply_to=reply_to,
            )
            if "mailbox" in decision.channels:
                written = runtime.mailbox.write(
                    {"kind": "context", **envelope}
                )
                mailbox_path = str(written)
            if "webhook" in decision.channels:
                webhook_result = runtime.webhook.send(envelope)

        return ContextAccepted(
            context_id=context_id,
            accepted=decision.forward,
            redacted=bool(hits),
            redaction_hits=hits,
            truncated=truncated,
            channels=list(decision.channels) if decision.forward else [],
            policy=policy,
            webhook=webhook_result,
            mailbox_path=mailbox_path,
            reply=None,
        )

    @app.get("/v1/events")
    def list_events() -> dict[str, Any]:
        events = [event.model_dump(mode="json") for event in runtime.store.list_events()]
        return {"events": events}

    @app.post("/v1/assistant-reply", response_model=AssistantReply)
    def post_reply(body: AssistantReplyIn) -> AssistantReply:
        if body.context_id and runtime.store.get_event(body.context_id) is None:
            raise HTTPException(
                status_code=404,
                detail=f"unknown context_id: {body.context_id}",
            )
        reply = AssistantReply(
            reply_id=str(uuid.uuid4()),
            context_id=body.context_id,
            text=body.text,
            source=body.source,
        )
        runtime.store.put_reply(reply)
        runtime.mailbox.write(
            {
                "kind": "assistant_reply",
                "reply_id": reply.reply_id,
                "context_id": reply.context_id,
                "created_at": reply.created_at.isoformat(),
                "source": reply.source,
                "text": reply.text,
            }
        )
        return reply

    @app.get("/v1/replies/latest")
    def latest_reply(
        context_id: str | None = Query(default=None),
    ) -> dict[str, Any]:
        reply = runtime.store.latest_reply(context_id)
        if reply is None:
            return {"reply": None}
        return {"reply": reply.model_dump(mode="json")}

    return app


app = create_app()
