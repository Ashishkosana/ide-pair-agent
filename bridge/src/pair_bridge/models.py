"""Shared protocol models for the IDE ↔ bridge ↔ assistant loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["share_selection", "share_file_diagnostics", "ask"]
Severity = Literal["error", "warning", "info", "hint"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Selection(BaseModel):
    text: str = ""
    start_line: int | None = None
    end_line: int | None = None


class FileContext(BaseModel):
    path: str | None = None
    language_id: str | None = None
    content: str | None = None
    selection: Selection | None = None


class WorkspaceContext(BaseModel):
    folder: str | None = None
    git_branch: str | None = None


class Diagnostic(BaseModel):
    severity: Severity = "info"
    message: str
    source: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class ClientInfo(BaseModel):
    name: str = "ide-pair-agent-extension"
    version: str = "0.1.0"


class IdeContextIn(BaseModel):
    """POST /v1/context body. Sent by the VS Code extension (or curl)."""

    schema_version: str = "1"
    intent: Intent
    prompt: str | None = None
    workspace: WorkspaceContext = Field(default_factory=WorkspaceContext)
    file: FileContext = Field(default_factory=FileContext)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    client: ClientInfo = Field(default_factory=ClientInfo)


class PolicyInfo(BaseModel):
    mode: str
    reason: str
    forward: bool
    summarize: bool
    channels: list[str]


class ContextAccepted(BaseModel):
    context_id: str
    accepted: bool
    redacted: bool
    redaction_hits: list[str]
    truncated: bool
    channels: list[str]
    policy: PolicyInfo
    webhook: dict[str, Any]
    mailbox_path: str | None
    reply: dict[str, Any] | None = None


class AssistantReplyIn(BaseModel):
    """POST /v1/assistant-reply body. Pushed by an assistant or automation."""

    context_id: str | None = None
    text: str
    source: str = "assistant"


class AssistantReply(BaseModel):
    reply_id: str
    context_id: str | None
    text: str
    source: str
    created_at: datetime = Field(default_factory=utcnow)


class StoredEvent(BaseModel):
    context_id: str
    created_at: datetime
    payload: IdeContextIn
    policy: PolicyInfo
    redaction_hits: list[str]
    truncated: bool
    channels: list[str]


class HealthOut(BaseModel):
    status: str = "ok"
    service: str = "pair-bridge"
    version: str
    webhook_configured: bool
    mailbox_dir: str
