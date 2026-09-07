"""Secret redaction applied before persist / mailbox / webhook.

M1 is a simple regex stub. It is not a security guarantee.
"""

from __future__ import annotations

import re
from typing import Any

from pair_bridge.models import IdeContextIn

REDACTED = "[REDACTED]"

# Order matters: more specific provider prefixes first.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "pem_private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_sk", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "assignment_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization)"
            r"(\s*[:=]\s*)['\"]?[^\s'\"]{8,}['\"]?"
        ),
    ),
    (
        "bearer_header",
        re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([A-Za-z0-9._\-+/=]{8,})"),
    ),
]


# YOU IMPLEMENT: stronger secret detection
#
# Current M1 uses simple regexes. Improve redact_text() / extra_redaction_rules()
# without logging the pre-redact payload. Suggested steps:
# 1. Shannon-entropy / high-randomness token detection for unlabeled secrets.
# 2. Keep a small, reviewed list of prefixes you actually encounter; rotate it.
# 3. Walk structured JSON / .env / YAML values, not just blob regex.
# 4. Decide whether markdown / test fixtures should be scanned the same way.
# 5. Add allowlists for known-public example strings so demos stay readable.
#
# Do not claim this module makes outbound payloads "safe."


def extra_redaction_rules(text: str) -> str:
    """YOU IMPLEMENT: additional scanners beyond the M1 regex list."""
    raise NotImplementedError(
        "YOU IMPLEMENT: extra_redaction_rules — entropy, structured .env/YAML "
        "walk, and reviewed prefix lists. See redact.py comments. M1 does not "
        "call this on the hot path."
    )


def redact_text(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, rule names that fired)."""
    hits: list[str] = []
    out = text
    for name, pattern in _RULES:
        if name == "bearer_header":

            def _bearer(match: re.Match[str]) -> str:
                return f"{match.group(1)}{REDACTED}"

            new_out, n = pattern.subn(_bearer, out)
        elif name == "assignment_secret":

            def _assign(match: re.Match[str]) -> str:
                return f"{match.group(1)}{match.group(2)}{REDACTED}"

            new_out, n = pattern.subn(_assign, out)
        else:
            new_out, n = pattern.subn(REDACTED, out)
        if n:
            hits.append(name)
            out = new_out
    return out, hits


def _walk(value: Any, hits: list[str]) -> Any:
    if isinstance(value, str):
        redacted, found = redact_text(value)
        hits.extend(found)
        return redacted
    if isinstance(value, list):
        return [_walk(item, hits) for item in value]
    if isinstance(value, dict):
        return {key: _walk(item, hits) for key, item in value.items()}
    return value


def redact_context(payload: IdeContextIn) -> tuple[IdeContextIn, list[str]]:
    """Deep-copy and redact string fields. Never mutate the caller's model."""
    hits: list[str] = []
    data = _walk(payload.model_dump(), hits)
    unique = list(dict.fromkeys(hits))
    return IdeContextIn.model_validate(data), unique
