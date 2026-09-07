"""Runtime settings. Localhost-first; webhook is opt-in."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8765
    mailbox_dir: str = "mailbox"
    assistant_webhook_url: str | None = None
    webhook_timeout_seconds: float = 5.0
    max_payload_chars: int = 200_000

    @property
    def webhook_configured(self) -> bool:
        return bool(self.assistant_webhook_url and self.assistant_webhook_url.strip())
