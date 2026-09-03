#!/usr/bin/env python3
# scripts/run_real_task.py
"""Execute a genuine end-to-end Kernel task and output machine-verifiable evidence."""

import os
import sys
import time
import json
from pathlib import Path

# Force mock planner provider for local offline deterministic execution
os.environ["AGENTCORE_PLANNER_PROVIDER"] = "mock"

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.kernel.kernel import Kernel


def main():
    print("=== Kernel Real-Task Validation ===")
    t0 = time.time()
    kernel = Kernel(project_id="cuu-gioi")

    goal = "Inspect cuu-gioi architecture and verify documents"
    result = kernel.run(goal=goal, project_id="cuu-gioi")

    elapsed = time.time() - t0
    print(f"Execution duration: {elapsed:.3f}s")
    print(f"Run ID    : {result.run_id}")
    print(f"Goal      : {result.goal}")
    print(f"Status    : {result.status}")
    print(f"Phase     : {result.phase}")
    print(f"Success   : {result.success}")
    print(f"LLM Calls : {result.llm_calls}")
    print(f"Errors    : {result.errors}")

    ctx = kernel.get_run(result.run_id)
    if ctx:
        print("\n--- Machine-Verifiable Evidence Artifact ---")
        evidence_artifact = {
            "run_id": ctx.run_id,
            "goal": ctx.goal,
            "project_id": ctx.project_id,
            "kernel_status": ctx.kernel_status,
            "kernel_phase": ctx.kernel_phase,
            "started_at": ctx.started_at,
            "finished_at": ctx.finished_at,
            "llm_calls": ctx.llm_calls,
            "knowledge_retrieved": ctx.knowledge_retrieved,
            "errors": ctx.errors,
            "verification_result": "PASS" if result.success else "FAIL",
        }
        print(json.dumps(evidence_artifact, indent=2))

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
