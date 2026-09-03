# core/events/bus.py
"""Event Bus — pub/sub for AgentEvent.

Design:
    - Bounded in-memory buffer (configurable max_events)
    - Subscriber isolation: one bad subscriber does not kill others
    - Non-blocking publish: subscriber exceptions are caught and logged
    - No secrets stored
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

from core.events.schema import AgentEvent, new_event
from core.events.redaction import redact_event

logger = logging.getLogger(__name__)


# Default max events to retain in memory
DEFAULT_MAX_EVENTS = 1000


@dataclass
class BusStats:
    published: int = 0
    dropped: int = 0
    subscribers: int = 0


Handler = Callable[[AgentEvent], None]


class EventBus:
    """Lightweight pub/sub event bus for kernel events.

    Thread-safe. Bounded buffer. Subscriber isolation.

    Usage:
        bus = EventBus()
        bus.subscribe(my_handler)
        bus.publish(event)
        bus.unsubscribe(my_handler)
    """

    def __init__(self, max_events: int = DEFAULT_MAX_EVENTS):
        self._max = max_events
        self._buffer: deque[AgentEvent] = deque(maxlen=max_events)
        self._handlers: list[Handler] = []
        self._lock = threading.RLock()
        self._stats = BusStats()

    # ── Publish ──────────────────────────────────────────────────────

    def publish(self, event: AgentEvent) -> None:
        """Publish an event. Safe to call from any thread.

        Before publishing, all secret content is redacted.
        Subscriber exceptions are caught and logged, never propagated.
        """
        # Redact secrets FIRST
        redact_event(event)

        with self._lock:
            self._buffer.append(event)
            self._stats.published += 1

        # Notify subscribers (outside the lock to avoid deadlock)
        # Each handler is called in its own try/except
        for handler in self._get_handlers_snapshot():
            self._safe_notify(handler, event)

    # ── Subscribe / unsubscribe ─────────────────────────────────────

    def subscribe(self, handler: Handler) -> None:
        """Register a handler. Idempotent."""
        with self._lock:
            if handler not in self._handlers:
                self._handlers.append(handler)
                self._stats.subscribers = len(self._handlers)

    def unsubscribe(self, handler: Handler) -> None:
        """Unregister a handler. Idempotent."""
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
                self._stats.subscribers = len(self._handlers)

    # ── Query ──────────────────────────────────────────────────────

    def events(self, run_id: Optional[str] = None,
               phase: Optional[str] = None,
               limit: int = 0) -> list[AgentEvent]:
        """Return events from buffer, optionally filtered."""
        with self._lock:
            evs = list(self._buffer)
        if run_id:
            evs = [e for e in evs if e.run_id == run_id]
        if phase:
            evs = [e for e in evs if e.phase == phase]
        if limit > 0:
            evs = evs[-limit:]
        return evs

    def get(self, event_id: str) -> Optional[AgentEvent]:
        """Get a specific event by id."""
        with self._lock:
            for e in self._buffer:
                if e.event_id == event_id:
                    return e
        return None

    def last(self, run_id: Optional[str] = None) -> Optional[AgentEvent]:
        """Return the most recent event, optionally filtered by run_id."""
        evs = self.events(run_id=run_id)
        return evs[-1] if evs else None

    def count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def stats(self) -> BusStats:
        with self._lock:
            return BusStats(
                published=self._stats.published,
                dropped=0,
                subscribers=len(self._handlers),
            )

    # ── Persistence ────────────────────────────────────────────────

    def save_to_file(self, path: str) -> None:
        """Persist events to a JSON file (for history)."""
        import json, os
        with self._lock:
            data = [e.to_dict() for e in self._buffer]
        p = __import__("pathlib").Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)

    def load_from_file(self, path: str) -> int:
        """Load events from a JSON file. Returns count loaded."""
        import json
        p = __import__("pathlib").Path(path)
        if not p.exists():
            return 0
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for d in data:
                    ev = AgentEvent.from_dict(d)
                    if len(self._buffer) < self._max:
                        self._buffer.append(ev)
            return len(data)
        except (json.JSONDecodeError, OSError, KeyError):
            return 0

    # ── Internals ─────────────────────────────────────────────────

    def _get_handlers_snapshot(self) -> list[Handler]:
        with self._lock:
            return list(self._handlers)

    def _safe_notify(self, handler: Handler, event: AgentEvent) -> None:
        """Call handler, catching all exceptions."""
        try:
            handler(event)
        except Exception:
            # Never propagate subscriber exceptions
            logger.warning(
                "EventBus subscriber raised: %s",
                __import__("traceback").format_exc(),
            )


# ── Global bus ──────────────────────────────────────────────────────

# The global bus is shared across all kernel runs.
# Import this from other modules.
_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_bus() -> EventBus:
    """Get or create the global event bus."""
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = EventBus()
        return _bus


def reset_bus() -> None:
    """Reset the global bus (for tests)."""
    global _bus
    with _bus_lock:
        _bus = EventBus()
