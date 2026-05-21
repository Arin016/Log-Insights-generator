"""Saviynt AI Platform HTTP backend — text-in/text-out over HTTP.

Talks to Saviynt's /agent/llm_chat endpoint which wraps AWS Bedrock.
Server manages session state. No native tool_use support.
"""

from __future__ import annotations

import time

import requests

from config import (
    LLM_HTTP_BASE_URL, LLM_HTTP_AUTH_URL,
    LLM_HTTP_USERNAME, LLM_HTTP_PASSWORD,
)
from core.analyzers.base import LLMBackend, LLMResponse
from core.logging_setup import log
from core.persistence.local_store import log_llm_call


class SaviyntHttpBackend(LLMBackend):
    """Saviynt AI Platform chat endpoint — text-in/text-out over HTTP."""

    def __init__(self, rak_id: str, use_case: str):
        self.rak_id = rak_id
        self.use_case = use_case
        self._token: str | None = None
        self._token_expires_at: float = 0
        self._session_id = f"{rak_id}__{use_case}"

    def start(self) -> None:
        self._authenticate()

    def close(self) -> None:
        self._token = None

    @property
    def supports_native_tool_use(self) -> bool:
        return False

    @property
    def supports_checkpointing(self) -> bool:
        return False

    def send_message(self, content: str, *, purpose: str = "", timeout: float = 60) -> LLMResponse:
        self._ensure_token()
        start = time.time()

        resp = requests.post(
            f"{LLM_HTTP_BASE_URL}/api/v1/agent/llm_chat",
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            json={"query": content, "session_id": self._session_id, "user_id": "ff_insights"},
            timeout=timeout,
        )
        resp.raise_for_status()
        response_text = resp.json().get("content", "")

        latency_ms = int((time.time() - start) * 1000)
        log_llm_call(
            rak_id=self.rak_id,
            purpose=purpose or f"react.{self.use_case}",
            request={"content": content[:500]},
            response={"text": response_text[:2000]},
            latency_ms=latency_ms,
            cost_usd=None,
            extras={"use_case": self.use_case, "backend": "saviynt_http"},
        )

        return LLMResponse(text=response_text)

    def _authenticate(self) -> None:
        resp = requests.post(
            LLM_HTTP_AUTH_URL,
            json={"username": LLM_HTTP_USERNAME, "password": LLM_HTTP_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 1800) - 60

    def _ensure_token(self) -> None:
        if time.time() >= self._token_expires_at:
            self._authenticate()
