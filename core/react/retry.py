"""Exponential backoff retry for infrastructure failures."""

import time

import requests.exceptions

from core.logging_setup import log


def with_retries(fn, *, max_attempts=3, base_delay=5.0, label=""):
    """Call fn(), retry on infra failures with exponential backoff."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except (RuntimeError, requests.exceptions.RequestException) as e:
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log.warning("retry.backoff", label=label, attempt=attempt,
                        delay=delay, error=str(e)[:200])
            time.sleep(delay)
