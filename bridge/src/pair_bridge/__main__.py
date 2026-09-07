"""`python -m pair_bridge` entrypoint."""

from __future__ import annotations

import uvicorn

from pair_bridge.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "pair_bridge.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
