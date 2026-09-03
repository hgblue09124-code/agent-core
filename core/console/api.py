# core/console/api.py
"""Live Activity API — HTTP server exposing EventBus via REST + SSE."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from core.events.bus import get_bus
from core.events.schema import AgentEvent

logger = logging.getLogger(__name__)

# Persistent events file (written by adapter, read by server in separate process)
_EVENTS_PATH = Path("/tmp/agent-core-events.json")

# ── Directory helpers ─────────────────────────────────────────────────

def _static_dir() -> Path:
    # console/ lives next to core/ (sibling directory)
    base = Path(__file__).resolve().parents[2] / "console"
    return base


# ── SSE client registry ───────────────────────────────────────────────

_sse_clients: list["SSEClient"] = []
_sse_lock = threading.Lock()


class SSEClient:
    def __init__(self, handler: BaseHTTPRequestHandler):
        self.handler = handler
        self.alive = True

    def send(self, event_data: dict) -> None:
        if not self.alive:
            return
        try:
            payload = f"data: {json.dumps(event_data, default=str)}\n\n"
            self.handler.wfile.write(payload.encode("utf-8"))
            self.handler.wfile.flush()
        except Exception:
            self.alive = False

    def close(self) -> None:
        self.alive = False


# ── Router ─────────────────────────────────────────────────────────────

class LiveActivityHandler(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"
    _bus = None  # set via class-level property

    @classmethod
    def get_bus(cls):
        # Always use the current global bus, not a cached reference.
        # This ensures tests that reset the bus work correctly.
        return get_bus()

    @staticmethod
    def _load_persisted_events() -> list[AgentEvent]:
        """Load events from persistent file (for cross-process)."""
        if not _EVENTS_PATH.exists():
            return []
        try:
            with open(_EVENTS_PATH, "r") as f:
                data = json.load(f)
            return [AgentEvent.from_dict(d) for d in data]
        except (json.JSONDecodeError, OSError, KeyError):
            return []

    @classmethod
    def _combined_events(cls, run_id: Optional[str] = None,
                         phase: Optional[str] = None) -> list[AgentEvent]:
        """Get events from in-memory bus + persisted file."""
        # In-memory bus events
        bus = cls.get_bus()
        evs = bus.events(run_id=run_id, phase=phase)
        seen_ids = {e.event_id for e in evs}
        # Persisted file events
        for pev in cls._load_persisted_events():
            if pev.event_id not in seen_ids:
                if run_id and pev.run_id != run_id:
                    continue
                if phase and pev.phase != phase:
                    continue
                evs.append(pev)
                seen_ids.add(pev.event_id)
        evs.sort(key=lambda e: e.timestamp)
        return evs

    def _set_headers(self, code: int = 200,
                     content_type: str = "application/json",
                     cors: bool = True,
                     extra: Optional[dict] = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods",
                             "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, Cache-Control")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/healthz":
                self._health()
            elif path == "/api/runs":
                self._list_runs()
            elif path.startswith("/api/runs/"):
                parts = path.split("/")
                if len(parts) == 5 and parts[4] == "events":
                    run_id = parts[3]
                    limit = int(qs.get("limit", [100])[0])
                    self._run_events(run_id, limit)
                elif len(parts) == 5 and parts[4] == "stream":
                    run_id = parts[3]
                    self._stream(run_id)
                elif len(parts) == 5 and parts[4] == "result":
                    run_id = parts[3]
                    self._run_result(run_id)
                elif len(parts) == 4:
                    run_id = parts[3]
                    self._run_info(run_id)
                else:
                    self._not_found()
            elif path == "/" or path == "/index.html":
                self._serve_file("index.html")
            elif path.startswith("/"):
                self._serve_static(path)
            else:
                self._not_found()
        except Exception as exc:
            logger.exception("API error: %s", exc)
            self._json({"error": str(exc)}, code=500)

    # ── Endpoints ─────────────────────────────────────────────────

    def _health(self):
        bus = self.get_bus()
        self._json({
            "status": "ok",
            "events_in_buffer": bus.count(),
            "subscribers": bus.stats().subscribers,
            "uptime": "ok",
        })

    def _list_runs(self):
        evs = self._combined_events()
        # Collect unique run_ids + last event per run
        run_map: dict[str, dict] = {}
        for ev in reversed(evs):
            if ev.run_id not in run_map:
                run_map[ev.run_id] = {
                    "run_id": ev.run_id,
                    "phase": ev.phase,
                    "status": ev.status,
                    "message": ev.action,
                    "timestamp": ev.timestamp,
                    "event_count": 0,
                }
            run_map[ev.run_id]["event_count"] += 1
        runs = sorted(run_map.values(),
                      key=lambda r: r["timestamp"], reverse=True)
        self._json({"runs": list(runs), "total": len(runs)})

    def _run_info(self, run_id: str):
        evs = self._combined_events(run_id=run_id)
        if not evs:
            self._json({"error": f"Run not found: {run_id}"}, code=404)
            return
        meta = {
            "run_id": run_id,
            "phase": evs[-1].phase,
            "status": evs[-1].status,
            "event_count": len(evs),
            "first_event": evs[0].to_dict() if evs else None,
            "last_event": evs[-1].to_dict(),
        }
        self._json(meta)

    def _run_events(self, run_id: str, limit: int = 100):
        evs = self._combined_events(run_id=run_id)
        if limit > 0:
            evs = evs[-limit:]
        self._json({
            "run_id": run_id,
            "events": [e.to_dict() for e in evs],
            "count": len(evs),
        })

    def _run_result(self, run_id: str):
        evs = self._combined_events(run_id=run_id)
        if not evs:
            self._json({"error": f"Run not found: {run_id}"}, code=404)
            return

        # Build result summary from events
        result_ev = None
        for ev in reversed(evs):
            if ev.phase == "RESULT":
                result_ev = ev
                break

        tasks = [e for e in evs if e.phase == "EXECUTE"]
        verify_evs = [e for e in evs if e.phase == "VERIFY"]
        pass_count = sum(1 for e in verify_evs if e.status == "PASS")
        total_duration = sum(e.duration for e in evs if e.duration)
        meta = result_ev.metadata if result_ev else {}

        self._json({
            "run_id": run_id,
            "status": result_ev.status if result_ev else evs[-1].status,
            "phase": result_ev.phase if result_ev else evs[-1].phase,
            "message": result_ev.action if result_ev else "",
            "verification": {
                "verified": meta.get("run_status") == "COMPLETED",
                "pass_count": pass_count,
                "total_checks": len(verify_evs),
            },
            "metrics": {
                "llm_calls": meta.get("llm_calls", 0),
                "estimated_tokens": meta.get("estimated_tokens", 0),
                "completed_tasks": meta.get("completed_tasks", len([e for e in tasks if e.status == "PASS"])),
                "failed_tasks": meta.get("failed_tasks", len([e for e in tasks if e.status == "FAIL"])),
            },
            "duration_seconds": round(total_duration, 3),
            "event_count": len(evs),
            "has_evidence": len([e for e in evs if e.metadata]) > 0,
        })

    def _stream(self, run_id: str):
        """Server-Sent Events endpoint for live updates."""
        self._set_headers(200, "text/event-stream",
                          extra={"Cache-Control": "no-cache",
                                 "Connection": "keep-alive"})

        client = SSEClient(self)

        # Send current events first (catch-up)
        existing = self._combined_events(run_id=run_id)
        for ev in existing:
            client.send(ev.to_dict())

        with _sse_lock:
            _sse_clients.append(client)

        self._sse_loop(client, run_id)

    def _sse_loop(self, client: SSEClient, run_id: str):
        """Poll for new events and send them to the client."""
        last_run_count = len(self._combined_events(run_id=run_id))
        last_result_sent = False
        loop_deadline = time.time() + 60

        try:
            while client.alive and time.time() < loop_deadline:
                time.sleep(0.3)
                current = self._combined_events(run_id=run_id)
                if len(current) > last_run_count:
                    for ev in current[last_run_count:]:
                        client.send(ev.to_dict())
                    last_run_count = len(current)
                if current and current[-1].phase == "RESULT" and not last_result_sent:
                    time.sleep(0.3)
                    if client.alive:
                        client.send({"type": "done"})
                    last_result_sent = True
                    break
        except Exception:
            pass
        finally:
            with _sse_lock:
                if client in _sse_clients:
                    _sse_clients.remove(client)
            try:
                client.handler.wfile.close()
            except Exception:
                pass

    # ── Static files ─────────────────────────────────────────────

    def _serve_file(self, name: str):
        p = _static_dir() / name
        if not p.exists():
            self._not_found()
            return
        ext = p.suffix.lower()
        ct_map = {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".ico": "image/x-icon",
        }
        ct = ct_map.get(ext, "text/plain")
        self._set_headers(200, ct)
        with open(p, "rb") as f:
            self.wfile.write(f.read())

    def _serve_static(self, path: str):
        # Security: prevent path traversal
        clean = path.lstrip("/")
        if ".." in clean:
            self._not_found()
            return
        self._serve_file(clean)

    # ── Helpers ──────────────────────────────────────────────────

    def _json(self, data: dict, code: int = 200):
        self._set_headers(code)
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def _not_found(self):
        self._json({"error": "Not found"}, code=404)

    def log_message(self, fmt, *args):
        # Suppress default noise; use logger instead
        pass


# ── Server ────────────────────────────────────────────────────────────

class LiveActivityServer:
    """HTTP API server for Live Activity Console."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def start(self) -> None:
        if self._running:
            return
        self._server = HTTPServer((self.host, self.port), LiveActivityHandler)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("Live Activity API started at %s", self.url)

    def _serve(self):
        assert self._server is not None
        try:
            self._server.serve_forever()
        except Exception:
            pass

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        self._running = False
        logger.info("Live Activity API stopped")

    def wait(self) -> None:
        """Block until the server is stopped."""
        if self._thread:
            self._thread.join()
