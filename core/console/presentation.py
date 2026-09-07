# core/console/presentation.py
"""Presentation mapper — Runtime models → User UI view-model.

Runtime remains the brain. This module is the only place user-facing copy
lives. The View must not branch on Agent Loop phases; it consumes the
dictionaries produced here.

Unknown phases, action types, and event kinds degrade to generic human
language. They never crash and never require a Runtime change.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from core.events.schema import AgentEvent
from core.runtime.models import (
    Action,
    AgentPhase,
    AgentState,
    CycleResult,
    ExecutionResult,
    Objective,
    ObjectiveState,
)


# ── Open registries (not a closed FSM) ────────────────────────────────
# Extra keys may be added as the Runtime grows. Lookups always have a
# fallback. The UI never iterates these maps to decide layout.

PRESENCE_BY_PHASE = {
    AgentPhase.IDLE.value: "ready",
    AgentPhase.COMPLETED.value: "ready",
    AgentPhase.WATCHING.value: "watching",
    AgentPhase.WAITING.value: "waiting",
    AgentPhase.PAUSED.value: "waiting",
    AgentPhase.NEEDS_USER.value: "needs_you",
    AgentPhase.FAILED.value: "error",
}

PRESENCE_LABEL = {
    "ready": "Sẵn sàng",
    "working": "Đang làm việc",
    "watching": "Đang theo dõi",
    "waiting": "Đang chờ",
    "needs_you": "Cần anh xác nhận",
    "error": "Gặp trở ngại",
}

PRESENCE_DETAIL = {
    "ready": "Em đang chờ anh giao việc.",
    "working": "Em đang làm việc cho anh.",
    "watching": "Em đang theo dõi giúp anh.",
    "waiting": "Em đang chờ thêm thông tin.",
    "needs_you": "Anh cần xác nhận trước khi em tiếp tục.",
    "error": "Có vấn đề. Em chưa hoàn thành được.",
}

# Human activity for known phases. Unknown phases use _humanize_token().
PHASE_ACTIVITY = {
    "IDLE": "Em đang chờ anh giao việc.",
    "OBSERVING": "Em đang xem anh vừa gửi gì…",
    "OBSERVE": "Em đang xem anh vừa gửi gì…",
    "UNDERSTANDING": "Em đang hiểu mục tiêu của anh…",
    "RETRIEVING": "Đang tìm lại thông tin liên quan…",
    "RETRIEVE": "Đang tìm lại thông tin liên quan…",
    "KNOWLEDGE": "Đang tìm lại thông tin liên quan…",
    "DECIDING": "Em đang chọn cách làm…",
    "DECIDE": "Em đang chọn cách làm…",
    "PLAN": "Em đang sắp xếp việc cần làm…",
    "PLANNING": "Em đang sắp xếp việc cần làm…",
    "EXECUTING": "Em đang làm việc cho anh…",
    "EXECUTE": "Em đang làm việc cho anh…",
    "ACT": "Em đang làm việc cho anh…",
    "ACTION_STARTED": "Em đang bắt đầu thực hiện…",
    "VERIFYING": "Em đang kiểm tra kết quả…",
    "VERIFY": "Em đang kiểm tra kết quả…",
    "REMEMBERING": "Em đang ghi nhớ để lần sau còn dùng…",
    "EXPERIENCE": "Em đang ghi nhớ để lần sau còn dùng…",
    "WAITING": "Em đang chờ thêm thông tin.",
    "NEEDS_USER": "Anh cần xác nhận trước khi em tiếp tục.",
    "WATCHING": "Em đang theo dõi giúp anh.",
    "WATCH": "Em đang theo dõi giúp anh.",
    "COMPLETED": "Xong rồi.",
    "FINISH": "Xong rồi.",
    "FAILED": "Có vấn đề. Em chưa hoàn thành được.",
    "PAUSED": "Em đang tạm dừng.",
    "RECOVERY": "Em đang gỡ rối để làm lại…",
    "CHECKPOINT": "Em đang lưu tiến độ…",
    "EVALUATION": "Em đang đánh giá kết quả…",
    "RESULT": "Em đã có kết quả.",
    "TASK_STARTED": "Em đã hiểu việc anh giao.",
    "TASK_COMPLETED": "Em đã xong việc này.",
    "TASK_FAILED": "Việc này chưa làm được.",
    "ACTION_COMPLETED": "Em vừa hoàn thành một bước.",
    "MEMORY_UPDATED": "Em đã cập nhật trí nhớ.",
    "TASK_CREATED": "Em đã nhận việc.",
    "PLAN_CREATED": "Em đã sắp xếp các bước.",
    "VERIFICATION_FAILED": "Kết quả chưa đạt. Em đang xem lại.",
}

STAGE_LABEL = {
    "OBSERVE": "Xem yêu cầu",
    "UNDERSTAND": "Hiểu mục tiêu",
    "RETRIEVE": "Tìm thông tin liên quan",
    "DECIDE": "Chọn cách làm",
    "ACT": "Thực hiện",
    "VERIFY": "Kiểm tra kết quả",
    "REMEMBER": "Ghi nhớ",
    "WATCH": "Theo dõi tiếp",
    "FINISH": "Hoàn thành",
}

ACTION_ACTIVITY = {
    "remember": "Đang ghi nhớ thông tin này…",
    "forget": "Đang xóa thông tin theo yêu cầu của anh…",
    "retrieve_memory": "Đang tìm lại thông tin liên quan…",
    "invoke_capability": "Đang thực hiện hành động…",
    "ask_user": "Anh cần xác nhận trước khi em tiếp tục.",
    "wait": "Em đang chờ.",
    "watch": "Em sẽ theo dõi giúp anh.",
    "finish": "Đã hoàn thành.",
    "echo": "Em đang trả lời anh.",
    "none": "Em đang xem xét…",
}

ACTION_DONE = {
    "remember": "Em đã nhớ.",
    "forget": "Em đã quên thông tin đó.",
    "retrieve_memory": "Em đã tìm được thông tin liên quan.",
    "invoke_capability": "Em đã thực hiện xong.",
    "echo": "Em đã trả lời.",
    "watch": "Em sẽ tiếp tục theo dõi.",
    "finish": "Xong rồi.",
    "ask_user": "Em đang chờ anh quyết định.",
}

OBJECTIVE_STATUS_LABEL = {
    ObjectiveState.PENDING.value: "Chưa bắt đầu",
    ObjectiveState.RUNNING.value: "Đang làm",
    ObjectiveState.WAITING.value: "Đang chờ",
    ObjectiveState.COMPLETED.value: "Hoàn thành",
    ObjectiveState.FAILED.value: "Chưa xong",
    ObjectiveState.BLOCKED.value: "Cần xác nhận",
}

_WORKING_SUFFIXES = ("ING",)
_TERMINAL_PRESENCE = {"ready", "error", "needs_you"}


def _as_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict() or {}
        except Exception:
            return {}
    return {}


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _humanize_token(token: str) -> str:
    """Fallback for unknown Runtime tokens. Never raises."""
    raw = str(token or "").strip()
    if not raw:
        return "đang xử lý"
    cleaned = raw.replace("_", " ").replace("-", " ").strip()
    return cleaned.lower()


def classify_presence(phase: str, *, objective_status: str = "", last_outcome: str = "") -> str:
    """Map AgentState.phase → a user-level presence. Open-ended."""
    if _upper(objective_status) == ObjectiveState.BLOCKED.value:
        return "needs_you"
    if _upper(last_outcome) == "FAILED" or _upper(objective_status) == ObjectiveState.FAILED.value:
        if _upper(phase) in {AgentPhase.FAILED.value, ""}:
            return "error"
    mapped = PRESENCE_BY_PHASE.get(_upper(phase))
    if mapped:
        return mapped
    token = _upper(phase)
    if not token:
        return "ready"
    if _upper(last_outcome) == "BLOCKED":
        return "needs_you"
    if _upper(last_outcome) == "FAILED":
        return "error"
    # Unknown phases must not be dropped. Prefer "working" over a blank idle screen.
    return "working"


def activity_headline(
    *,
    phase: str = "",
    action: Optional[Action | dict] = None,
    event: Optional[AgentEvent | dict] = None,
    capability: str = "",
) -> str:
    """Human activity line. Prefers action semantics over raw phase names."""
    action_d = _as_dict(action)
    event_d = _as_dict(event) if not isinstance(event, AgentEvent) else event.to_dict()
    cap = capability or str(action_d.get("capability") or event_d.get("metadata", {}).get("capability") or "")
    action_type = _lower(action_d.get("type"))

    if _upper(phase) == AgentPhase.NEEDS_USER.value or action_type == "ask_user":
        return PHASE_ACTIVITY["NEEDS_USER"]

    cap_l = cap.lower()
    if "mutation" in cap_l or "config" in cap_l:
        return "Đang cập nhật cấu hình Agent Core…"

    if action_type and action_type in ACTION_ACTIVITY:
        return ACTION_ACTIVITY[action_type]

    phase_key = _upper(phase) or _upper(event_d.get("phase"))
    if phase_key in PHASE_ACTIVITY:
        return PHASE_ACTIVITY[phase_key]

    event_action = str(event_d.get("action") or event_d.get("message") or "").strip()
    if event_action and not event_action.isupper() and "→" not in event_action:
        # Already a sentence from Runtime; keep it if it reads human.
        if " " in event_action and len(event_action) < 180:
            return event_action

    if phase_key:
        return f"Đang {_humanize_token(phase_key)}…"
    return "Em đang làm việc cho anh…"


def why_copy(*, decision: Any = None, action: Optional[Action | dict] = None, phase: str = "") -> str:
    decision_d = _as_dict(decision)
    reason = str(decision_d.get("reason") or "").strip()
    if reason and reason not in {"mock", "deterministic"} and not reason.lower().startswith("deterministic"):
        return reason
    action_d = _as_dict(action)
    expected = str(action_d.get("expected_outcome") or "").strip()
    if expected:
        return expected
    if _upper(phase) == AgentPhase.NEEDS_USER.value:
        return "Việc này cần anh cho phép trước khi em làm."
    return ""


def _progress_ratio(stages: Iterable[str], phase: str, presence: str) -> float:
    stage_list = [s for s in (stages or []) if s]
    if presence == "ready" and _upper(phase) in {AgentPhase.IDLE.value, AgentPhase.COMPLETED.value}:
        return 1.0 if stage_list else 0.0
    if presence == "error":
        return 1.0 if stage_list else 0.0
    if not stage_list:
        return 0.15 if presence == "working" else 0.0
    # Canonical user-visible steps, not a hard-coded Runtime requirement.
    expected = ["OBSERVE", "UNDERSTAND", "RETRIEVE", "DECIDE", "ACT", "VERIFY", "REMEMBER", "FINISH"]
    done = {s.upper() for s in stage_list}
    hit = sum(1 for step in expected if step in done)
    if "WATCH" in done and "FINISH" not in done:
        hit += 1
    return min(1.0, max(0.08, hit / float(len(expected))))


def _progress_steps(stages: Iterable[str], phase: str, presence: str) -> list[dict]:
    stage_list = [_upper(s) for s in (stages or []) if s]
    seen: list[str] = []
    for s in stage_list:
        if s not in seen:
            seen.append(s)
    current = _upper(phase)
    steps = []
    for index, key in enumerate(seen):
        label = STAGE_LABEL.get(key, _humanize_token(key).capitalize())
        is_last = index == len(seen) - 1
        active = is_last and presence == "working"
        done = (not active) and (presence in _TERMINAL_PRESENCE or index < len(seen) - 1 or presence != "working")
        if presence == "working" and is_last:
            done = False
            active = True
        steps.append({
            "key": key,
            "label": label,
            "done": done,
            "active": active,
        })
    if not steps and presence == "working":
        steps.append({
            "key": current or "WORKING",
            "label": activity_headline(phase=phase),
            "done": False,
            "active": True,
        })
    return steps


def _format_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, (int, float, bool)):
        return str(output)
    if isinstance(output, dict):
        if output.get("content"):
            return str(output["content"]).strip()
        if output.get("echo"):
            return str(output["echo"]).strip()
        if output.get("forgotten"):
            return f"Đã quên: {output['forgotten']}"
        items = output.get("items")
        if isinstance(items, list):
            if not items:
                return "Em chưa tìm thấy gì khớp."
            return "\n".join(f"• {item}" for item in items[:6])
        if output.get("result"):
            return str(output["result"]).strip()
        if output.get("value") not in (None, ""):
            key = output.get("key") or ""
            return f"{key}: {output['value']}".strip(": ")
        parts = []
        for key, value in list(output.items())[:6]:
            if key in {"remembered", "memory_id", "evidence"}:
                continue
            if value in (None, "", [], {}):
                continue
            parts.append(f"{key}: {value}")
        return "\n".join(parts)
    if isinstance(output, list):
        return "\n".join(f"• {item}" for item in output[:6])
    return str(output).strip()


def present_result(
    *,
    objective: Optional[Objective] = None,
    action: Optional[Action] = None,
    execution: Optional[ExecutionResult] = None,
    verification: Any = None,
    phase: str = "",
    last_outcome: str = "",
    error: str = "",
) -> Optional[dict]:
    presence = classify_presence(
        phase,
        objective_status=objective.status if objective else "",
        last_outcome=last_outcome,
    )
    if presence == "needs_you":
        return None
    if presence == "working":
        return None

    action_d = _as_dict(action)
    execution_d = _as_dict(execution)
    verification_d = _as_dict(verification)
    action_type = _lower(action_d.get("type"))
    ok = True
    if presence == "error" or _upper(last_outcome) == "FAILED":
        ok = False
    if execution_d and execution_d.get("success") is False:
        ok = False
    if verification_d.get("verdict") in {"FAIL", "FAILED"}:
        ok = False

    if not ok:
        body = error or (objective.last_error if objective else "") or execution_d.get("error") or "Em chưa hoàn thành được việc này."
        return {
            "present": True,
            "ok": False,
            "headline": "Chưa xong",
            "body": body,
        }

    # Idle with nothing done — no result card.
    if presence == "ready" and not execution_d and not (objective and objective.status == ObjectiveState.COMPLETED.value):
        if not last_outcome or last_outcome in {"", "IDLE"}:
            return None

    headline = ACTION_DONE.get(action_type, "Em đã xong.")
    body = _format_output(execution_d.get("output"))
    if not body and objective:
        body = objective.desired_outcome or objective.intent
    if presence == "watching":
        headline = "Em đang theo dõi giúp anh."
        body = (objective.intent if objective else body) or body
    return {
        "present": True,
        "ok": True,
        "headline": headline,
        "body": body or "Em đã hoàn thành việc anh giao.",
    }


def present_pending_approval(objective: Optional[Objective], action: Optional[Action] = None) -> Optional[dict]:
    if objective is None:
        return None
    blocked = objective.status == ObjectiveState.BLOCKED.value
    pending = objective.pending_action
    if not blocked and not pending:
        return None
    action_d = _as_dict(action) or dict(pending or {})
    cap = str(action_d.get("capability") or "")
    operation = str(action_d.get("operation") or action_d.get("type") or "")
    if "mutation" in cap.lower() or "config" in cap.lower():
        summary = "Cập nhật cấu hình Agent Core"
    elif cap:
        summary = cap
    else:
        summary = _humanize_token(operation) or "hành động này"
    reason = objective.last_error or "Việc này có thể thay đổi dữ liệu, nên em cần anh cho phép."
    return {
        "present": True,
        "headline": "Anh cần xác nhận trước khi em tiếp tục.",
        "reason": reason,
        "action_summary": summary,
        "objective_id": objective.objective_id,
        "capability": cap,
        "operation": operation,
    }


def present_objective(objective: Optional[Objective]) -> Optional[dict]:
    if objective is None:
        return None
    return {
        "id": objective.objective_id,
        "intent": objective.intent,
        "desired_outcome": objective.desired_outcome or objective.intent,
        "status": objective.status,
        "status_label": OBJECTIVE_STATUS_LABEL.get(objective.status, _humanize_token(objective.status)),
        "kind": objective.kind,
        "updated_at": objective.updated_at,
        "created_at": objective.created_at,
        "last_error": objective.last_error,
    }


def present_history(objectives: Iterable[Objective], *, limit: int = 12) -> list[dict]:
    items = list(objectives or [])
    items.sort(key=lambda o: o.updated_at or o.created_at, reverse=True)
    out = []
    for obj in items[:limit]:
        row = present_objective(obj)
        if row:
            out.append(row)
    return out


def present_completed_actions(events: Iterable[AgentEvent], *, limit: int = 8) -> list[dict]:
    """Translate AgentEvents into user-readable completed steps."""
    rows: list[dict] = []
    for ev in list(events or [])[-40:]:
        d = ev.to_dict() if isinstance(ev, AgentEvent) else dict(ev or {})
        phase = _upper(d.get("phase"))
        status = _upper(d.get("status"))
        if phase in {"RESULT", "TASK_COMPLETED", "ACTION_COMPLETED", "EXECUTE", "VERIFY", "EXPERIENCE", "MEMORY_UPDATED"}:
            label = activity_headline(phase=phase, event=d)
            if status in {"FAIL", "ERROR"}:
                label = d.get("action") or d.get("message") or "Một bước chưa thành công."
            rows.append({
                "id": d.get("event_id") or "",
                "label": label,
                "ok": status not in {"FAIL", "ERROR"},
                "at": d.get("timestamp") or "",
                "phase": phase,
                "status": status,
            })
    return rows[-limit:]


def present_identity(state: AgentState, *, objective: Optional[Objective] = None) -> dict:
    presence = classify_presence(
        state.phase,
        objective_status=objective.status if objective else "",
        last_outcome=state.last_outcome,
    )
    return {
        "name": "Agent Core",
        "status": presence,
        "status_label": PRESENCE_LABEL.get(presence, "Sẵn sàng"),
        "status_detail": PRESENCE_DETAIL.get(presence, PRESENCE_DETAIL["ready"]),
    }


def present_activity(
    state: AgentState,
    *,
    objective: Optional[Objective] = None,
    action: Optional[Action] = None,
    decision: Any = None,
    events: Optional[Iterable[AgentEvent]] = None,
) -> dict:
    last_event = None
    evs = list(events or [])
    if evs:
        last_event = evs[-1]
    presence = classify_presence(
        state.phase,
        objective_status=objective.status if objective else "",
        last_outcome=state.last_outcome,
    )
    action_type = _lower(_as_dict(action).get("type"))
    if presence == "needs_you":
        headline = PHASE_ACTIVITY["NEEDS_USER"]
    elif presence == "error":
        headline = PHASE_ACTIVITY["FAILED"]
    elif presence == "ready" and state.last_outcome in {"COMPLETED", "IDLE", ""}:
        if objective and objective.status == ObjectiveState.COMPLETED.value:
            headline = ACTION_DONE.get(action_type, PHASE_ACTIVITY["COMPLETED"])
        else:
            headline = PHASE_ACTIVITY["IDLE"]
    else:
        headline = activity_headline(phase=state.phase, action=action, event=last_event)
    return {
        "headline": headline,
        "detail": PRESENCE_DETAIL.get(presence, ""),
        "why": why_copy(decision=decision, action=action, phase=state.phase),
        "source_phase": state.phase,
    }


def present_progress(state: AgentState, stages: Iterable[str], *, objective: Optional[Objective] = None) -> dict:
    presence = classify_presence(
        state.phase,
        objective_status=objective.status if objective else "",
        last_outcome=state.last_outcome,
    )
    steps = _progress_steps(stages, state.phase, presence)
    return {
        "ratio": _progress_ratio(stages, state.phase, presence),
        "steps": steps,
        "current_label": next((s["label"] for s in steps if s["active"]), steps[-1]["label"] if steps else ""),
        "completed_labels": [s["label"] for s in steps if s["done"]],
    }


def present_error(state: AgentState, *, objective: Optional[Objective] = None, error: str = "") -> Optional[dict]:
    presence = classify_presence(
        state.phase,
        objective_status=objective.status if objective else "",
        last_outcome=state.last_outcome,
    )
    if presence != "error":
        return None
    message = error or state.last_error or (objective.last_error if objective else "") or "Em gặp trở ngại khi làm việc này."
    return {
        "present": True,
        "message": message,
        "recovery_hint": "Anh thử nói lại, hoặc cho em phép làm tiếp.",
    }


def present_cycle(result: CycleResult) -> dict:
    """User-facing slice of one CycleResult. Additive; does not replace Runtime fields."""
    objective = result.objective
    state = result.agent_state
    identity = present_identity(state, objective=objective)
    pending = present_pending_approval(objective, result.action)
    return {
        "identity": identity,
        "objective": present_objective(objective),
        "activity": present_activity(
            state, objective=objective, action=result.action, decision=result.decision
        ),
        "progress": present_progress(state, result.stages, objective=objective),
        "result": present_result(
            objective=objective,
            action=result.action,
            execution=result.execution,
            verification=result.verification,
            phase=state.phase,
            last_outcome=state.last_outcome,
            error=result.error,
        ),
        "pending_approval": pending,
        "error": present_error(state, objective=objective, error=result.error),
        "completed_actions": [],
    }


def present_workspace(
    *,
    state: AgentState,
    objectives: Iterable[Objective],
    events: Optional[Iterable[AgentEvent]] = None,
    cycle: Optional[CycleResult] = None,
) -> dict:
    """Full User UI snapshot. Built only from Runtime abstractions."""
    objs = list(objectives or [])
    active = None
    if cycle and cycle.objective:
        active = cycle.objective
    elif state.active_objective_id:
        active = next((o for o in objs if o.objective_id == state.active_objective_id), None)
    if active is None:
        open_objs = [o for o in objs if o.status in {
            ObjectiveState.RUNNING.value,
            ObjectiveState.BLOCKED.value,
            ObjectiveState.WAITING.value,
            ObjectiveState.PENDING.value,
        }]
        open_objs.sort(key=lambda o: o.updated_at or o.created_at, reverse=True)
        active = open_objs[0] if open_objs else None

    action = cycle.action if cycle else None
    if action is None and active and active.pending_action:
        try:
            action = Action.from_dict(active.pending_action)
        except Exception:
            action = None

    stages = list(cycle.stages) if cycle else []
    identity = present_identity(state, objective=active)
    pending = present_pending_approval(active, action)
    evs = list(events or [])
    relevant = [e for e in evs if not active or e.run_id == active.objective_id or not e.run_id]
    if not relevant:
        relevant = evs

    return {
        "identity": identity,
        "objective": present_objective(active),
        "activity": present_activity(
            state,
            objective=active,
            action=action,
            decision=cycle.decision if cycle else None,
            events=relevant,
        ),
        "progress": present_progress(state, stages, objective=active),
        "result": present_result(
            objective=active,
            action=action,
            execution=cycle.execution if cycle else None,
            verification=cycle.verification if cycle else None,
            phase=state.phase,
            last_outcome=state.last_outcome,
            error=(cycle.error if cycle else "") or state.last_error,
        ),
        "pending_approval": pending,
        "error": present_error(state, objective=active, error=(cycle.error if cycle else "") or state.last_error),
        "completed_actions": present_completed_actions(relevant),
        "history": present_history(objs),
        "developer": {
            "phase": state.phase,
            "last_outcome": state.last_outcome,
            "loop_iteration": state.loop_iteration,
            "llm_calls": state.llm_calls if cycle is None else (cycle.llm_calls or state.llm_calls),
            "active_objective_id": state.active_objective_id,
            "stages": stages,
            "autonomy_enabled": state.autonomy_enabled,
            "updated_at": state.updated_at,
        },
    }


def serialize_cycle(result: CycleResult) -> dict:
    """API payload for submit/approve. Keeps historical fields, adds presentation."""
    verification = result.verification
    verification_d = _as_dict(verification)
    return {
        "event_id": result.event.event_id,
        "objective": result.objective.to_dict() if result.objective else None,
        "phase": result.agent_state.phase,
        "stages": list(result.stages),
        "outcome": result.agent_state.last_outcome,
        "llm_calls": result.llm_calls,
        "error": result.error or "",
        "agent_state": result.agent_state.to_dict(),
        "action": result.action.to_dict() if result.action else None,
        "execution": result.execution.to_dict() if result.execution else None,
        "verification": verification_d or None,
        "presentation": present_cycle(result),
    }
