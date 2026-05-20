"""Abstract ReAct runner interface.

Both the custom hardened runner (kiro path) and the LangGraph runner (http path)
implement this. The pipeline calls this interface via the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.contracts import Finding, LogEvent, RAKMetadata


class ReactRunner(ABC):
    """Contract for ReAct orchestration backends."""

    @abstractmethod
    def run(
        self,
        *,
        use_case: str,
        rak_metadata: RAKMetadata,
        scoped_events: list[LogEvent],
        custom_overrides: list[dict],
    ) -> list[Finding]:
        """Run a single ReAct investigation for one use case.

        Returns verified findings (may be empty if no threats detected).
        """
