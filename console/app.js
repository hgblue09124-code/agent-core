/**
 * agent-core Live Console — app.js
 * Fetches real events from the Live Activity API and renders them.
 * No fake events. No animations. Just real data.
 */

const API_BASE = '';  // same origin

// ── State ─────────────────────────────────────────────────────────────

const state = {
  runs: {},           // run_id → { phase, status, last_ts, event_count }
  activeRunId: null,
  eventCount: 0,
  connected: false,
  es: null,           // EventSource
  pollTimer: null,
  lastSeenEventId: new Set(),
};

// ── API helpers ───────────────────────────────────────────────────────

async function api(url) {
  const r = await fetch(API_BASE + url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}

async function fetchRuns() {
  try {
    const data = await api('/api/runs');
    return data.runs || [];
  } catch {
    return [];
  }
}

async function fetchRunInfo(runId) {
  return api(`/api/runs/${runId}`);
}

async function fetchEvents(runId) {
  return api(`/api/runs/${runId}/events?limit=200`);
}

async function fetchResult(runId) {
  return api(`/api/runs/${runId}/result`);
}

async function fetchHealth() {
  try {
    return await api('/api/healthz');
  } catch {
    return null;
  }
}

// ── Live connection ───────────────────────────────────────────────────

function connectLive(runId) {
  if (state.es) {
    state.es.close();
    state.es = null;
  }
  const url = `/api/runs/${runId}/stream`;
  try {
    state.es = new EventSource(url);
  } catch {
    startPolling(runId);
    return;
  }

  setStatus('connecting');
  state.es.onopen = () => { setStatus('connected'); state.connected = true; };

  state.es.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'done') {
        // Stream ended
        renderResult();
        return;
      }
      handleEvent(ev);
    } catch { /* ignore parse errors */ }
  };

  state.es.onerror = () => {
    state.connected = false;
    setStatus('disconnected');
    if (state.es) {
      state.es.close();
      state.es = null;
    }
    // Fallback to polling
    startPolling(runId);
  };
}

function startPolling(runId) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    try {
      const evs = await fetchEvents(runId);
      if (evs.events) {
        evs.events.forEach(handleEvent);
      }
      const health = await fetchHealth();
      if (health) setStatus('connected');
    } catch {
      setStatus('disconnected');
    }
  }, 1000);
}

function stopLive() {
  if (state.es) { state.es.close(); state.es = null; }
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  setStatus('disconnected');
}

function setStatus(status) {
  const el = document.getElementById('connection-status');
  const labels = {
    connected: '● Connected',
    disconnected: '○ Disconnected',
    connecting: '◐ Connecting',
  };
  el.textContent = labels[status] || status;
  el.className = 'conn-status ' + status;
}

// ── Event handler ─────────────────────────────────────────────────────

function handleEvent(ev) {
  const runId = ev.run_id;
  if (!state.runs[runId]) {
    state.runs[runId] = { phase: '', status: '', event_count: 0 };
  }
  const run = state.runs[runId];
  run.phase = ev.phase;
  run.status = ev.status;
  run.last_ts = ev.timestamp;
  run.event_count = (run.event_count || 0) + 1;
  state.eventCount++;

  // Update counters
  document.getElementById('event-count').textContent =
    state.eventCount + ' event' + (state.eventCount !== 1 ? 's' : '');

  // Deduplicate
  if (state.lastSeenEventId.has(ev.event_id)) return;
  state.lastSeenEventId.add(ev.event_id);

  // Update run list
  renderRunList();

  // Update active run panels
  if (runId === state.activeRunId) {
    prependEvent(ev);
    renderEvidence(ev);
    if (ev.phase === 'RESULT') renderResult();
    else renderGoal();  // refresh goal meta
  }
}

// ── Render helpers ─────────────────────────────────────────────────────

function renderRunList() {
  const el = document.getElementById('run-list');
  const runs = Object.entries(state.runs)
    .sort(([, a], [, b]) => (b.last_ts || '').localeCompare(a.last_ts || ''));

  if (runs.length === 0) {
    el.innerHTML = '<div class="empty-state">No runs yet</div>';
    return;
  }

  el.innerHTML = runs.map(([id, r]) => {
    const phaseClass = r.phase.toLowerCase();
    const active = id === state.activeRunId ? ' active' : '';
    return `
      <div class="run-item${active}" onclick="selectRun('${id}')">
        <div class="run-id">${id}</div>
        <div class="run-phase">${r.phase}</div>
        <span class="run-status status-${r.status.toLowerCase()}">${r.status}</span>
      </div>`;
  }).join('');
}

async function selectRun(runId) {
  state.activeRunId = runId;
  stopLive();
  renderRunList();

  // Clear panels
  document.getElementById('activity-feed').innerHTML =
    '<div class="empty-state">Loading...</div>';
  document.getElementById('evidence-panel').innerHTML =
    '<div class="empty-state">No evidence yet</div>';
  document.getElementById('result-panel').innerHTML =
    '<div class="empty-state">Run not complete</div>';

  // Load all events for this run
  try {
    const evs = await fetchEvents(runId);
    document.getElementById('activity-feed').innerHTML = '';
    (evs.events || []).forEach(ev => {
      state.lastSeenEventId.add(ev.event_id);
      prependEvent(ev, /* silent */ true);
    });
  } catch { /* ignore */ }

  renderGoal();
  renderEvidenceForRun(runId);
  renderResultForRun(runId);

  // Connect to live stream
  connectLive(runId);
}

function prependEvent(ev, silent) {
  const feed = document.getElementById('activity-feed');
  if (feed.querySelector('.empty-state')) {
    feed.innerHTML = '';
  }

  const ts = formatTime(ev.timestamp);
  const line = document.createElement('div');
  line.className = 'event-line' + (silent ? '' : ' new');
  line.innerHTML = `
    <span class="event-time">${ts}</span>
    <span class="event-phase ${ev.phase}">${ev.phase}</span>
    <span class="event-status ${ev.status}">${ev.status}</span>
    <span class="event-body">
      <span class="event-action">${escHtml(ev.action || '')}</span>
      ${ev.message ? `<div class="event-message">${escHtml(ev.message)}</div>` : ''}
    </span>`;

  feed.insertBefore(line, feed.firstChild);

  // Trim to 500 lines
  while (feed.children.length > 500) {
    feed.removeChild(feed.lastChild);
  }
}

async function renderGoal() {
  if (!state.activeRunId) return;
  const el = document.getElementById('goal-panel');
  const info = await fetchRunInfo(state.activeRunId).catch(() => null);
  if (!info) return;

  const first = info.first_event || {};
  const last = info.last_event || {};
  const meta = last.metadata || {};

  el.innerHTML = `
    <div class="goal-panel-body">
      <span class="label">run_id</span><span class="value mono">${escHtml(state.activeRunId)}</span>
      <span class="label">project</span><span class="value">${escHtml(meta.project_id || last.message || '—')}</span>
      <span class="label">goal</span><span class="value">${escHtml(first.metadata?.goal || '—')}</span>
      <span class="label">phase</span><span class="value">${escHtml(last.phase)}</span>
      <span class="label">status</span><span class="value">${escHtml(last.status)}</span>
      <span class="label">started</span><span class="value">${formatTime(first.timestamp)}</span>
      <span class="label">events</span><span class="value">${info.event_count}</span>
    </div>`;
}

async function renderEvidenceForRun(runId) {
  const el = document.getElementById('evidence-panel');
  try {
    const data = await fetchEvents(runId);
    const evs = data.events || [];
    const evWithMeta = evs.filter(e => e.metadata && Object.keys(e.metadata).length > 0);
    if (evWithMeta.length === 0) {
      el.innerHTML = '<div class="empty-state">No evidence yet</div>';
      return;
    }
    el.innerHTML = evWithMeta.slice(-5).map(ev => {
      const rows = Object.entries(ev.metadata).map(([k, v]) => {
        if (v === null || v === undefined) return '';
        const vstr = String(v);
        const cls = v === true || vstr === 'PASS' ? 'pass' : v === false || vstr === 'FAIL' ? 'fail' : '';
        return `<div class="evidence-row">
          <span class="lbl">${escHtml(k)}</span>
          <span class="val ${cls}">${escHtml(vstr.substring(0, 200))}</span>
        </div>`;
      }).join('');
      return `<div class="evidence-section">
        <h3>${escHtml(ev.phase)} · ${formatTime(ev.timestamp)}</h3>
        ${rows}
      </div>`;
    }).join('');
  } catch {
    el.innerHTML = '<div class="empty-state">Error loading evidence</div>';
  }
}

function renderEvidence(ev) {
  // Append latest evidence
  if (!ev.metadata || Object.keys(ev.metadata).length === 0) return;
  const el = document.getElementById('evidence-panel');
  if (el.querySelector('.empty-state')) el.innerHTML = '';

  const rows = Object.entries(ev.metadata).map(([k, v]) => {
    if (v === null || v === undefined) return '';
    const vstr = String(v);
    const cls = v === true || vstr === 'PASS' ? 'pass' : v === false || vstr === 'FAIL' ? 'fail' : '';
    return `<div class="evidence-row">
      <span class="lbl">${escHtml(k)}</span>
      <span class="val ${cls}">${escHtml(vstr.substring(0, 200))}</span>
    </div>`;
  }).join('');

  const section = document.createElement('div');
  section.className = 'evidence-section';
  section.innerHTML = `<h3>${escHtml(ev.phase)} · ${formatTime(ev.timestamp)}</h3>${rows}`;
  el.insertBefore(section, el.firstChild);
  while (el.children.length > 5) el.removeChild(el.lastChild);
}

async function renderResultForRun(runId) {
  const el = document.getElementById('result-panel');
  try {
    const data = await fetchResult(runId);
    renderResultData(el, data);
  } catch {
    el.innerHTML = '<div class="empty-state">Run not complete</div>';
  }
}

function renderResult() {
  if (!state.activeRunId) return;
  renderResultForRun(state.activeRunId);
}

function renderResultData(el, data) {
  if (!data || !data.run_id) {
    el.innerHTML = '<div class="empty-state">No result data</div>';
    return;
  }

  const isPass = data.status === 'PASS' || data.status === 'OK';
  const isFail = data.status === 'FAIL' || data.status === 'ERROR';
  const statusCls = isPass ? 'pass' : isFail ? 'fail' : '';

  const verif = data.verification || {};
  const metrics = data.metrics || {};
  const verifText = verif.verified ? 'VERIFIED' : 'NOT VERIFIED';
  const verifCls = verif.verified ? 'pass' : 'fail';

  el.innerHTML = `
    <div class="result-row">
      <span class="lbl">run_id</span>
      <span class="val">${escHtml(data.run_id)}</span>
    </div>
    <div class="result-row">
      <span class="lbl">status</span>
      <span class="val big ${statusCls}">${escHtml(data.status)}</span>
    </div>
    <div class="result-row">
      <span class="lbl">verification</span>
      <span class="val ${verifCls}">${verifText}</span>
    </div>
    <div class="result-row">
      <span class="lbl">checks</span>
      <span class="val">${verif.pass_count ?? 0}/${verif.total_checks ?? 0} PASS</span>
    </div>
    <div class="result-row">
      <span class="lbl">tasks</span>
      <span class="val">${metrics.completed_tasks ?? 0} OK · ${metrics.failed_tasks ?? 0} FAIL</span>
    </div>
    <div class="result-row">
      <span class="lbl">llm_calls</span>
      <span class="val">${metrics.llm_calls ?? 0}</span>
    </div>
    <div class="result-row">
      <span class="lbl">tokens (est)</span>
      <span class="val">${metrics.estimated_tokens ?? 0}</span>
    </div>
    <div class="result-row">
      <span class="lbl">duration</span>
      <span class="val">${data.duration_seconds ? data.duration_seconds.toFixed(2) + 's' : '—'}</span>
    </div>
    <div class="result-row">
      <span class="lbl">events</span>
      <span class="val">${data.event_count ?? 0}</span>
    </div>
    <div class="result-row">
      <span class="lbl">evidence</span>
      <span class="val">${data.has_evidence ? 'Yes' : 'No'}</span>
    </div>`;
}

// ── Utility ───────────────────────────────────────────────────────────

function formatTime(ts) {
  if (!ts) return '—';
  try {
    // "2026-09-03T10:21:04" or "2026-09-03T10:21:04.123456+00:00"
    const t = ts.split('T')[1] || ts;
    return t.split('+')[0].split('.')[0];
  } catch {
    return ts;
  }
}

function escHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────

async function init() {
  // Check API health
  const health = await fetchHealth();
  if (health) {
    setStatus('connected');
    state.connected = true;
  } else {
    setStatus('disconnected');
  }

  // Load existing runs
  const runs = await fetchRuns();
  runs.forEach(r => {
    state.runs[r.run_id] = {
      phase: r.phase,
      status: r.status,
      last_ts: r.timestamp,
      event_count: r.event_count,
    };
  });
  renderRunList();

  // If there are runs, auto-select the latest
  if (runs.length > 0) {
    await selectRun(runs[0].run_id);
  }
}

init();
