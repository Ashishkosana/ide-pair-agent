from __future__ import annotations

from pair_bridge.agent.summarize import (
    SUMMARIZE_CONTENT_CHARS,
    extract_signatures,
    summarize_payload,
)
from pair_bridge.models import IdeContextIn


def test_extract_signatures_keeps_defs_not_bodies() -> None:
    text = (
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def greet(name: str) -> str:\n"
        "    return f'hello {name}'\n"
        "\n"
        "class Greeter:\n"
        "    def run(self) -> None:\n"
        "        print('hi')\n"
    )
    summary = extract_signatures(text, path="src/app.py", language_id="python")
    assert "summarized src/app.py" in summary
    assert "not a generated answer" in summary
    assert "def greet(name: str) -> str:" in summary
    assert "class Greeter:" in summary
    assert "import os" in summary
    assert "return f'hello {name}'" not in summary
    assert "print('hi')" not in summary


def test_extract_signatures_excerpt_when_no_defs() -> None:
    lines = [f"value_{i} = {i}" for i in range(50)]
    text = "\n".join(lines)
    summary = extract_signatures(text, path="data.txt", language_id="plaintext")
    assert "value_0 = 0" in summary
    assert "value_49 = 49" in summary
    assert "value_25 = 25" not in summary
    assert "\n…\n" in summary or "\n…\n" in summary.replace("\r", "")


def test_extract_signatures_is_deterministic() -> None:
    text = "def foo():\n    return 1\n" * 400
    assert extract_signatures(text) == extract_signatures(text)


def test_summarize_payload_only_rewrites_oversized_fields(make_context) -> None:
    content = "def greet(name):\n    return name\n" + ("x = 1\n" * 2500)
    assert len(content) > SUMMARIZE_CONTENT_CHARS
    payload = IdeContextIn.model_validate(
        make_context(
            intent="share_file_diagnostics",
            prompt="Why unused?",
            file={
                "path": "src/app.py",
                "language_id": "python",
                "content": content,
                "selection": {
                    "text": "print('tiny')\n",
                    "start_line": 1,
                    "end_line": 1,
                },
            },
        )
    )
    summarized = summarize_payload(payload)
    assert summarized.prompt == "Why unused?"
    assert summarized.file.selection is not None
    assert summarized.file.selection.text == "print('tiny')\n"
    assert summarized.file.content is not None
    assert "[summarized" in summarized.file.content
    assert "def greet(name):" in summarized.file.content
    assert summarized.file.content.count("x = 1") < 5
