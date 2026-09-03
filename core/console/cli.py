#!/usr/bin/env python3
# core/console/cli.py
"""Live Activity Console CLI — starts the HTTP server + optionally runs an agent.

Usage:
    python -m core.console.cli                   # start server only
    python -m core.console.cli --run "goal"      # start server + run agent
    python -m core.console.cli --run "goal" --no-browser  # server only
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.console.api import LiveActivityServer
from core.console.adapter import patch_runtime_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
log = logging.getLogger(__name__)


def run_agent(goal: str, project_id: str) -> None:
    """Run a single agent goal with event emission."""
    from core.events.bus import reset_bus
    from core.runtime.engine import RuntimeEngine

    reset_bus()
    patch_runtime_engine()

    log.info("Starting agent run: goal=%r project=%s", goal, project_id)
    engine = RuntimeEngine()
    state = engine.run(project_id, goal)
    log.info("Agent run done: status=%s phase=%s", state.status.value, state.phase.value)


def main():
    parser = argparse.ArgumentParser(prog="python -m core.console.cli")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--run", dest="goal", default=None,
                        help="Run a goal after starting server")
    parser.add_argument("--project", default="agent-core")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't open browser")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Patch RuntimeEngine to emit events
    patch_runtime_engine()

    server = LiveActivityServer(host=args.host, port=args.port)

    # Start server in background thread
    server.start()

    # Open browser
    if not args.no_browser:
        def _open():
            time.sleep(0.8)
            webbrowser.open(server.url)
        threading.Thread(target=_open, daemon=True).start()

    print(f"┌─────────────────────────────────────────────┐")
    print(f"│  agent-core Live Console v1.1              │")
    print(f"├─────────────────────────────────────────────┤")
    print(f"│  Server : {server.url:<36}│")
    print(f"│  API    : {server.url}api/runs              │")
    print(f"└─────────────────────────────────────────────┘")
    print()
    print("Open browser at:", server.url)
    print("Press Ctrl+C to stop.")

    # Run agent if requested
    if args.goal:
        # Run in same thread so server stays up
        try:
            run_agent(args.goal, args.project)
        except Exception as exc:
            log.error("Agent run failed: %s", exc)

    # Keep server alive until Ctrl+C
    try:
        server.wait()
    except KeyboardInterrupt:
        server.stop()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
