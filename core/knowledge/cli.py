#!/usr/bin/env python3
# core/knowledge/cli.py
"""Knowledge Engine CLI v0.7.

Usage:
    python -m core.knowledge.cli list [--domain <d>] [--status <s>]
    python -m core.knowledge.cli search "<query>" [--top-k <n>]
    python -m core.knowledge.cli inspect <prim_id>
    python -m core.knowledge.cli stats
    python -m core.knowledge.cli add --domain <d> --concept <c> --description <desc>
    python -m core.knowledge.cli activate <prim_id> [--evidence-id <eid>]
    python -m core.knowledge.cli relate <src_id> <tgt_id> <type> [--note <n>]
"""

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.knowledge.engine import KnowledgeEngine
from core.knowledge.schema import KnowledgeStatus, SourceType


def fmt_prim(prim):
    lines = [
        f"ID         : {prim.id}",
        f"Domain     : {prim.domain}",
        f"Concept    : {prim.concept}",
        f"Status     : {prim.status}",
        f"Confidence : {prim.confidence:.2f}",
        f"Created    : {prim.created_at}",
        f"Updated    : {prim.updated_at}",
        f"Usage      : {prim.usage_count} (success={prim.success_count}, fail={prim.failure_count})",
        f"Success %  : {prim.success_rate():.0%}",
        f"Provenance : {prim.provenance.source_type} | {prim.provenance.created_by}",
        f"Run        : {prim.provenance.run_id or '—'}",
        f"Evidence   : {len(prim.provenance.evidence_ids)} items",
    ]
    if prim.description:
        lines.append(f"\nDescription: {prim.description}")
    if prim.when_to_use:
        lines.append(f"\nWhen to use: {prim.when_to_use}")
    if prim.implementation_pattern:
        lines.append(f"\nPattern    : {prim.implementation_pattern[:200]}")
    if prim.failure_modes:
        lines.append(f"\nFailure    : {', '.join(prim.failure_modes[:3])}")
    if prim.relations:
        rels = [f"{r.relation_type}→{r.target_id}" for r in prim.relations]
        lines.append(f"\nRelations  : {', '.join(rels)}")
    return "\n".join(lines)


def cmd_list(args):
    engine = KnowledgeEngine()
    prims = engine.list_primitives()
    if args.domain:
        prims = [p for p in prims if p.domain == args.domain]
    if args.status:
        prims = [p for p in prims if p.status == args.status]
    if not prims:
        print("Không tìm thấy primitive nào.")
        return 0
    for p in prims:
        rate = f"{p.success_rate():.0%}" if p.usage_count else "—"
        print(f"  {p.id}  [{p.status:10}] {p.domain:12} {p.concept[:50]:50}  conf={p.confidence:.2f}  rate={rate}")
    print(f"\n{len(prims)} primitive(s)")
    return 0


def cmd_search(args):
    engine = KnowledgeEngine()
    result = engine.retrieve(args.query, top_k=args.top_k or 5)
    if not result.scores:
        print("Không tìm thấy kết quả phù hợp.")
        return 0
    print(f"Tìm thấy {result.candidates_considered} primitive, top {len(result.scores)}:")
    for s in result.scores:
        prim = engine.get_primitive(s.primitive_id)
        if prim:
            print(f"\n  {prim.id}  score={s.score:.3f}  [{prim.status}]  {prim.concept[:60]}")
            for reason in s.reasons[:3]:
                print(f"    → {reason}")
    return 0


def cmd_inspect(args):
    engine = KnowledgeEngine()
    prim = engine.get_primitive(args.prim_id)
    if not prim:
        print(f"Không tìm thấy: {args.prim_id}")
        return 1
    print(fmt_prim(prim))
    return 0


def cmd_stats(args):
    engine = KnowledgeEngine()
    s = engine.stats()
    print(f"Tổng số primitive : {s.total}")
    print("\nTheo trạng thái:")
    for status, count in sorted(s.by_status.items()):
        print(f"  {status:12} : {count}")
    print("\nTheo domain:")
    for domain, count in sorted(s.by_domain.items()):
        print(f"  {domain:20} : {count}")
    return 0


def cmd_add(args):
    engine = KnowledgeEngine()
    prim = engine.create_primitive(
        domain=args.domain,
        concept=args.concept,
        description=args.description,
        when_to_use=getattr(args, "when_to_use", ""),
        implementation_pattern=getattr(args, "pattern", ""),
        verification_method=getattr(args, "verification", ""),
        examples=getattr(args, "examples", None),
        source_type=SourceType.MANUAL.value,
        created_by="cli",
    )
    print(f"Đã tạo: {prim.id}  [{prim.status}]")
    return 0


def cmd_activate(args):
    engine = KnowledgeEngine()
    prim = engine.get_primitive(args.prim_id)
    if not prim:
        print(f"Không tìm thấy: {args.prim_id}")
        return 1
    try:
        evidence_ids = [args.evidence_id] if args.evidence_id else []
        prim, record = engine.activate_primitive(prim, evidence_ids, reason="CLI activation")
        print(f"Đã kích hoạt: {prim.id}  [{prim.status}]")
    except Exception as e:
        print(f"Lỗi: {e}")
        return 1
    return 0


def cmd_relate(args):
    engine = KnowledgeEngine()
    engine.add_relation(args.src_id, args.tgt_id, args.rel_type, note=args.note or "")
    print(f"Đã thêm quan hệ: {args.src_id} --{args.rel_type}--> {args.tgt_id}")
    return 0


def main():
    parser = argparse.ArgumentParser(prog="python -m core.knowledge.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="Liệt kê primitives")
    p_list.add_argument("--domain", help="Lọc theo domain")
    p_list.add_argument("--status", help="Lọc theo status")
    p_list.set_defaults(func=cmd_list)

    # search
    p_search = sub.add_parser("search", help="Tìm kiếm primitive")
    p_search.add_argument("query", help="Query string")
    p_search.add_argument("--top-k", type=int, help="Số kết quả")
    p_search.set_defaults(func=cmd_search)

    # inspect
    p_insp = sub.add_parser("inspect", help="Chi tiết một primitive")
    p_insp.add_argument("prim_id", help="Primitive ID")
    p_insp.set_defaults(func=cmd_inspect)

    # stats
    sub.add_parser("stats", help="Thống kê knowledge base").set_defaults(func=cmd_stats)

    # add
    p_add = sub.add_parser("add", help="Tạo primitive mới")
    p_add.add_argument("--domain", required=True)
    p_add.add_argument("--concept", required=True)
    p_add.add_argument("--description", required=True)
    p_add.add_argument("--when-to-use", dest="when_to_use")
    p_add.add_argument("--pattern")
    p_add.add_argument("--verification")
    p_add.add_argument("--examples", nargs="*")
    p_add.set_defaults(func=cmd_add)

    # activate
    p_act = sub.add_parser("activate", help="Kích hoạt primitive lên ACTIVE")
    p_act.add_argument("prim_id")
    p_act.add_argument("--evidence-id", dest="evidence_id")
    p_act.set_defaults(func=cmd_activate)

    # relate
    p_rel = sub.add_parser("relate", help="Thêm quan hệ giữa 2 primitive")
    p_rel.add_argument("src_id")
    p_rel.add_argument("tgt_id")
    p_rel.add_argument("rel_type")
    p_rel.add_argument("--note")
    p_rel.set_defaults(func=cmd_relate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
