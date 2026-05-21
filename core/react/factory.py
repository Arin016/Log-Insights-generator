"""Factory that returns the correct ReAct runner based on LLM_BACKEND config."""

from config import LLM_BACKEND


def get_react_runner():
    """Return the correct run function based on LLM_BACKEND.

    All returned functions have the same signature:
        fn(use_case, rak_metadata, scoped_events, custom_overrides) → list[Finding]
    """

    if LLM_BACKEND == "kiro":
        from core.analyzers.acp_client import KiroAcpSession
        from core.react.react_runner import run_react_session

        def runner(**kwargs):
            return run_react_session(backend_cls=KiroAcpSession, **kwargs)
        return runner

    elif LLM_BACKEND == "http":
        from core.analyzers.http_client import SaviyntHttpBackend
        from core.react.react_runner import run_react_session

        def runner(**kwargs):
            return run_react_session(backend_cls=SaviyntHttpBackend, **kwargs)
        return runner

    elif LLM_BACKEND == "bedrock":
        # Future: LangGraph runner with native tool_use
        # from core.react.langgraph_runner import run_react_session
        raise NotImplementedError(
            "LLM_BACKEND='bedrock' requires LangGraph runner (not yet implemented). "
            "Use 'kiro' or 'http' for now."
        )

    else:
        raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND!r}. Use 'kiro', 'http', or 'bedrock'.")
