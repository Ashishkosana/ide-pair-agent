"""Routing / allow / summarize / channel policy.

Deterministic rules over intent, diagnostics, and selection. This process
never generates the assistant's coding answer — it only decides whether to
forward redacted context, whether to replace oversized text with a
signature excerpt, and which outbound channel to use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pair_bridge.agent.summarize import (
    SUMMARIZE_CONTENT_CHARS,
    SUMMARIZE_SELECTION_CHARS,
)
from pair_bridge.models import IdeContextIn
from pair_bridge.redact import REDACTED

# After redaction, leftover alphanumeric budget that still counts as "useful".
_SECRETS_ONLY_USEFUL_CHARS = 40
_BINARY_NONTEXT_RATIO = 0.30
_BINARY_SAMPLE_CHARS = 8_192

LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "pnpm-lock.yml",
        "bun.lock",
        "bun.lockb",
        "Cargo.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
        "flake.lock",
    }
)

BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".woff",
        ".woff2",
        ".ttf",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".wasm",
        ".class",
        ".o",
        ".pyc",
    }
)

_VENDOR_SEGMENTS = frozenset({"node_modules", ".git"})


@dataclass(frozen=True)
class PolicyDecision:
    forward: bool
    summarize: bool
    channels: tuple[str, ...]
    reason: str
    mode: str


def _basename(path: str | None) -> str:
    if not path:
        return ""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _text_blob(payload: IdeContextIn) -> str:
    parts: list[str] = []
    if payload.prompt:
        parts.append(payload.prompt)
    if payload.file.content:
        parts.append(payload.file.content)
    if payload.file.selection and payload.file.selection.text:
        parts.append(payload.file.selection.text)
    for diagnostic in payload.diagnostics:
        parts.append(diagnostic.message)
    return "\n".join(parts)


def _looks_binary(text: str) -> bool:
    if not text:
        return False
    if "\x00" in text:
        return True
    sample = text[:_BINARY_SAMPLE_CHARS]
    weird = 0
    for char in sample:
        code = ord(char)
        if code < 32 and char not in "\t\n\r":
            weird += 1
        elif code == 127:
            weird += 1
    return (weird / len(sample)) >= _BINARY_NONTEXT_RATIO


def _is_binary_ish(payload: IdeContextIn) -> bool:
    ext = Path(payload.file.path or "").suffix.lower()
    texts: list[str] = []
    if payload.file.content:
        texts.append(payload.file.content)
    if payload.file.selection and payload.file.selection.text:
        texts.append(payload.file.selection.text)
    if ext in BINARY_EXTENSIONS and (payload.file.content or not texts):
        return True
    return any(_looks_binary(text) for text in texts)


def _is_lockfile(payload: IdeContextIn) -> bool:
    return _basename(payload.file.path) in LOCKFILE_NAMES


def _is_vendor_dump(payload: IdeContextIn) -> bool:
    path = (payload.file.path or "").replace("\\", "/")
    return any(part in _VENDOR_SEGMENTS for part in path.split("/") if part)


def _is_secrets_only(payload: IdeContextIn) -> bool:
    blob = _text_blob(payload)
    if REDACTED not in blob:
        return False
    leftover = blob.replace(REDACTED, "")
    useful = re.sub(r"[\W_]+", "", leftover, flags=re.ASCII)
    return blob.count(REDACTED) >= 1 and len(useful) < _SECRETS_ONLY_USEFUL_CHARS


def _has_pair_context(payload: IdeContextIn) -> bool:
    selection = ""
    if payload.file.selection and payload.file.selection.text:
        selection = payload.file.selection.text.strip()
    content = (payload.file.content or "").strip()
    prompt = (payload.prompt or "").strip()
    if payload.intent == "ask":
        return bool(prompt or selection or content or payload.diagnostics)
    if payload.intent == "share_selection":
        return bool(selection)
    return bool(content or payload.diagnostics)


def _over_budget(payload: IdeContextIn) -> bool:
    content = payload.file.content or ""
    selection = ""
    if payload.file.selection and payload.file.selection.text:
        selection = payload.file.selection.text
    return (
        len(content) > SUMMARIZE_CONTENT_CHARS
        or len(selection) > SUMMARIZE_SELECTION_CHARS
    )


def _should_wake(payload: IdeContextIn) -> bool:
    """Webhook is a wake-up; mailbox is the audit log."""
    if payload.intent == "ask":
        return True
    if any(item.severity == "error" for item in payload.diagnostics):
        return True
    if payload.intent == "share_file_diagnostics" and payload.diagnostics:
        return True
    return False


def _channels(*, forward: bool, wake: bool, webhook_configured: bool) -> tuple[str, ...]:
    if not forward:
        return ()
    chosen: list[str] = ["mailbox"]
    if webhook_configured and wake:
        chosen.append("webhook")
    return tuple(chosen)


def decide(
    payload: IdeContextIn, *, webhook_configured: bool = False
) -> PolicyDecision:
    """Decide whether to forward, summarize, and which outbound channel to use.

    Rules (first match wins for drops):

    1. Drop binary-ish payloads, lockfiles, vendor/VCS dumps, secrets-only
       leftovers, or empty pair context.
    2. Summarize when file content or selection exceeds the char budget.
    3. Channels: mailbox on every forward; webhook only when configured and
       the event is wake-worthy (ask, errors, or file+diagnostics).
    """
    if _is_binary_ish(payload):
        return PolicyDecision(
            forward=False,
            summarize=False,
            channels=(),
            reason=(
                "drop: binary-ish payload (null bytes, high control-char "
                "ratio, or binary extension)"
            ),
            mode="drop",
        )
    if _is_lockfile(payload):
        name = _basename(payload.file.path)
        return PolicyDecision(
            forward=False,
            summarize=False,
            channels=(),
            reason=f"drop: lockfile dump ({name})",
            mode="drop",
        )
    if _is_vendor_dump(payload):
        return PolicyDecision(
            forward=False,
            summarize=False,
            channels=(),
            reason="drop: vendor or VCS dump (node_modules / .git)",
            mode="drop",
        )
    if _is_secrets_only(payload):
        return PolicyDecision(
            forward=False,
            summarize=False,
            channels=(),
            reason=(
                "drop: secrets-only after redaction; no remaining "
                "pair-programming context"
            ),
            mode="drop",
        )
    if not _has_pair_context(payload):
        return PolicyDecision(
            forward=False,
            summarize=False,
            channels=(),
            reason="drop: no selection, file, prompt, or diagnostics to pair on",
            mode="drop",
        )

    summarize = _over_budget(payload)
    channels = _channels(
        forward=True,
        wake=_should_wake(payload),
        webhook_configured=webhook_configured,
    )
    if summarize:
        return PolicyDecision(
            forward=True,
            summarize=True,
            channels=channels,
            reason=(
                "summarize: selection or file exceeds char budget; "
                "forward signature extraction (not a generated answer)"
            ),
            mode="summarize",
        )
    return PolicyDecision(
        forward=True,
        summarize=False,
        channels=channels,
        reason=(
            f"allow: {payload.intent} with source and/or diagnostics "
            "(raw after redaction)"
        ),
        mode="allow",
    )


def default_m1_decision(*, webhook_configured: bool) -> PolicyDecision:
    """Conservative fallback if decide() is unavailable."""
    channels: list[str] = ["mailbox"]
    if webhook_configured:
        channels.append("webhook")
    return PolicyDecision(
        forward=True,
        summarize=False,
        channels=tuple(channels),
        reason=(
            "decide() not implemented; conservative M1 default "
            "(redact + forward, no summarization, no generated answer)"
        ),
        mode="m1-default",
    )


def resolve_decision(
    payload: IdeContextIn, *, webhook_configured: bool
) -> PolicyDecision:
    """Call decide(); fall back only if it still raises NotImplementedError."""
    try:
        return decide(payload, webhook_configured=webhook_configured)
    except NotImplementedError:
        return default_m1_decision(webhook_configured=webhook_configured)
