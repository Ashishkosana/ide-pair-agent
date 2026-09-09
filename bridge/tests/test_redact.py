from __future__ import annotations

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


def test_extra_redaction_rules_do_not_raise() -> None:
    assert extra_redaction_rules("hello world") == "hello world"


def test_redact_jwt() -> None:
    jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFBP7HGdR-U"
    )
    text, hits = redact_text(f"Authorization: Bearer {jwt}")
    assert jwt not in text
    assert "jwt" in hits or "bearer_header" in hits


def test_redact_gitlab_pat() -> None:
    text, hits = redact_text("export GL=glpat-abcdefghijklmnopqrstuvwxyz0123")
    assert "glpat-" not in text
    assert "gitlab_pat" in hits


def test_redact_url_userinfo() -> None:
    text, hits = redact_text("postgres://alice:s3cr3tpass@localhost/app")
    assert "s3cr3tpass" not in text
    assert "[REDACTED]" in text
    assert "url_userinfo" in hits


def test_redact_high_entropy_token() -> None:
    token = "xK9mP2nQ7vR4sT8wY1zA3bC5dE0fH6jL"
    text, hits = redact_text(f"orphan token sitting here {token} in source")
    assert token not in text
    assert "high_entropy" in hits


def test_redact_skips_git_sha() -> None:
    sha = "a" * 40
    text, hits = redact_text(f"commit {sha} on main")
    assert sha in text
    assert "high_entropy" not in hits


def test_extra_rules_allowlist_placeholder() -> None:
    assert "your-api-key-here" in extra_redaction_rules("key=your-api-key-here")
