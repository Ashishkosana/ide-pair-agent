from __future__ import annotations

import pytest

from pair_bridge.models import IdeContextIn
from pair_bridge.redact import extra_redaction_rules, redact_context, redact_text


def test_redact_openai_and_assignment() -> None:
    text, hits = redact_text("token=sk-abcdefghijklmnopqrstuvwxyz1234")
    assert "[REDACTED]" in text
    assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in text
    assert hits


def test_redact_github_pat() -> None:
    text, hits = redact_text("export GH=ghp_abcdefghijklmnopqrstuvwxyz0123")
    assert "ghp_" not in text
    assert "github_pat" in hits


def test_redact_context_before_outbound(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            prompt="do not leak api_key=supersecretvalue",
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": None,
                "selection": {
                    "text": "API_KEY = 'sk-abcdefghijklmnopqrstuvwxyz9999'\n",
                    "start_line": 1,
                    "end_line": 1,
                },
            },
        )
    )
    redacted, hits = redact_context(payload)
    dumped = redacted.model_dump()
    blob = str(dumped)
    assert "supersecretvalue" not in blob
    assert "sk-abcdefghijklmnopqrstuvwxyz9999" not in blob
    assert "[REDACTED]" in blob
    assert hits


def test_extra_redaction_rules_are_you_implement() -> None:
    with pytest.raises(NotImplementedError, match="YOU IMPLEMENT"):
        extra_redaction_rules("anything")
