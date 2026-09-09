"""Deterministic signature / excerpt extraction.

This is not an LLM. It copies lines that already exist in the payload
(imports, defs, a head/tail excerpt). It never invents a coding answer.
"""

from __future__ import annotations

import re

from pair_bridge.models import IdeContextIn

# Over these sizes, decide() sets summarize=True and the bridge replaces
# the oversized field with extract_signatures() output.
SUMMARIZE_CONTENT_CHARS = 8_000
SUMMARIZE_SELECTION_CHARS = 4_000

_MAX_SIGNATURES = 60
_EXCERPT_HEAD_LINES = 20
_EXCERPT_TAIL_LINES = 10
_MINIFIED_HEAD_CHARS = 800
_MINIFIED_TAIL_CHARS = 400

# Structural lines only — must match source text, not paraphrase it.
_SIG = re.compile(
    r"^\s*(?:"
    r"import\b.+"
    r"|from\b.+"
    r"|#include\b.+"
    r"|use\s+.+"
    r"|package\b.+"
    r"|export\b.+"
    r"|def\s+\w+.+"
    r"|class\s+\w+.+"
    r"|interface\s+\w+.+"
    r"|type\s+\w+.+"
    r"|enum\s+\w+.+"
    r"|struct\s+\w+.+"
    r"|fn\s+\w+.+"
    r"|func\s+\w+.+"
    r"|function\s+\w+.+"
    r"|async\s+function\s+\w+.+"
    r"|pub\s+(?:async\s+)?fn\s+\w+.+"
    r"|impl\b.+"
    r"|trait\s+\w+.+"
    r")",
    re.MULTILINE,
)


def extract_signatures(
    text: str,
    *,
    path: str | None = None,
    language_id: str | None = None,
) -> str:
    """Return signatures or a head/tail excerpt. Never invents symbols."""
    n_chars = len(text)
    n_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    where = path or "selection"
    lang = language_id or "unknown"
    header = (
        f"[summarized {where} ({lang}); {n_chars} chars, {n_lines} lines; "
        "signatures/excerpt only — not a generated answer]"
    )

    signatures: list[str] = []
    seen: set[str] = set()
    for match in _SIG.finditer(text):
        line = match.group(0).rstrip()
        if line in seen:
            continue
        seen.add(line)
        signatures.append(line)
        if len(signatures) >= _MAX_SIGNATURES:
            break

    if signatures:
        body = "\n".join(signatures)
        if len(signatures) >= _MAX_SIGNATURES:
            body += "\n…[signature list capped]"
        return f"{header}\n{body}\n"

    raw_lines = text.splitlines()
    if len(raw_lines) <= 30:
        # Few lines but huge (minified / dumped). Copy head and tail only.
        head = text[:_MINIFIED_HEAD_CHARS]
        tail = (
            text[-_MINIFIED_TAIL_CHARS:]
            if len(text) > _MINIFIED_HEAD_CHARS + _MINIFIED_TAIL_CHARS
            else ""
        )
        mid = "\n…\n" if tail else ""
        return f"{header}\n{head}{mid}{tail}\n"

    excerpt = raw_lines[:_EXCERPT_HEAD_LINES] + ["…"] + raw_lines[-_EXCERPT_TAIL_LINES:]
    return f"{header}\n" + "\n".join(excerpt) + "\n"


def summarize_payload(payload: IdeContextIn) -> IdeContextIn:
    """Replace oversized file/selection fields. Prompt and diagnostics stay."""
    data = payload.model_dump()
    file_data = data.get("file") or {}
    path = file_data.get("path")
    language_id = file_data.get("language_id")

    content = file_data.get("content")
    if isinstance(content, str) and len(content) > SUMMARIZE_CONTENT_CHARS:
        file_data["content"] = extract_signatures(
            content, path=path, language_id=language_id
        )

    selection = file_data.get("selection") or {}
    text = selection.get("text")
    if isinstance(text, str) and len(text) > SUMMARIZE_SELECTION_CHARS:
        selection["text"] = extract_signatures(
            text, path=path or "selection", language_id=language_id
        )
        file_data["selection"] = selection

    data["file"] = file_data
    return IdeContextIn.model_validate(data)
