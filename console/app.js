/**
 * Personal Agent — User Workspace
 * Presentation-only. Consumes AgentState / Objective / Activity / Result
 * via /api/agent/* . Does not branch layout on Runtime phases.
 */

const API_BASE = "";

const ui = {
  workspace: null,
  lastPresentation: null,
  conversation: [],
  sending: false,
  developerOpen: false,
  pendingObjectiveId: null,
};

function $(id) {
  return document.getElementById(id);
}

async function api(path, options) {
  const res = await fetch(API_BASE + path, {
    cache: "no-cache",
    headers: { "Content-Type": "application/json", ...(options && options.headers) },
    ...options,
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!res.ok) {
    const err = new Error((data && data.error) || res.statusText || "request failed");
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s == null ? "" : s);
  return d.innerHTML;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Chào buổi sáng";
  if (h < 18) return "Chào buổi chiều";
  return "Chào buổi tối";
}

function setPresence(status, label) {
  const pill = $("status-pill");
  const orb = $("orb");
  pill.dataset.status = status || "ready";
  $("status-label").textContent = label || "Sẵn sàng";
  orb.classList.toggle("working", status === "working" || status === "watching");
  orb.setAttribute("aria-label", "Agent status: " + (label || status || "ready"));
}

function renderIdentity(ws) {
  const identity = (ws && ws.identity) || {};
  $("greeting").textContent = greeting();
  setPresence(identity.status, identity.status_label);
}

function renderNow(ws, presentation) {
  const view = presentation || ws || {};
  const objective = view.objective || null;
  const activity = view.activity || {};
  const progress = view.progress || {};
  const result = view.result;
  const pending = view.pending_approval;
  const error = view.error;

  $("now-intent").textContent = objective
    ? objective.intent
    : (ui.sending ? "Em đang nhận việc của anh…" : "Chưa có việc nào đang chạy.");
  $("now-outcome").textContent = objective && objective.desired_outcome && objective.desired_outcome !== objective.intent
    ? objective.desired_outcome
    : (objective ? (objective.status_label || "") : "");

  $("activity-headline").textContent = ui.sending
    ? "Em đang làm việc cho anh…"
    : (activity.headline || "Em đang chờ anh giao việc.");
  $("activity-why").textContent = activity.why || "";

  const steps = progress.steps || [];
  const progressEl = $("progress-block");
  if (steps.length || (progress.ratio && progress.ratio > 0)) {
    progressEl.hidden = false;
    $("progress-fill").style.width = Math.round((progress.ratio || 0) * 100) + "%";
    $("steps").innerHTML = steps.map((s) => {
      const cls = s.active ? "active" : s.done ? "done" : "";
      const mark = s.done ? "✓" : s.active ? "" : "";
      return `<li class="${cls}"><span class="mark">${mark}</span><span>${esc(s.label)}</span></li>`;
    }).join("");
  } else {
    progressEl.hidden = true;
    $("steps").innerHTML = "";
  }

  const resultEl = $("result-block");
  const showResult = result && result.present && !ui.sending && !(pending && pending.present);
  if (showResult) {
    resultEl.hidden = false;
    resultEl.classList.toggle("ok", !!result.ok);
    resultEl.classList.toggle("bad", !result.ok);
    $("result-kicker").textContent = result.ok ? "Kết quả" : "Chưa xong";
    $("result-headline").textContent = result.headline || "";
    $("result-body").textContent = result.body || "";
  } else {
    resultEl.hidden = true;
  }

  const approvalEl = $("approval-block");
  if (pending && pending.present && !ui.sending) {
    approvalEl.hidden = false;
    ui.pendingObjectiveId = pending.objective_id;
    $("approval-headline").textContent = pending.headline || "Anh cần xác nhận trước khi em tiếp tục.";
    $("approval-reason").textContent = pending.reason || "";
    $("approval-action").textContent = pending.action_summary || "";
  } else {
    approvalEl.hidden = true;
    if (!pending) ui.pendingObjectiveId = null;
  }

  const errorEl = $("error-block");
  if (error && error.present && !ui.sending) {
    errorEl.hidden = false;
    $("error-message").textContent = error.message || "";
    $("error-hint").textContent = error.recovery_hint || "";
  } else {
    errorEl.hidden = true;
  }

  const done = (ws && ws.completed_actions) || [];
  const doneWrap = $("done-list");
  if (done.length) {
    doneWrap.hidden = false;
    $("done-items").innerHTML = done.map((d) =>
      `<li class="${d.ok ? "" : "bad"}">${esc(d.label)}</li>`
    ).join("");
  } else {
    doneWrap.hidden = true;
  }

  const history = (ws && ws.history) || [];
  const hist = $("history-list");
  if (!history.length) {
    hist.innerHTML = '<li class="empty-hint">Chưa có việc nào.</li>';
  } else {
    hist.innerHTML = history.map((h) =>
      `<li><span class="h-intent">${esc(h.intent)}</span><span class="h-status">${esc(h.status_label)}</span></li>`
    ).join("");
  }
}

function renderThread() {
  const thread = $("thread");
  if (!ui.conversation.length && !ui.sending) {
    thread.innerHTML = `
      <div class="msg agent">
        <p class="msg-kicker">Agent</p>
        <p>Anh giao việc, em làm. Không cần biết Runtime chạy thế nào.</p>
      </div>`;
    return;
  }
  const bits = ui.conversation.map((m) => {
    if (m.role === "user") {
      return `<div class="msg user"><p>${esc(m.text)}</p></div>`;
    }
    return `<div class="msg agent"><p class="msg-kicker">${esc(m.kicker || "Agent")}</p><p>${esc(m.text)}</p></div>`;
  });
  if (ui.sending) {
    bits.push(`<div class="msg agent working"><p class="msg-kicker">Agent</p><p class="msg-body">Em đang làm việc cho anh…</p></div>`);
  }
  thread.innerHTML = bits.join("");
  thread.scrollTop = thread.scrollHeight;
}

function renderDeveloper(ws, cycle) {
  const payload = {
    agent_state: ws && ws.developer,
    presentation_identity: ws && ws.identity,
    last_cycle_phase: cycle && cycle.phase,
    last_cycle_stages: cycle && cycle.stages,
    last_outcome: cycle && cycle.outcome,
    objective: cycle && cycle.objective,
  };
  $("developer-json").textContent = JSON.stringify(payload, null, 2);
}

function render(extraCycle) {
  const ws = ui.workspace;
  const presentation = ui.lastPresentation || ws;
  renderIdentity(ws || presentation);
  renderNow(ws, presentation);
  renderThread();
  renderDeveloper(ws, extraCycle);
}

async function refreshWorkspace() {
  try {
    ui.workspace = await api("/api/agent/workspace");
    if (ui.workspace && ui.workspace.identity) {
      ui.lastPresentation = ui.workspace;
    }
  } catch {
    /* keep last snapshot */
  }
  render();
}

function pushAgentFromPresentation(p, fallback) {
  if (!p) {
    ui.conversation.push({ role: "agent", text: fallback || "Em đã nhận việc." });
    return;
  }
  if (p.pending_approval && p.pending_approval.present) {
    ui.conversation.push({
      role: "agent",
      kicker: "Cần anh",
      text: p.pending_approval.headline + (p.pending_approval.reason ? "\n" + p.pending_approval.reason : ""),
    });
    return;
  }
  if (p.error && p.error.present) {
    ui.conversation.push({ role: "agent", kicker: "Trở ngại", text: p.error.message });
    return;
  }
  if (p.result && p.result.present) {
    const body = [p.result.headline, p.result.body].filter(Boolean).join("\n");
    ui.conversation.push({ role: "agent", kicker: p.result.ok ? "Kết quả" : "Chưa xong", text: body });
    return;
  }
  ui.conversation.push({
    role: "agent",
    text: (p.activity && p.activity.headline) || fallback || "Em đã xong bước này.",
  });
}

async function submitMessage(text, extras) {
  const message = String(text || "").trim();
  if (!message || ui.sending) return;
  ui.sending = true;
  ui.conversation.push({ role: "user", text: message });
  render();
  $("composer-input").value = "";
  try {
    const body = { message, ...(extras || {}) };
    const res = await api("/api/agent/submit", {
      method: "POST",
      body: JSON.stringify(body),
    });
    ui.lastPresentation = res.presentation || ui.lastPresentation;
    pushAgentFromPresentation(res.presentation, res.error);
    await refreshWorkspace();
  } catch (err) {
    ui.conversation.push({
      role: "agent",
      kicker: "Lỗi",
      text: (err && err.message) || "Em không gửi được việc này.",
    });
  } finally {
    ui.sending = false;
    render();
  }
}

async function approvePending() {
  const id = ui.pendingObjectiveId
    || (ui.workspace && ui.workspace.pending_approval && ui.workspace.pending_approval.objective_id);
  if (!id || ui.sending) return;
  ui.sending = true;
  render();
  try {
    const res = await api("/api/agent/approve", {
      method: "POST",
      body: JSON.stringify({ objective_id: id }),
    });
    ui.lastPresentation = res.presentation || ui.lastPresentation;
    pushAgentFromPresentation(res.presentation, "Em đã làm tiếp.");
    await refreshWorkspace();
  } catch (err) {
    ui.conversation.push({
      role: "agent",
      kicker: "Lỗi",
      text: (err && err.message) || "Em chưa nhận được xác nhận.",
    });
  } finally {
    ui.sending = false;
    render();
  }
}

function dismissApproval() {
  ui.conversation.push({
    role: "agent",
    text: "Được. Em giữ nguyên, không làm bước đó.",
  });
  const block = $("approval-block");
  if (block) block.hidden = true;
  renderThread();
}

async function loadDeveloperFeed() {
  const feed = $("activity-feed");
  try {
    const data = await api("/api/runs");
    const runs = (data && data.runs) || [];
    if (!runs.length) {
      feed.innerHTML = '<div class="empty-state">Waiting for events...</div>';
      return;
    }
    const runId = runs[0].run_id;
    const evs = await api("/api/runs/" + encodeURIComponent(runId) + "/events?limit=80");
    const events = (evs && evs.events) || [];
    if (!events.length) {
      feed.innerHTML = '<div class="empty-state">Waiting for events...</div>';
      return;
    }
    feed.innerHTML = events.slice().reverse().map((ev) => {
      const ts = String(ev.timestamp || "").split("T")[1] || "";
      return `<div class="event-line">
        <span>${esc(ts.split(".")[0])}</span>
        <span>${esc(ev.phase)} · ${esc(ev.status)}</span>
        <span>${esc(ev.action || ev.message || "")}</span>
      </div>`;
    }).join("");
  } catch {
    feed.innerHTML = '<div class="empty-state">Waiting for events...</div>';
  }
}

function toggleDeveloper() {
  ui.developerOpen = !ui.developerOpen;
  $("developer").hidden = !ui.developerOpen;
  $("toggle-developer").setAttribute("aria-pressed", ui.developerOpen ? "true" : "false");
  document.getElementById("app").classList.toggle("dev-open", ui.developerOpen);
  if (ui.developerOpen) loadDeveloperFeed();
}

function bind() {
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    submitMessage($("composer-input").value);
  });
  $("toggle-developer").addEventListener("click", toggleDeveloper);
  $("approve-btn").addEventListener("click", approvePending);
  $("deny-btn").addEventListener("click", dismissApproval);
  document.querySelectorAll(".quick").forEach((btn) => {
    btn.addEventListener("click", () => submitMessage(btn.getAttribute("data-prompt")));
  });
}

async function init() {
  bind();
  await refreshWorkspace();
  const ws = ui.workspace;
  if (ws && ws.history && ws.history.length && !ui.conversation.length) {
    const latest = ws.history[0];
    if (latest && latest.intent) {
      ui.conversation.push({ role: "user", text: latest.intent });
      if (ws.result && ws.result.present) {
        pushAgentFromPresentation(ws);
      }
    }
  }
  render();
}

init();
