"""Optional outbound webhook. URL is user-configured; no vendor API is assumed."""

from __future__ import annotations

from typing import Any

import httpx


class WebhookAdapter:
    def __init__(
        self,
        url: str | None,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.url = (url or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self._client = client

    def send(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if not self.url:
            return {"attempted": False, "ok": True, "skipped": True}

        # YOU IMPLEMENT: webhook authenticity
        # 1. Sign the body with HMAC-SHA256 using a local secret.
        # 2. Send X-Pair-Agent-Signature / timestamp headers the receiver checks.
        # 3. Do not invent a vendor-specific auth scheme here.
        headers = {
            "Content-Type": "application/json",
            "X-Pair-Agent-Event": "ide.context",
        }
        try:
            if self._client is not None:
                response = self._client.post(
                    self.url, json=envelope, headers=headers
                )
            else:
                response = httpx.post(
                    self.url,
                    json=envelope,
                    timeout=self.timeout_seconds,
                    headers=headers,
                )
            return {
                "attempted": True,
                "ok": response.is_success,
                "skipped": False,
                "status_code": response.status_code,
            }
        except httpx.HTTPError as exc:
            return {
                "attempted": True,
                "ok": False,
                "skipped": False,
                "error": exc.__class__.__name__,
            }
