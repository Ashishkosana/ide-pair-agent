# pair-bridge

Local FastAPI process that sits between a VS Code extension and an external
desktop assistant.

`decide()` in `src/pair_bridge/agent/policy.py` applies deterministic
allow / drop / summarize / channel rules. This process does not generate
coding answers and is not a Cursor or Grok product.

See the repository root README for architecture, honesty constraints, and
the extension + bridge demo.
