"""Routing / allow / summarize policy.

This module is the portfolio hook. M1 ships a conservative default and an
intentional NotImplementedError. It does **not** generate coding answers.
"""

from __future__ import annotations

from dataclasses import dataclass

from pair_bridge.models import IdeContextIn

YOU_IMPLEMENT_STEPS = """
YOU IMPLEMENT: pair_bridge.agent.policy.decide

This function is intentionally unfinished. Do not replace it with a
hard-coded fake LLM answer or a canned "I am an AI pair programmer" string.

Implement these steps:

1. Allow / drop
   - Drop if the payload is secrets-only, a lockfile dump, or binary-ish.
   - Allow normal pair-programming context (source + diagnostics + question).

2. Summarize vs raw
   - If selection/file exceeds a token/char budget, summarize.
   - You own the summarizer (a model you control, or signature extraction).
   - M1 must not invent a summary. Until you implement this, send raw
     (after redaction) or drop.

3. Channel selection
   - mailbox: local JSONL audit log for an assistant to tail.
   - webhook: wake a user-configured desktop assistant / automation.
   - Choose one or both. Do not embed vendor-specific Bot APIs here.

4. Never generate the assistant's coding answer in this process.
   The bridge forwards context and later accepts a reply. It is not the brain.

Until this is implemented, resolve_decision() catches NotImplementedError
and uses default_m1_decision(): redact (elsewhere) + forward to mailbox,
and webhook if ASSISTANT_WEBHOOK_URL is set.
"""


@dataclass(frozen=True)
class PolicyDecision:
    forward: bool
    summarize: bool
    channels: tuple[str, ...]
    reason: str
    mode: str


def decide(payload: IdeContextIn) -> PolicyDecision:
    """Decide whether to forward, summarize, and which outbound channel to use.

    Raises:
        NotImplementedError: intentional M1 marker. See YOU_IMPLEMENT_STEPS.
    """
    del payload  # unused until you implement this
    raise NotImplementedError(YOU_IMPLEMENT_STEPS)


def default_m1_decision(*, webhook_configured: bool) -> PolicyDecision:
    """Conservative default used while decide() is unimplemented."""
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
    """Call decide(); fall back to the M1 default when it is not implemented."""
    try:
        return decide(payload)
    except NotImplementedError:
        return default_m1_decision(webhook_configured=webhook_configured)
