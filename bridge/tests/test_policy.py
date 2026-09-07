from __future__ import annotations

import pytest

from pair_bridge.agent.policy import (
    decide,
    default_m1_decision,
    resolve_decision,
)
from pair_bridge.models import IdeContextIn


def test_decide_raises_you_implement(make_context) -> None:
    payload = IdeContextIn.model_validate(make_context())
    with pytest.raises(NotImplementedError, match="YOU IMPLEMENT"):
        decide(payload)


def test_default_m1_includes_webhook_only_when_configured() -> None:
    with_hook = default_m1_decision(webhook_configured=True)
    without = default_m1_decision(webhook_configured=False)
    assert with_hook.channels == ("mailbox", "webhook")
    assert without.channels == ("mailbox",)
    assert with_hook.summarize is False
    assert with_hook.mode == "m1-default"


def test_resolve_falls_back_to_default(make_context) -> None:
    payload = IdeContextIn.model_validate(make_context())
    decision = resolve_decision(payload, webhook_configured=False)
    assert decision.mode == "m1-default"
    assert decision.forward is True
