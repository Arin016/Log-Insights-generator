"""Conservative canary/phrase detectors supplement (never replace) capability isolation."""
import re


PATTERNS = (r"ignore\s+previous", r"ignore\s+(?:the\s+)?(?:deadline|output schema)",
    r"hide\s+(?:all\s+)?bank", r"send\s+credentials", r"synthetic_canary", r"repeat tool calls forever",
    r"another tenant", r"override the scope", r"system:\s*accuse", r"<script>")


def detect(events):
    # Joining neighboring fields catches the frozen split-instruction challenge;
    # it is deliberately not described as a general injection recognizer.
    text=" ".join(e.text for e in sorted(events,key=lambda e:(e.occurred_at,e.event_id))).lower()
    return tuple(pattern for pattern in PATTERNS if re.search(pattern,text))
