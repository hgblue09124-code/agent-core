# core/console/api.py
"""Live Activity API — HTTP server exposing EventBus via REST + SSE."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from core.events.bus import get_bus
from core.events.schema import AgentEvent

logger = logging.getLogger(__name__)

# Persistent events file (written by adapter, read by server in separate process)
_EVENTS_PATH = Path("/tmp/agent-core-events.json")

# Shared AgentRuntime singleton for console HTTP server lifecycle
_shared_runtime = None
_runtime_lock = threading.Lock()
_runtime_submit_lock = threading.Lock()
_last_cycle_lock = threading.Lock()
_last_cycle_result = None


def get_shared_runtime():
    """Returns or initializes the shared AgentRuntime instance for the console process."""
    global _shared_runtime
    if _shared_runtime is None:
        with _runtime_lock:
            if _shared_runtime is None:
                from core.capabilities.adapter import CapabilityRegistry
                from core.capabilities.mock_adapter import (
                    MockEchoCapabilityAdapter,
                    MutationCapability,
                )
                from core.runtime.agent_runtime import AgentRuntime
                registry = CapabilityRegistry()
                registry.register(MockEchoCapabilityAdapter())
                registry.register(MutationCapability())
                storage = os.environ.get("AGENTCORE_CONSOLE_STORAGE")
                _shared_runtime = AgentRuntime(
                    storage_dir=storage if storage else None,
                    capabilities=registry,
                )
    return _shared_runtime


def _remember_cycle(result) -> None:
    global _last_cycle_result
    with _last_cycle_lock:
        _last_cycle_result = result


def _cached_cycle():
    with _last_cycle_lock:
        return _last_cycle_result

# ── Directory helpers ─────────────────────────────────────────────────

def _static_dir() -> Path:
    # console/ lives next to core/ (sibling directory)
    base = Path(__file__).resolve().parents[2] / "console"
    return base


# ── SSE client registry ───────────────────────────────────────────────
# SSE clients register as bus subscribers for real-time push.
# Polling is removed; the bus notifies subscribers immediately on publish.

_sse_clients: list["SSEClient"] = []
_sse_lock = threading.Lock()


class SSEClient:
    """An SSE client with its own queue and bus subscriber thread.

    Events from the bus are queued (non-blocking) so the bus thread
    is never blocked. A background thread drains the queue and writes
    to the client socket.
    """

    def __init__(self, handler: BaseHTTPRequestHandler,
                 run_id: Optional[str] = None):
        self.handler = handler
        self.run_id = run_id          # filter: None = all events
        self.alive = True
        self._queue: queue.Queue = queue.Queue(maxsize=200)
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

        # Register as bus subscriber
        bus = get_bus()
        bus.subscribe(self._bus_handler)

    def _bus_handler(self, event: AgentEvent) -> None:
        """Called synchronously by EventBus.publish(). Runs in bus thread.

        Non-blocking: drops event if queue is full rather than blocking
        the bus thread. This keeps publish() latency low.
        """
        if not self.alive:
            bus = get_bus()
            bus.unsubscribe(self._bus_handler)
            return
        # Filter by run_id if specified
        if self.run_id and event.run_id != self.run_id:
            return
        try:
            self._queue.put_nowait(event.to_dict())
        except queue.Full:
            # Drop rather than block the bus thread
            pass

    def _drain(self) -> None:
        """Background thread: write queued events to SSE socket."""
        while self.alive:
            try:
                data = self._queue.get(timeout=1.0)
                self._send(data)
            except queue.Empty:
                continue
            except Exception:
                break
        # Drain remaining
        while True:
            try:
                data = self._queue.get_nowait()
                self._send(data)
            except queue.Empty:
                break
            except Exception:
                break

    def _send(self, data: dict) -> None:
        """Write one SSE data frame to the client."""
        if not self.alive:
            return
        try:
            payload = f"data: {json.dumps(data, default=str)}\n\n"
            self.handler.wfile.write(payload.encode("utf-8"))
            self.handler.wfile.flush()
        except Exception:
            self.alive = False

    def close(self) -> None:
        """Unsubscribe from bus and signal drain thread to stop."""
        if not self.alive:
            return
        self.alive = False
        try:
            bus = get_bus()
            bus.unsubscribe(self._bus_handler)
        except Exception:
            pass
        try:
            self.handler.wfile.close()
        except Exception:
            pass


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
                     extra: Optional[dict] = None,
                     length: Optional[int] = None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods",
                             "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, Cache-Control")
            # Prevent nginx buffering for SSE
            self.send_header("X-Accel-Buffering", "no")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204, length=0)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/agent/submit":
                self._agent_submit()
            elif path == "/api/agent/approve":
                self._agent_approve()
            else:
                self._not_found()
        except Exception as exc:
            logger.exception("API error: %s", exc)
            self._json({"error": str(exc)}, code=500)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/agent/objectives":
                self._list_objectives()
            elif path == "/api/agent/workspace":
                self._agent_workspace()
            elif path == "/api/agent/state":
                self._agent_state()
            elif path == "/api/healthz":
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
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            return
        except Exception as exc:
            logger.exception("API error: %s", exc)
            try:
                self._json({"error": str(exc)}, code=500)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                return

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
        """Server-Sent Events endpoint — real-time push via bus subscription.

        No polling. The SSE client registers as a bus subscriber and receives
        events immediately when RuntimeEngine publishes them.
        """
        self._set_headers(200, "text/event-stream",
                          extra={"Cache-Control": "no-store, no-cache",
                                 "Connection": "keep-alive",
                                 "X-Accel-Buffering": "no"})

        # Create SSE client that subscribes to the bus
        client = SSEClient(self, run_id=run_id)

        # Send current events first (catch-up)
        existing = self._combined_events(run_id=run_id)
        for ev in existing:
            # Queue for the drain thread (non-blocking)
            client._queue.put_nowait(ev.to_dict())

        # Register client for cleanup tracking
        with _sse_lock:
            _sse_clients.append(client)

        # Send a "stream opened" comment so the browser knows it's live
        try:
            self.handler.wfile.write(b": connected\n\n")
            self.handler.wfile.flush()
        except Exception:
            pass

        # Register a done-sender callback via the run result check
        # The drain thread watches for RESULT phase in the stream
        self._sse_wait_for_done(client, run_id)

    def _sse_wait_for_done(self, client: SSEClient, run_id: str) -> None:
        """Wait for RESULT phase then send 'done' and close.

        This runs in the request thread. We poll very infrequently
        (every 5s) just to detect run completion — all real-time delivery
        happens via the bus subscriber queue.
        """
        deadline = time.time() + 3600  # 1h max
        try:
            while client.alive and time.time() < deadline:
                time.sleep(5)
                if not client.alive:
                    break
                # Check if run has RESULT
                evs = self._combined_events(run_id=run_id)
                if evs and evs[-1].phase == "RESULT":
                    try:
                        payload = "data: {\"type\": \"done\"}\n\n"
                        client.handler.wfile.write(payload.encode("utf-8"))
                        client.handler.wfile.flush()
                    except Exception:
                        pass
                    break
        except Exception:
            pass
        finally:
            client.close()
            with _sse_lock:
                if client in _sse_clients:
                    _sse_clients.remove(client)

    # ── Static files ─────────────────────────────────────────────

    def _serve_file(self, name: str):
        p = _static_dir() / name
        if not p.exists():
            self._not_found()
            return
        ext = p.suffix.lower()
        ct_map = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json",
            ".ico": "image/x-icon",
        }
        ct = ct_map.get(ext, "text/plain")
        body = p.read_bytes()
        self._set_headers(200, ct, length=len(body))
        self.wfile.write(body)

    def _serve_static(self, path: str):
        # Security: prevent path traversal
        clean = path.lstrip("/")
        if ".." in clean:
            self._not_found()
            return
        self._serve_file(clean)

    # ── Helpers ──────────────────────────────────────────────────

    def _json(self, data: dict, code: int = 200):
        payload = json.dumps(data, indent=2, default=str).encode("utf-8")
        self._set_headers(code, length=len(payload))
        self.wfile.write(payload)

    def _not_found(self):
        self._json({"error": "Not found"}, code=404)

    def _agent_submit(self):
        try:
            content_len_header = self.headers.get("Content-Length", "0")
            content_len = int(content_len_header) if content_len_header.isdigit() else 0
        except Exception:
            self._json({"error": "Invalid Content-Length header"}, code=400)
            return

        if content_len <= 0:
            self._json({"error": "Empty request body"}, code=400)
            return

        if content_len > 1_000_000:  # 1MB limit for payload
            self._json({"error": "Payload too large"}, code=413)
            return

        try:
            body = self.rfile.read(content_len)
            req_data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json({"error": "Invalid JSON payload"}, code=400)
            return
        except Exception as exc:
            logger.error("Error reading request body: %s", exc)
            self._json({"error": "Failed to read request body"}, code=400)
            return

        if not isinstance(req_data, dict):
            self._json({"error": "Request payload must be a JSON object"}, code=400)
            return

        message = req_data.get("message")
        if not message or not isinstance(message, str):
            self._json({"error": "Field 'message' must be a non-empty string"}, code=400)
            return

        if len(message) > 10_000:
            self._json({"error": "Message length exceeds limit of 10,000 characters"}, code=400)
            return

        user_approved = bool(req_data.get("user_approved", False))

        try:
            runtime = get_shared_runtime()
            with _runtime_submit_lock:
                res = runtime.submit(message, user_approved=user_approved)
            _remember_cycle(res)
            from core.console.presentation import serialize_cycle
            self._json(serialize_cycle(res))
        except Exception as exc:
            logger.exception("AgentRuntime submission error: %s", exc)
            self._json({"error": "Runtime processing failure"}, code=500)

    def _list_objectives(self):
        try:
            runtime = get_shared_runtime()
            objs = runtime.list_objectives()
            self._json({"objectives": [o.to_dict() for o in objs], "total": len(objs)})
        except Exception as exc:
            logger.exception("AgentRuntime list_objectives error: %s", exc)
            self._json({"error": "Failed to list objectives"}, code=500)

    def _read_json_body(self) -> tuple[Optional[dict], Optional[tuple[dict, int]]]:
        """Return (payload, error_response). error_response is (dict, code)."""
        try:
            content_len_header = self.headers.get("Content-Length", "0")
            content_len = int(content_len_header) if content_len_header.isdigit() else 0
        except Exception:
            return None, ({"error": "Invalid Content-Length header"}, 400)

        if content_len <= 0:
            return None, ({"error": "Empty request body"}, 400)
        if content_len > 1_000_000:
            return None, ({"error": "Payload too large"}, 413)

        try:
            body = self.rfile.read(content_len)
            req_data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, ({"error": "Invalid JSON payload"}, 400)
        except Exception as exc:
            logger.error("Error reading request body: %s", exc)
            return None, ({"error": "Failed to read request body"}, 400)

        if not isinstance(req_data, dict):
            return None, ({"error": "Request payload must be a JSON object"}, 400)
        return req_data, None

    def _agent_approve(self):
        req_data, err = self._read_json_body()
        if err is not None:
            self._json(err[0], code=err[1])
            return

        objective_id = req_data.get("objective_id")
        if not objective_id or not isinstance(objective_id, str):
            self._json({"error": "Field 'objective_id' must be a non-empty string"}, code=400)
            return

        try:
            runtime = get_shared_runtime()
            with _runtime_submit_lock:
                res = runtime.approve(objective_id)
            _remember_cycle(res)
            from core.console.presentation import serialize_cycle
            self._json(serialize_cycle(res))
        except Exception as exc:
            logger.exception("AgentRuntime approval error: %s", exc)
            self._json({"error": "Runtime processing failure"}, code=500)

    def _agent_workspace(self):
        try:
            from core.console.presentation import present_workspace
            runtime = get_shared_runtime()
            events = self._combined_events()
            view = present_workspace(
                state=runtime.state,
                objectives=runtime.list_objectives(),
                events=events,
                cycle=_cached_cycle(),
            )
            self._json(view)
        except Exception as exc:
            logger.exception("AgentRuntime workspace error: %s", exc)
            self._json({"error": "Failed to build workspace"}, code=500)

    def _agent_state(self):
        try:
            runtime = get_shared_runtime()
            self._json({"agent_state": runtime.state.to_dict()})
        except Exception as exc:
            logger.exception("AgentRuntime state error: %s", exc)
            self._json({"error": "Failed to read agent state"}, code=500)

    def log_message(self, fmt, *args):
        # Suppress default noise; use logger instead
        pass


# ── Server ────────────────────────────────────────────────────────────

class LiveActivityServer:
    """HTTP API server for Live Activity Console.

    Uses ThreadingHTTPServer so SSE long-lived connections do not block
    other concurrent requests (e.g. healthz, static files).
    """

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
        self._server = ThreadingHTTPServer(
            (self.host, self.port), LiveActivityHandler)
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
        # Close all SSE clients gracefully
        with _sse_lock:
            for client in list(_sse_clients):
                try:
                    client.close()
                except Exception:
                    pass
            _sse_clients.clear()
        logger.info("Live Activity API stopped")

    def wait(self) -> None:
        """Block until the server is stopped."""
        if self._thread:
            self._thread.join()
