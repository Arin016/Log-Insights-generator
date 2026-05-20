"""Kiro ACP (Agent Client Protocol) session client.

Manages a stateful conversation with Kiro via the `kiro-cli acp` subprocess.
Uses JSON-RPC 2.0 over stdin/stdout for multi-turn interaction where the LLM
retains full context across turns naturally.

Protocol (discovered empirically):
  1. Spawn `kiro-cli acp`
  2. Send `initialize` → get capabilities
  3. Send `session/new` with {cwd, mcpServers: []} → get sessionId
  4. Send `session/prompt` with {sessionId, prompt: [{type:"text", text:"..."}]}
     → stream session/update (agent_message_chunk) until result with stopReason
  5. Repeat step 4 for each turn
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from typing import Any

from config import KIRO_BINARY, KIRO_MODEL, PROJECT_ROOT
from core.analyzers.base import LLMBackend, LLMResponse
from core.logging_setup import log
from core.persistence.local_store import log_llm_call


class KiroAcpSession(LLMBackend):
    """A stateful ACP session wrapping a long-running kiro-cli acp subprocess."""

    def __init__(self, rak_id: str, use_case: str, model: str | None = None):
        self.rak_id = rak_id
        self.use_case = use_case
        self.model = model or KIRO_MODEL
        self._proc: subprocess.Popen | None = None
        self._session_id: str | None = None
        self._request_id = 0

    # ─── Lifecycle ──────────────────────────────────────────────────────

    def start(self) -> None:
        self._proc = subprocess.Popen(
            [KIRO_BINARY, "acp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
        )
        self._initialize()
        self._create_session()
        log.info("acp.session_started", rak_id=self.rak_id, use_case=self.use_case,
                 session_id=self._session_id)

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        self._proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    # ─── LLMBackend properties ──────────────────────────────────────────

    @property
    def supports_native_tool_use(self) -> bool:
        return False

    @property
    def supports_checkpointing(self) -> bool:
        return False

    # ─── Public API ─────────────────────────────────────────────────────

    def send_message(self, content: str, *, purpose: str = "", timeout: float = 60) -> LLMResponse:
        """Send a message and return the full assistant response."""
        start = time.time()
        request_id = self._next_id()

        msg = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "session/prompt",
            "params": {
                "sessionId": self._session_id,
                "prompt": [{"type": "text", "text": content}],
            },
        }
        self._send(msg)
        response_text = self._collect_response(timeout=timeout)
        latency_ms = int((time.time() - start) * 1000)

        log_llm_call(
            rak_id=self.rak_id,
            purpose=purpose or f"react.{self.use_case}",
            request={"session_id": self._session_id, "content": content[:500]},
            response={"text": response_text[:2000]},
            latency_ms=latency_ms,
            cost_usd=None,
            extras={"use_case": self.use_case, "model": self.model},
        )

        log.info("acp.turn_complete", rak_id=self.rak_id, use_case=self.use_case,
                 latency_ms=latency_ms, response_len=len(response_text))
        return LLMResponse(text=response_text)

    # ─── Internal Protocol ──────────────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, msg: dict) -> None:
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _read_all(self, wait: float = 3) -> bytes:
        data = b""
        end = time.time() + wait
        while time.time() < end:
            ready, _, _ = select.select([self._proc.stdout], [], [], 0.3)
            if ready:
                chunk = os.read(self._proc.stdout.fileno(), 8192)
                if chunk:
                    data += chunk
                else:
                    break
        return data

    def _collect_response(self, timeout: float = 60) -> str:
        """Read messages until stopReason received, accumulating text chunks."""
        chunks: list[str] = []
        end_time = time.time() + timeout

        buffer = b""
        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            ready, _, _ = select.select([self._proc.stdout], [], [], min(0.5, remaining))
            if not ready:
                if self._proc.poll() is not None:
                    raise RuntimeError("ACP subprocess died unexpectedly")
                continue

            chunk = os.read(self._proc.stdout.fileno(), 8192)
            if not chunk:
                raise RuntimeError("ACP subprocess closed stdout")
            buffer += chunk

            # Process complete lines
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line_str = line.decode().strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                # Check for response (end of turn)
                if "result" in msg and "id" in msg:
                    return "".join(chunks)

                # Check for error
                if "error" in msg and "id" in msg:
                    raise RuntimeError(f"ACP error: {msg['error']}")

                # Process notifications
                method = msg.get("method", "")
                params = msg.get("params", {})

                if method == "session/update":
                    update = params.get("update", {})
                    session_update = update.get("sessionUpdate", "")
                    if session_update == "agent_message_chunk":
                        content = update.get("content", {})
                        if isinstance(content, dict) and content.get("type") == "text":
                            chunks.append(content.get("text", ""))

        raise RuntimeError(f"ACP response timeout after {timeout}s")

    def _initialize(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "ff_insights", "version": "0.1.0"},
                "protocolVersion": "2025-01-01",
            },
        }
        self._send(msg)
        time.sleep(1)
        resp_data = self._read_all(3)
        if not resp_data:
            raise RuntimeError("ACP initialize: no response")
        # Parse first JSON line
        for line in resp_data.decode().split("\n"):
            if line.strip():
                try:
                    resp = json.loads(line)
                    if "error" in resp:
                        raise RuntimeError(f"ACP initialize failed: {resp['error']}")
                    return
                except json.JSONDecodeError:
                    continue

    def _create_session(self) -> None:
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "session/new",
            "params": {
                "cwd": str(PROJECT_ROOT),
                "mcpServers": [],
            },
        }
        self._send(msg)
        time.sleep(3)
        resp_data = self._read_all(5)
        if not resp_data:
            raise RuntimeError("ACP session/new: no response")

        for line in resp_data.decode().split("\n"):
            if line.strip():
                try:
                    resp = json.loads(line)
                    if "result" in resp and "sessionId" in resp.get("result", {}):
                        self._session_id = resp["result"]["sessionId"]
                        return
                except json.JSONDecodeError:
                    continue

        if not self._session_id:
            raise RuntimeError(f"ACP session/new: no sessionId in response")
