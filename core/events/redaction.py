# core/events/redaction.py
"""Secret redaction for AgentEvent.

Before an event is published, all secret-like content is replaced
with [REDACTED]. This is the LAST line of defense against secrets
leaking into event logs and history.
"""

from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS = [
    # API keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
    re.compile(r"xoxp-[A-Za-z0-9-]{20,}"),
    # Generic credential patterns
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[=:]\s*['\"]?([^\s'\",;}\]]+)"),
    # Authorization header
    re.compile(r"(?i)Authorization:\s*Bearer\s+[A-Za-z0-9\-_.=]+"),
    re.compile(r"(?i)Authorization:\s*Basic\s+[A-Za-z0-9+/=]+"),
    # Bootstrap / private key blocks
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    # Long base64-ish strings (>= 40 chars, only base64 chars)
    re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/=]{40,}(?![A-Za-z0-9+/=])"),
]

# Replace with this placeholder
REDACTED = "[REDACTED]"


def scrub_string(text: str) -> str:
    """Scrub all secret-like content from a string."""
    if not text:
        return text
    result = text
    for pat in _SECRET_PATTERNS:
        result = pat.sub(REDACTED, result)
    return result


def _is_sensitive_key(key: str) -> bool:
    """Check if a dict key looks sensitive."""
    k = key.lower()
    return any(s in k for s in (
        "api_key", "apikey", "secret", "password", "passwd", "pwd",
        "token", "authorization", "credential", "private_key",
    ))


def scrub_metadata(meta: Any) -> Any:
    """Recursively scrub metadata dict."""
    if isinstance(meta, dict):
        out: dict = {}
        for k, v in meta.items():
            if _is_sensitive_key(str(k)):
                out[k] = REDACTED
            else:
                out[k] = scrub_metadata(v)
        return out
    if isinstance(meta, list):
        return [scrub_metadata(x) for x in meta]
    if isinstance(meta, str):
        return scrub_string(meta)
    return meta


def redact_event(event) -> "AgentEvent":
    """Redact an AgentEvent in place (returns it)."""
    event.action = scrub_string(event.action)
    event.message = scrub_string(event.message)
    event.task_id = scrub_string(event.task_id)
    event.metadata = scrub_metadata(event.metadata)
    return event


def contains_secret(text: str) -> bool:
    """Check if text contains any secret-like pattern."""
    if not text:
        return False
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False
