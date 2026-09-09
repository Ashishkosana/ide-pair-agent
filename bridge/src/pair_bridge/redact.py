"""Secret redaction applied before persist / mailbox / webhook.

This is a stub-plus: regex prefixes, URL userinfo, and a conservative
entropy scanner. It is not a DLP product or a security guarantee.
Never log the pre-redact payload.
"""

from __future__ import annotations

import math
import re
from collections import Counter
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
    ("gitlab_pat", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("huggingface_token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{36,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("xai_key", re.compile(r"\bxai-[A-Za-z0-9]{20,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("openai_sk", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
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

# Demo / docs placeholders that should stay readable.
_ALLOWLIST = frozenset(
    {
        "your-api-key-here",
        "changeme",
        "placeholder",
        "exampletokenvalue",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    }
)

_URL_USERINFO = re.compile(
    r"(?i)(://[^:\s/#]+:)([^@\s/#]+)(@)"
)

_ENV_SECRET_LINE = re.compile(
    r"(?im)^(\s*(?:export\s+)?"
    r"[A-Z][A-Z0-9_]*"
    r"(?:SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY|PRIVATE_KEY|ACCESS_KEY|AUTH)"
    r")=(\S+)$"
)

_ENTROPY_CANDIDATE = re.compile(r"[A-Za-z0-9_\-+=]{32,}")
_HEX_ONLY = re.compile(r"^[0-9a-f]{32,64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)

_MIN_ENTROPY = 4.0
_MIN_CLASSES = 3


def _shannon(text: str) -> float:
    counts = Counter(text)
    length = len(text)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _char_classes(text: str) -> int:
    classes = 0
    if re.search(r"[a-z]", text):
        classes += 1
    if re.search(r"[A-Z]", text):
        classes += 1
    if re.search(r"[0-9]", text):
        classes += 1
    if re.search(r"[_\-+=]", text):
        classes += 1
    return classes


def _looks_high_entropy_secret(token: str) -> bool:
    if token.lower() in _ALLOWLIST:
        return False
    if _UUID.match(token) or _HEX_ONLY.match(token.lower()):
        return False
    if len(token) < 32:
        return False
    if _char_classes(token) < _MIN_CLASSES:
        return False
    return _shannon(token) >= _MIN_ENTROPY


def apply_extra_scanners(text: str) -> tuple[str, list[str]]:
    """Entropy, URL userinfo, and labeled .env values beyond the prefix list."""
    hits: list[str] = []
    out = text

    def _urlinfo(match: re.Match[str]) -> str:
        return f"{match.group(1)}{REDACTED}{match.group(3)}"

    new_out, n = _URL_USERINFO.subn(_urlinfo, out)
    if n:
        hits.append("url_userinfo")
        out = new_out

    def _env(match: re.Match[str]) -> str:
        value = match.group(2)
        if value.lower() in _ALLOWLIST:
            return match.group(0)
        return f"{match.group(1)}={REDACTED}"

    new_out, n = _ENV_SECRET_LINE.subn(_env, out)
    if n:
        hits.append("env_secret_line")
        out = new_out

    def _entropy(match: re.Match[str]) -> str:
        token = match.group(0)
        if _looks_high_entropy_secret(token):
            return REDACTED
        return token

    new_out, n = _ENTROPY_CANDIDATE.subn(_entropy, out)
    if n and new_out != out:
        hits.append("high_entropy")
        out = new_out

    return out, hits


def extra_redaction_rules(text: str) -> str:
    """Additional scanners: URL userinfo, labeled .env lines, entropy tokens."""
    redacted, _hits = apply_extra_scanners(text)
    return redacted


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

    extra_out, extra_hits = apply_extra_scanners(out)
    if extra_hits:
        hits.extend(extra_hits)
        out = extra_out
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
