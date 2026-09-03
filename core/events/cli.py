#!/usr/bin/env python3
# core/events/cli.py
"""Live Activity Console CLI v1.1.

Usage:
    python -m core.events.cli history <run_id> [--limit <n>]
    python -m core.events.cli live <run_id>          # follow mode
    python -m core.events.cli events [--run-id <id>] [--limit <n>]
    python -m core.events.cli stats
"""

import argparse
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.events.bus import get_bus
from core.events.schema import AgentEvent, EventPhase, EventStatus


PHASE_WIDTH = 10
STATUS_WIDTH = 5


def fmt_event(ev: AgentEvent) -> str:
    """Format one event as a console line."""
    ts = ev.short_ts()
    phase = ev.phase.ljust(PHASE_WIDTH)
    status = ev.status.ljust(STATUS_WIDTH)
    action = ev.action[:55] if ev.action else ""
    msg = ev.message[:30] if ev.message else ""
    return f"[{ts}] {phase} {status} {action}  {msg}"


def cmd_history(args):
    bus = get_bus()
    evs = bus.events(run_id=args.run_id, limit=args.limit or 0)
    if not evs:
        print(f"Không có event nào cho run: {args.run_id}")
        return 0 if args.run_id else 1
    for ev in evs:
        print(fmt_event(ev))
    print(f"\n{len(evs)} event(s)")
    return 0


def cmd_live(args):
    """Follow mode: poll for new events."""
    bus = get_bus()
    seen = set()
    print(f"Following run: {args.run_id}")
    print("Ctrl+C để dừng.\n")
    while True:
        evs = bus.events(run_id=args.run_id)
        for ev in evs:
            if ev.event_id not in seen:
                seen.add(ev.event_id)
                print(fmt_event(ev))
        time.sleep(0.5)


def cmd_events(args):
    bus = get_bus()
    evs = bus.events(run_id=args.run_id, limit=args.limit or 50)
    if not evs:
        print("Không có event nào.")
        return 0
    for ev in evs:
        print(fmt_event(ev))
    print(f"\n{len(evs)} event(s)")
    return 0


def cmd_stats(args):
    bus = get_bus()
    s = bus.stats()
    print(f"Events in buffer : {bus.count()}")
    print(f"Total published  : {s.published}")
    print(f"Subscribers      : {s.subscribers}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.events.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hist = sub.add_parser("history", help="Lịch sử event của một run")
    p_hist.add_argument("run_id")
    p_hist.add_argument("--limit", type=int)
    p_hist.set_defaults(func=cmd_history)

    p_live = sub.add_parser("live", help="Follow event stream cho một run")
    p_live.add_argument("run_id")
    p_live.set_defaults(func=cmd_live)

    p_ev = sub.add_parser("events", help="Liệt kê events")
    p_ev.add_argument("--run-id", dest="run_id")
    p_ev.add_argument("--limit", type=int)
    p_ev.set_defaults(func=cmd_events)

    sub.add_parser("stats", help="Event bus stats").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except KeyboardInterrupt:
        print("\nĐã dừng.")
        sys.exit(0)


if __name__ == "__main__":
    main()
