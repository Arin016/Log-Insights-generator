"""Abstract LLM backend interface.

Both kiro (subprocess) and http (Anthropic API) backends implement this.
The ReAct runner codes against this interface, never against a concrete backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standardized response from any LLM backend."""
    text: str
    raw: Any = None  # backend-specific payload (tool_use blocks, stop_reason, etc.)


class LLMBackend(ABC):
    """Contract for LLM communication backends."""

    @abstractmethod
    def start(self) -> None:
        """Initialize the backend (spawn subprocess, open HTTP session, etc.)."""

    @abstractmethod
    def close(self) -> None:
        """Tear down the backend."""

    @abstractmethod
    def send_message(self, content: str, *, purpose: str = "", timeout: float = 60) -> LLMResponse:
        """Send a message and return the assistant's response."""

    @property
    @abstractmethod
    def supports_native_tool_use(self) -> bool:
        """True if the backend handles tool_use natively (HTTP/Anthropic).
        False if tools are simulated via text protocol (kiro)."""

    @property
    @abstractmethod
    def supports_checkpointing(self) -> bool:
        """True if conversation state can be externally reconstructed.
        HTTP backends: yes (we hold the message list).
        Subprocess backends: no (state lives in the process memory)."""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
