#!/usr/bin/env python3
# core/experience/cli.py
"""Experience Engine CLI v0.8.

Usage:
    python -m core.experience.cli list [--limit <n>]
    python -m core.experience.cli inspect <run_id>
    python -m core.experience.cli stats
    python -m core.experience.cli lessons [--limit <n>]
    python -m core.experience.cli candidates
    python -m core.experience.cli promote
"""

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.experience.engine import ExperienceEngine


def fmt_exp(exp):
    lines = [
        f"Run ID     : {exp.run_id}",
        f"Goal       : {exp.goal[:60]}",
        f"Project    : {exp.project_id}",
        f"Outcome    : {exp.outcome}",
        f"Action     : {exp.action[:80]}",
        f"Observation: {exp.observation[:80]}",
        f"Duration   : {exp.duration:.2f}s",
        f"LLM calls  : {exp.llm_calls}",
        f"Tokens     : {exp.estimated_tokens}",
        f"Created    : {exp.created_at}",
    ]
    if exp.failure:
        lines.append(f"Failure    : {exp.failure[:60]}")
    if exp.recovery:
        lines.append(f"Recovery   : {exp.recovery[:60]}")
    return "\n".join(lines)


def cmd_list(args):
    engine = ExperienceEngine()
    exps = engine.list_experiences()
    if args.limit:
        exps = exps[-args.limit:]
    if not exps:
        print("Không có experience nào.")
        return 0
    for e in exps:
        status = "SUCCESS" if e.success() else "FAIL"
        print(f"  {e.run_id}  [{status:7}]  {e.goal[:50]:50}  dur={e.duration:.1f}s  llm={e.llm_calls}")
    print(f"\n{len(exps)} experience(s)")
    return 0


def cmd_inspect(args):
    engine = ExperienceEngine()
    exp = engine.get_experience(args.run_id)
    if not exp:
        print(f"Không tìm thấy: {args.run_id}")
        return 1
    print(fmt_exp(exp))
    return 0


def cmd_stats(args):
    engine = ExperienceEngine()
    s = engine.stats()
    print(f"Tổng experiences: {s.total_experiences}")
    print(f"Tổng lessons   : {s.total_lessons}")
    print(f"Tổng candidates  : {s.total_candidates}")
    print(f"Tổng promoted    : {s.total_promoted}")
    print(f"\nMetrics:")
    print(f"  Success rate   : {s.metrics.success_rate:.0%}")
    print(f"  Failure rate   : {s.metrics.failure_rate:.0%}")
    print(f"  Recovery rate  : {s.metrics.recovery_rate:.0%}")
    print(f"  Avg duration   : {s.metrics.avg_duration:.2f}s")
    print(f"  Avg LLM calls  : {s.metrics.avg_llm_calls:.1f}")
    print(f"  Avg tokens     : {s.metrics.avg_tokens:.0f}")
    return 0


def cmd_lessons(args):
    engine = ExperienceEngine()
    exps = engine.list_experiences()
    lessons = engine.extract_lessons(exps)
    if args.limit:
        lessons = lessons[-args.limit:]
    if not lessons:
        print("Không có lesson nào.")
        return 0
    for l in lessons:
        print(f"  {l.lesson_id}  [{l.lesson_type:25}]  conf={l.confidence:.2f}  {l.title[:50]}")
    print(f"\n{len(lessons)} lesson(s)")
    return 0


def cmd_candidates(args):
    engine = ExperienceEngine()
    candidates = engine.get_candidates()
    if not candidates:
        print("Không có candidate nào.")
        return 0
    for c in candidates:
        print(f"  {c.candidate_id}  [{c.status:10}]  conf={c.confidence:.2f}  {c.primitive.concept[:40]}")
    print(f"\n{len(candidates)} candidate(s)")
    return 0


def cmd_promote(args):
    engine = ExperienceEngine()
    results = engine.promote()
    if not results:
        print("Không có gì để promote.")
        return 0
    for r in results:
        status = "✓" if r.promoted else "✗"
        print(f"  {status} {r.candidate_id} → {r.primitive_id}  {r.reason}")
    print(f"\n{len(results)} promotion(s)")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.experience.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Liệt kê experiences").set_defaults(func=cmd_list)
    sub.add_parser("stats", help="Thống kê experiences").set_defaults(func=cmd_stats)
    sub.add_parser("lessons", help="Liệt kê lessons").set_defaults(func=cmd_lessons)
    sub.add_parser("candidates", help="Liệt kê candidates").set_defaults(func=cmd_candidates)
    sub.add_parser("promote", help="Promote candidates").set_defaults(func=cmd_promote)

    p_insp = sub.add_parser("inspect", help="Chi tiết một experience")
    p_insp.add_argument("run_id")
    p_insp.set_defaults(func=cmd_inspect)

    p_list = sub.add_parser("list", help="Liệt kê experiences")
    p_list.add_argument("--limit", type=int)
    p_list.set_defaults(func=cmd_list)

    p_lessons = sub.add_parser("lessons", help="Liệt kê lessons")
    p_lessons.add_argument("--limit", type=int)
    p_lessons.set_defaults(func=cmd_lessons)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()