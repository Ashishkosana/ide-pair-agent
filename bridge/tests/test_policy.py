from __future__ import annotations

from pair_bridge.agent.policy import (
    decide,
    default_m1_decision,
    resolve_decision,
)
from pair_bridge.models import IdeContextIn
from pair_bridge.redact import REDACTED


def test_decide_allows_normal_selection(make_context) -> None:
    payload = IdeContextIn.model_validate(make_context())
    decision = decide(payload, webhook_configured=False)
    assert decision.forward is True
    assert decision.summarize is False
    assert decision.mode == "allow"
    assert decision.channels == ("mailbox",)
    assert "allow:" in decision.reason


def test_decide_drops_lockfile(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            file={
                "path": "frontend/package-lock.json",
                "language_id": "json",
                "content": '{"packages": {"a": {"version": "1.0.0"}}}\n',
                "selection": None,
            },
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"
    assert decision.forward is False
    assert decision.channels == ()
    assert "lockfile" in decision.reason


def test_decide_drops_binary_extension(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            file={
                "path": "assets/logo.png",
                "language_id": None,
                "content": "\x00\x01\x02\x03not-really-png",
                "selection": None,
            },
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"
    assert "binary" in decision.reason


def test_decide_drops_null_bytes(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            file={
                "path": "src/blob.dat",
                "language_id": None,
                "content": None,
                "selection": {
                    "text": "abc\x00\x00\x00def",
                    "start_line": 1,
                    "end_line": 1,
                },
            }
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"


def test_decide_drops_vendor_dump(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            file={
                "path": "node_modules/leftpad/index.js",
                "language_id": "javascript",
                "content": "module.exports = function leftpad() {}\n",
                "selection": None,
            },
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"
    assert "vendor" in decision.reason


def test_decide_drops_secrets_only(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            prompt=None,
            diagnostics=[],
            file={
                "path": ".env",
                "language_id": "dotenv",
                "content": f"API_KEY = {REDACTED}\nTOKEN = {REDACTED}\n",
                "selection": None,
            },
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"
    assert "secrets-only" in decision.reason


def test_decide_allows_source_with_redacted_secret(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": (
                    f"API_KEY = {REDACTED}\n\n"
                    "def greet(name: str) -> str:\n"
                    "    return f'hello {name}'\n"
                ),
                "selection": None,
            },
            intent="share_file_diagnostics",
        )
    )
    decision = decide(payload)
    assert decision.forward is True
    assert decision.mode == "allow"


def test_decide_drops_empty_share_selection(make_context) -> None:
    payload = IdeContextIn.model_validate(
        make_context(
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": None,
                "selection": {"text": "", "start_line": 1, "end_line": 1},
            }
        )
    )
    decision = decide(payload)
    assert decision.mode == "drop"
    assert "no selection" in decision.reason


def test_decide_summarizes_large_file(make_context) -> None:
    content = "def greet(name):\n    return name\n" + ("x = 1\n" * 2500)
    payload = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": content,
                "selection": None,
            },
        )
    )
    decision = decide(payload)
    assert decision.forward is True
    assert decision.summarize is True
    assert decision.mode == "summarize"
    assert "mailbox" in decision.channels


def test_decide_webhook_only_when_configured_and_wakeable(make_context) -> None:
    quiet = IdeContextIn.model_validate(make_context())
    asked = IdeContextIn.model_validate(
        make_context(intent="ask", prompt="Why is this unused?")
    )
    errors = IdeContextIn.model_validate(
        make_context(
            diagnostics=[
                {
                    "severity": "error",
                    "message": "Undefined name",
                    "source": "pyright",
                    "start_line": 1,
                    "end_line": 1,
                }
            ]
        )
    )
    file_diags = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": "def greet(name):\n    return name\n",
                "selection": None,
            },
            diagnostics=[
                {
                    "severity": "warning",
                    "message": "Missing return type",
                    "source": "pyright",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
        )
    )

    assert decide(quiet, webhook_configured=True).channels == ("mailbox",)
    assert decide(asked, webhook_configured=False).channels == ("mailbox",)
    assert decide(asked, webhook_configured=True).channels == ("mailbox", "webhook")
    assert decide(errors, webhook_configured=True).channels == ("mailbox", "webhook")
    assert decide(file_diags, webhook_configured=True).channels == (
        "mailbox",
        "webhook",
    )


def test_decide_is_deterministic(make_context) -> None:
    payload = IdeContextIn.model_validate(make_context(intent="ask", prompt="Explain"))
    first = decide(payload, webhook_configured=True)
    second = decide(payload, webhook_configured=True)
    assert first == second


def test_default_m1_includes_webhook_only_when_configured() -> None:
    with_hook = default_m1_decision(webhook_configured=True)
    without = default_m1_decision(webhook_configured=False)
    assert with_hook.channels == ("mailbox", "webhook")
    assert without.channels == ("mailbox",)
    assert with_hook.summarize is False
    assert with_hook.mode == "m1-default"


def test_resolve_uses_implemented_decide(make_context) -> None:
    payload = IdeContextIn.model_validate(make_context())
    decision = resolve_decision(payload, webhook_configured=False)
    assert decision.mode == "allow"
    assert decision.forward is True
    assert decision.channels == ("mailbox",)
