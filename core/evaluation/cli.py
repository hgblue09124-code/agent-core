#!/usr/bin/env python3
# core/evaluation/cli.py
"""Evaluation Engine CLI v0.9.

Usage:
    python -m core.evaluation.cli evaluate <target_id> [--evidence-id <id>]
    python -m core.evaluation.cli evidence list [--type <t>]
    python -m core.evaluation.cli candidates
    python -m core.evaluation.cli benchmark
    python -m core.evaluation.cli stats
"""

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.evaluation.engine import EvaluationEngine


def cmd_evaluate(args):
    engine = EvaluationEngine()
    if args.evidence_id:
        ev = engine.get_evidence(args.evidence_id)
        if not ev:
            print(f"Không tìm thấy: {args.evidence_id}")
            return 1
        ev_list = [ev]
    else:
        ev_list = engine.list_evidence()

    ev = engine.evaluate(args.target_id, ev_list, "GOAL_ACHIEVED")
    print(f"Evaluation: {ev.evaluation_id}")
    print(f"Target    : {ev.target_id}")
    print(f"Achievement: {ev.achievement}")
    print(f"Verdict  : {ev.verdict}")
    print(f"Score    : {ev.total_score():.3f}")
    if ev.failed_criteria:
        print(f"Failed   : {', '.join(ev.failed_criteria)}")
    if ev.warnings:
        print(f"Warnings : {', '.join(ev.warnings)}")
    return 0


def cmd_evidence(args):
    engine = EvaluationEngine()
    ev_list = engine.list_evidence(evidence_type=args.type)
    if not ev_list:
        print("Không có evidence nào.")
        return 0
    for e in ev_list:
        status = "PASS" if e.is_pass() else "FAIL"
        print(f"  {e.evidence_id}  [{e.type:15}]  {status:4}  {e.source[:40]}")
    print(f"\n{len(ev_list)} evidence")
    return 0


def cmd_candidates(args):
    engine = EvaluationEngine()
    cands = engine.list_candidates()
    if not cands:
        print("Không có candidate nào.")
        return 0
    for c in cands:
        print(f"  {c.candidate_id}  [{c.verdict:10}]  {c.target}  {c.hypothesis[:40]}")
    print(f"\n{len(cands)} candidate(s)")
    return 0


def cmd_benchmark(args):
    engine = EvaluationEngine()
    print("Chạy benchmarks...")
    report = engine.run_benchmarks()
    print(report.summary())
    return 0


def cmd_stats(args):
    engine = EvaluationEngine()
    s = engine.stats()
    print(f"Tổng evidence     : {s.total_evaluations}")
    print(f"Candidates        : {s.improvement_candidates}")
    print(f"  Đã accept       : {s.improvements_accepted}")
    print(f"  Đã reject       : {s.improvements_rejected}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.evaluation.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_eval = sub.add_parser("evaluate", help="Đánh giá một target")
    p_eval.add_argument("target_id")
    p_eval.add_argument("--evidence-id", dest="evidence_id")
    p_eval.set_defaults(func=cmd_evaluate)

    p_ev = sub.add_parser("evidence", help="Liệt kê evidence")
    p_ev.add_argument("--type", dest="type")
    p_ev.set_defaults(func=cmd_evidence)

    sub.add_parser("candidates", help="Liệt kê candidates").set_defaults(func=cmd_candidates)
    sub.add_parser("benchmark", help="Chạy benchmark").set_defaults(func=cmd_benchmark)
    sub.add_parser("stats", help="Thống kê").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
