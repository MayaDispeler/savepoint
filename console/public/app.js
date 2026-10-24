"use strict";
// Savepoint console: static viewer of recorded data (window.BUNDLE, window.EXPERIENCE). No network requests.
// Pages are hash routes so every page and filter state can be linked from a portfolio.
const B = window.BUNDLE, X = window.EXPERIENCE;
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (x, d = 1) => (x == null ? "n/a" : (x * 100).toFixed(d) + "%");
const num = (n) => Number(n).toLocaleString("en-US");

const APPS = {
  claimdesk: { name: "ClaimDesk 98", kind: "A fake insurance-claims screen built for this project", real: false },
  openmrs: { name: "OpenMRS", kind: "A real hospital record system (open source, run in Docker)", real: true },
  idempiere: { name: "iDempiere", kind: "A real business and ERP system (open source, run in Docker)", real: true },
};
const ARMS = {
  B: { name: "No protection", blurb: "The agent runs on its own, with nothing watching it." },
  S: { name: "Savepoint", blurb: "Checkpoints, checks, and automatic undo when something is wrong." },
  R: { name: "Savepoint + retry", blurb: "Same, and the agent gets another try from the last good state." },
};
const OUT = {
  VS: { icon: "check", word: "Correct", badge: "ok", what: "Finished the task and the data is right." },
  VF: { icon: "undo", word: "Safe fail", badge: "safe", what: "Did not finish, but left the data exactly as it was." },
  IS: { icon: "alertCircle", word: "False done", badge: "wrong", what: "Said “done”, but the data is wrong. Nobody was warned." },
  IF: { icon: "x", word: "Mess left", badge: "mess", what: "Stopped partway and left half-finished changes behind." },
  RF: { icon: "alert", word: "Restore failed", badge: "rf", what: "The undo itself was not exact (this never happened)." },
};
const FAULT_TEXT = {
  none: "No failure was injected: the agent followed the instructions.",
  stop_at: "The agent was made to stop partway through.",
  wrong_value: "The agent was made to type a wrong value.",
  skip_save: "The agent was made to skip the final save, then report done anyway.",
  done_early: "The agent was made to report done after only part of the work.",
};
const outcome = (r) => (r.sp_outcome === "rollback_failed" ? "RF" : r.oracle);
const tile = (r) => {
  const o = outcome(r), d = OUT[o];
  return `<a class="tile o-${o}" href="#/run/${r.id}" aria-label="${esc(taskTitle(r.workflow_id))}, attempt ${r.trial}, ${esc(ARMS[r.arm].name)}: ${d.word}">${icon(d.icon)}<span>${d.word}</span></a>`;
};
const badge = (o) => `<span class="badge ${OUT[o].badge}">${icon(OUT[o].icon, "s")}${OUT[o].word}</span>`;
const appOf = (wf) => wf.split(".")[0];
const WF = Object.fromEntries((B ? B.workflows : []).map((w) => [w.id, w]));
const taskTitle = (id) => (WF[id] ? WF[id].title : id);
const results = B ? B.results : null;

// ---------- parse the contract YAML just enough to explain it in words ----------
function parseContract(w) {
  const lines = w.yaml.split("\n");
  const top = {};
  let key = null;
  for (const l of lines) {
    const m = /^([a-z_]+):\s?(.*)$/.exec(l);
    if (m) { key = m[1]; top[key] = [m[2]]; } else if (key) top[key].push(l);
  }
  const text = (k) => (top[k] || []).join(" ").replace(/\s+/g, " ").trim();
  const ids = (k) => (top[k] || []).map((l) => /^-\s+id:\s*(.+)$/.exec(l.trim())).filter(Boolean).map((m) => m[1]);
  const params = {};
  for (const l of top.params || []) { const m = /^\s+([a-z_]+):\s*(.+)$/.exec(l); if (m) params[m[1]] = m[2].replace(/^'|'$/g, ""); }
  let instr = text("instruction").replace(/\{([a-z_]+)(?::\.(\d)f)?\}/g, (_, k, d) => (params[k] == null ? "{" + k + "}" : d ? Number(params[k]).toFixed(Number(d)) : params[k]));
  const frame = (top.frame || []).join("\n");
  const allowed = (frame.match(/- table:/g) || []).length;
  return { instruction: instr, safety: ids("invariants").length, goal: ids("goal").length, allowed, lookup: /lookup_only: true/.test(w.yaml) };
}

// ---------- shell: navigation ----------
const NAV = [
  { group: "Start" },
  { route: "", label: "Overview", icon: "home" },
  { group: "Experience" },
  { route: "try", label: "Try it", icon: "play", note: "60 s" },
  { group: "Evidence" },
  { route: "results", label: "Test results", icon: "grid", note: B ? num(B.runs.length) : "" },
  { route: "benchmark", label: "Benchmark", icon: "chart" },
  { route: "tasks", label: "Tasks and rules", icon: "list", note: B ? String(B.workflows.length) : "" },
  { group: "Learn" },
  { route: "how", label: "How it works", icon: "shield" },
  { route: "glossary", label: "Glossary and limits", icon: "book" },
];
function renderNav(active) {
  $("#nav").innerHTML = NAV.map((n) => n.group ? `<div class="nav-group">${esc(n.group)}</div>` :
    `<a href="#/${n.route}" ${n.route === active ? 'aria-current="page"' : ""}>${icon(n.icon)}<span>${esc(n.label)}</span>${n.note ? `<small>${esc(n.note)}</small>` : ""}</a>`).join("");
}

function pageShell({ crumbs, title, lede, body, actions }) {
  const c = crumbs && crumbs.length ? `<nav class="crumbs" aria-label="Breadcrumb">${crumbs.map((x, i) => (x.href ? `<a href="${x.href}">${esc(x.label)}</a>` : `<span>${esc(x.label)}</span>`) + (i < crumbs.length - 1 ? icon("chevronRight") : "")).join("")}</nav>` : "";
  return `${c}<div class="pagehead"><h1>${esc(title)}</h1>${lede ? `<p>${lede}</p>` : ""}${actions || ""}</div>${body}`;
}

// ---------- pages ----------
function viewOverview() {
  const by = results.by_app;
  const rows = Object.keys(APPS).filter((a) => by[a]).map((a) => {
    const R = by[a].arms, n = Object.values(R).reduce((s, x) => s + x.n, 0);
    return `<tr><td><b>${esc(APPS[a].name)}</b><br><span class="subtle">${esc(APPS[a].kind)}</span></td><td class="num" data-label="Runs">${num(n)}</td>
      <td class="num" data-label="Ended clean, no protection">${pct(R.B.atomicity, 0)}</td><td class="num" data-label="Ended clean, with Savepoint"><b>${pct(R.S.atomicity, 0)}</b></td>
      <td class="num" data-label="Said done but wrong (without to with)">${R.B.IS} → <b>${R.S.IS}</b></td></tr>`;
  }).join("");
  const body = `
  <section class="sect" style="margin-top:0"><h2>How it works</h2><p class="lede">Three moves wrapped around any agent that clicks through software.</p>
    <div class="steps">
      <div class="step"><span class="n">1</span><h3>Save</h3><p>Before the agent starts, and before risky clicks like Save or Delete, Savepoint takes a checkpoint of the data.</p></div>
      <div class="step"><span class="n">2</span><h3>Check</h3><p>When the agent says “done”, Savepoint checks the result against a written rule: what must now be true, and what must not have changed.</p></div>
      <div class="step"><span class="n">3</span><h3>Undo</h3><p>If any check fails, Savepoint restores the checkpoint, then compares the data row by row to prove nothing was left behind.</p></div>
    </div></section>
  <section class="sect"><h2>What the tests show</h2>
    <p class="lede">600 recorded runs on three apps, with failures injected on purpose. “Ended clean” means the run either finished correctly or failed without changing anything.</p>
    <div class="panel flush"><table class="stack"><thead><tr><th>App</th><th class="num">Runs</th><th class="num">Ended clean, no protection</th><th class="num">Ended clean, with Savepoint</th><th class="num">Said “done” but wrong (without → with)</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="hintline" style="margin-top:8px">Source: <a href="#/benchmark">Benchmark</a>. Every one of the ${results.fidelity.restores} rollbacks restored the data exactly.</p></section>
  <section class="sect"><h2>What this is, and what it is not</h2>
    <div class="two"><div class="callout">${icon("info")}<div><p><b>What it is</b></p><p>A safety layer that sits around an agent. It does not make the agent smarter. It makes failures safe and catches false “done” reports.</p></div></div>
    <div class="callout warn">${icon("alert")}<div><p><b>What these numbers are not</b></p><p>The agent in every test is a script that fails on purpose, not an AI model. The numbers show what Savepoint does with known failures. They do not measure how reliable any AI model is.</p></div></div></div></section>
  <section class="sect"><h2>Where to go next</h2>
    <div class="panel flush"><table class="stack"><tbody>
      <tr><td><a href="#/try"><b>Try it</b></a></td><td class="muted">Break an agent on purpose and watch Savepoint undo it. About a minute.</td></tr>
      <tr><td><a href="#/results"><b>Test results</b></a></td><td class="muted">All 600 runs, one square each. Click any square to see exactly what happened.</td></tr>
      <tr><td><a href="#/benchmark"><b>Benchmark</b></a></td><td class="muted">The numbers per app: clean-outcome rate, repeated-attempt reliability, restore speed.</td></tr>
      <tr><td><a href="#/tasks"><b>Tasks and rules</b></a></td><td class="muted">The 30 tasks the agent was given and the written rules each result is checked against.</td></tr>
      <tr><td><a href="#/how"><b>How it works</b></a></td><td class="muted">A fuller explanation, with the technical detail for engineers.</td></tr>
    </tbody></table></div></section>`;
  return pageShell({
    title: "Undo for AI agents that work on old software",
    lede: "Many companies run on old screens with no API. An AI agent can click through them, but when it fails halfway, or says “done” when it isn’t, the data is left broken and someone has to repair it by hand. Savepoint is a safety layer: it saves the data before risky steps, checks the result, and restores the data if anything is wrong.",
    actions: `<div class="actions"><a class="btn primary" href="#/try">${icon("play", "s")} Try it: break an agent, then undo it</a><a class="btn" href="#/results">See the 600 test runs</a></div>`,
    body,
  });
}

const resState = { app: "claimdesk", arm: "all", show: "all" };
function viewResults() {
  const segBtn = (key, val, label) => `<button type="button" data-res="${key}" data-val="${val}" aria-pressed="${resState[key] === val}">${esc(label)}</button>`;
  const apps = Object.keys(APPS);
  const legend = ["VS", "VF", "IS", "IF", "RF"].map((o) => `<div class="item"><div class="tile o-${o}">${icon(OUT[o].icon)}<span>${OUT[o].word}</span></div><p><b>${OUT[o].word}</b>${OUT[o].what}</p></div>`).join("");
  const sel = B.runs.filter((r) => (resState.app === "all" || appOf(r.workflow_id) === resState.app) && (resState.arm === "all" || r.arm === resState.arm)
    && (resState.show === "all" || ["IS", "IF", "RF"].includes(outcome(r))));
  const cnt = (o) => sel.filter((r) => outcome(r) === o).length;
  let panels = "";
  for (const app of apps) {
    if (resState.app !== "all" && resState.app !== app) continue;
    for (const arm of ["B", "S", "R"]) {
      if (resState.arm !== "all" && resState.arm !== arm) continue;
      const runs = B.runs.filter((r) => appOf(r.workflow_id) === app && r.arm === arm);
      if (!runs.length) continue;
      const T = Math.max(...runs.map((r) => r.trial));
      const wfs = [...new Set(runs.map((r) => r.workflow_id))].sort();
      let g = `<div class="col"></div>` + [...Array(T).keys()].map((i) => `<div class="col">Attempt ${i + 1}</div>`).join("");
      for (const wf of wfs) {
        g += `<div class="wf">${esc(taskTitle(wf))}</div>`;
        for (let t = 1; t <= T; t++) {
          const r = runs.find((x) => x.workflow_id === wf && x.trial === t);
          const show = r && (resState.show === "all" || ["IS", "IF", "RF"].includes(outcome(r)));
          g += `<div>${show ? tile(r) : ""}</div>`;
        }
      }
      panels += `<section class="panel sect" style="margin-top:16px"><div class="armhead"><h3>${esc(APPS[app].name)} · ${esc(ARMS[arm].name)}</h3><p>${esc(ARMS[arm].blurb)}</p></div>
        <div class="grid res" style="grid-template-columns:minmax(150px,230px) repeat(${T},minmax(0,1fr))">${g}</div></section>`;
    }
  }
  const body = `
  <section class="sect" style="margin-top:0"><h2>How to read this page</h2>
    <p class="lede">Each square is one test run: an agent doing one small task. Rows are tasks and columns are repeat attempts (up to 10 on ClaimDesk, 5 on the real apps). The same failures were injected in every protection level, so rows line up fairly. <b>Click any square</b> to see the full story of that run.</p>
    <div class="panel"><div class="legend">${legend}</div></div></section>
  <section class="sect"><h2>Filter</h2>
    <div class="filters">
      <div class="field"><span class="label">App</span><div class="seg" role="group" aria-label="App">${segBtn("app", "all", "All apps")}${apps.map((a) => segBtn("app", a, APPS[a].name)).join("")}</div></div>
      <div class="field"><span class="label">Protection</span><div class="seg" role="group" aria-label="Protection">${segBtn("arm", "all", "All")}${["B", "S", "R"].map((a) => segBtn("arm", a, ARMS[a].name)).join("")}</div></div>
      <div class="field"><span class="label">Show</span><div class="seg" role="group" aria-label="Show">${segBtn("show", "all", "Every run")}${segBtn("show", "bad", "Only wrong results")}</div></div>
    </div>
    <p class="hintline">${resState.app === "all" ? "Showing every app." : "Showing " + esc(APPS[resState.app].name) + " only. Choose another app above to compare."}</p>
    <div class="summaryline" aria-live="polite"><span><b>${num(sel.length)}</b> runs shown</span><span>${cnt("VS")} correct</span><span>${cnt("VF")} safe fail</span><span>${cnt("IS")} false done</span><span>${cnt("IF")} mess left</span><span>${cnt("RF")} restore failed</span></div>
  </section>${panels || `<div class="callout">${icon("info")}<p>No runs match these filters.</p></div>`}`;
  return pageShell({ title: "Test results", lede: "Every recorded run, one square each, grouped by app and protection level.", body });
}
function bindResults() {
  $$("[data-res]").forEach((b) => b.addEventListener("click", () => { resState[b.dataset.res] = b.dataset.val; render(); }));
}

const STEP_WORDS = { "#save": "Click Save", "#ok": "Click OK on the confirmation", "#save-note": "Click Save note", "#delete": "Click Delete claim", "#next-button": "Click Next", "#submit": "Click Confirm", "#registration-submit": "Click Confirm", "#addAllergyBtn": "Click Save allergy", "#amount": "Type in the Amount box" };
function stepText(s) {
  const t = s.target || "";
  if (s.type === "goto") return "Open a page";
  if (s.type === "wait") return "Wait for the screen to finish";
  if (s.type === "fill") return STEP_WORDS[t] || "Type into a field";
  if (s.type === "select") return "Choose an option from a list";
  if (s.type === "click_until") return "Click Next until the confirm page appears";
  if (s.type === "click") return STEP_WORDS[t] || "Click a button or link";
  return s.type;
}
const CHECK_WORDS = { amount_under_cap: "The amount stays under 100,000", no_negative_amounts: "No amount is negative", no_orphan_notes: "No note is left without a claim", frame: "Nothing else changed" };
const checkText = (id) => CHECK_WORDS[id] || id.replace(/_/g, " ");

function viewRun(id) {
  const r = B.runs.find((x) => x.id === id);
  if (!r) return pageShell({ title: "Run not found", body: `<div class="callout bad">${icon("alert")}<p>No run has this id. <a href="#/results">Back to the test results</a>.</p></div>` });
  const o = outcome(r), app = appOf(r.workflow_id), info = WF[r.workflow_id] ? parseContract(WF[r.workflow_id]) : null;
  const steps = B.steps.filter((s) => s.run_id === id).sort((a, b) => a.idx - b.idx);
  const cps = B.checkpoints.filter((c) => c.run_id === id);
  const vals = B.validations.filter((v) => v.run_id === id);
  const rbs = B.rollbacks.filter((x) => x.run_id === id);
  let tl = `<li><span class="dot ${r.arm === "B" ? "" : "cp"}">${icon(r.arm === "B" ? "play" : "diamond", "s")}</span><div class="t">${r.arm === "B" ? "Run starts with no protection" : "Savepoint saves a checkpoint of the data"}<small>${r.arm === "B" ? "Nothing is saved, so nothing can be undone." : "This is the state everything can be rolled back to."}</small></div></li>`;
  for (const s of steps) {
    for (const c of cps.filter((c) => c.step_idx === s.idx && c.kind !== "initial")) tl += `<li><span class="dot cp">${icon("diamond", "s")}</span><div class="t">Savepoint saves a checkpoint<small>Taken before a risky click</small></div></li>`;
    tl += `<li><span class="dot">${icon(s.type === "fill" || s.type === "select" ? "code" : s.type === "wait" ? "info" : "arrowRight", "s")}</span><div class="t">Agent: ${esc(stepText(s))}${s.state_changed ? "<small>The data changed after this step</small>" : ""}</div></li>`;
  }
  const failed = vals.filter((v) => !v.passed);
  const goalish = vals.filter((v) => v.phase === "goal" || v.phase === "frame");
  if (vals.length) tl += `<li><span class="dot ${failed.length ? "bad" : "ok"}">${icon(failed.length ? "x" : "check", "s")}</span><div class="t">Savepoint checks the result<small>${failed.length ? failed.length + " check" + (failed.length > 1 ? "s" : "") + " failed" : "All checks passed"}</small></div></li>`;
  for (const rb of rbs) tl += `<li><span class="dot cp">${icon("undo", "s")}</span><div class="t">Savepoint restores the checkpoint<small>Rows different afterwards: ${rb.rows_differ}${rb.exact ? " (exact)" : ""}</small></div></li>`;
  if (r.sp_outcome === "committed" || r.sp_outcome === "retried_committed") tl += `<li><span class="dot ok">${icon("check", "s")}</span><div class="t">Result accepted<small>${r.retries ? "After a retry from the last good state" : "All checks passed"}</small></div></li>`;
  const checks = vals.length ? ["invariant", "goal", "frame"].map((ph) => {
    const items = vals.filter((v) => v.phase === ph);
    if (!items.length) return "";
    const title = ph === "invariant" ? "Safety checks after each change" : ph === "goal" ? "Did the task get done?" : "Did anything else change?";
    return `<h4 style="margin:12px 0 6px">${title}</h4>` + items.map((v) => `<div class="check ${v.passed ? "ok" : "bad"}">${icon(v.passed ? "check" : "x", "s")}<div>${esc(checkText(v.check_id))}${v.passed ? "" : `<small>Expected ${esc(JSON.stringify(v.expected))}, found ${esc(Array.isArray(v.observed) ? v.observed.join("; ") : JSON.stringify(v.observed))}</small>`}</div></div>`).join("");
  }).join("") : `<p class="muted">No checks ran. ${r.arm === "B" ? "This protection level has no checks." : "The run ended before any data changed and before the agent said done, so Savepoint only restored the checkpoint."}</p>`;
  let restore = "";
  for (const rb of rbs) {
    const why = { invariant: "a safety check failed", false_completion: "the agent said done but the result was wrong", agent_failed: "the agent could not finish", error: "the app produced an error", timeout: "the run took too long", step_budget: "the agent used too many steps" }[rb.reason] || rb.reason;
    restore += `<div class="panel" style="margin-top:16px"><h3>The undo</h3><p class="muted">Savepoint restored the checkpoint because ${esc(why)}. Rows different afterwards: <b>${rb.rows_differ}</b>${rb.exact ? ", so the restore was exact" : ""}. Restore took ${rb.restore_ms} ms.</p>
      ${rb.shot_before && rb.shot_after ? `<div class="cmp" id="cmp" style="--pos:50%"><img alt="Screen before the restore" src="${esc(rb.shot_before)}"><img class="after" alt="Screen after the restore" src="${esc(rb.shot_after)}"><div class="bar"></div><span class="lab l">Before</span><span class="lab r">After</span></div><input type="range" min="0" max="100" value="50" id="slider" aria-label="Slide to compare the screen before and after the restore"><p class="hintline">Drag the slider. The screen changed in ${rb.pixel_diff_pct}% of its pixels.</p>` : `<p class="hintline">Screenshots are saved for featured runs only. Try the ones marked in the Try it page.</p>`}</div>`;
  }
  const ctx = [
    ["The task", info ? esc(info.instruction) : esc(taskTitle(r.workflow_id))],
    ["What went wrong", esc(FAULT_TEXT[r.fault] || r.fault)],
    ["Protection", `<b>${esc(ARMS[r.arm].name)}.</b> ${esc(ARMS[r.arm].blurb)}`],
    ["How it ended", `${badge(o)} ${esc(OUT[o].what)}`],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  const tech = [["Run id", r.id], ["Task id", r.workflow_id], ["Attempt", r.trial], ["Injected fault", r.fault], ["Agent status", r.agent_status], ["Savepoint outcome", r.sp_outcome], ["Steps", r.steps], ["Retries", r.retries], ["Wall time (ms)", r.wall_ms], ["Checkpoint and restore time (ms)", r.checkpoint_ms]]
    .map(([k, v]) => `<dt>${k}</dt><dd class="mono">${esc(v)}</dd>`).join("");
  const body = `<div class="panel"><dl class="defs">${ctx}</dl></div>
    <div class="two wide-left" style="margin-top:16px"><div class="panel"><h3>What happened, in order</h3><ol class="tl" style="margin-top:12px">${tl}</ol></div>
      <div class="panel"><h3>What Savepoint checked</h3>${checks}</div></div>${restore}
    <details class="disc" style="margin-top:16px"><summary>${icon("chevronDown", "s")} Technical details</summary><div class="body"><dl class="defs">${tech}</dl></div></details>`;
  return pageShell({
    crumbs: [{ label: "Test results", href: "#/results" }, { label: APPS[app].name }, { label: taskTitle(r.workflow_id) }, { label: "Attempt " + r.trial }],
    title: taskTitle(r.workflow_id), lede: `${esc(APPS[app].name)} · attempt ${r.trial} · ${esc(ARMS[r.arm].name)}`, body,
    actions: `<div class="actions"><a class="btn sm" href="#/results">${icon("arrowLeft", "s")} Back to test results</a></div>`,
  });
}
function bindRun() { const sl = $("#slider"); if (sl) sl.addEventListener("input", () => $("#cmp").style.setProperty("--pos", sl.value + "%")); }

const benchState = { app: "claimdesk" };
function viewBenchmark() {
  const apps = Object.keys(APPS).filter((a) => results.by_app[a]);
  const R = results.by_app[benchState.app], arms = R.arms, W = 720, H = 300, L = 48, Rr = 140, T = 16, Bt = 36;
  const K = Math.max(2, ...Object.values(arms).map((a) => Object.keys(a.pass_hat_k).length));
  const x = (k) => L + ((k - 1) / (K - 1)) * (W - L - Rr), y = (v) => T + (1 - v) * (H - T - Bt);
  const sty = { B: 'stroke="#101828" stroke-dasharray="6 4"', S: 'stroke="#1D4ED8"', R: 'stroke="#1D4ED8" stroke-dasharray="2 3"' };
  let g = "";
  for (let v = 0; v <= 1.001; v += 0.25) g += `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="#E4E7EC"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${Math.round(v * 100)}%</text>`;
  for (let k = 1; k <= K; k++) g += `<text x="${x(k)}" y="${H - 14}" text-anchor="middle">${k}</text>`;
  g += `<text x="${(L + W - Rr) / 2}" y="${H}" text-anchor="middle">Number of attempts in a row</text>`;
  const same = (a, b) => arms[a] && arms[b] && JSON.stringify(arms[a].pass_hat_k) === JSON.stringify(arms[b].pass_hat_k);
  const labels = [];
  for (const a of ["S", "R", "B"]) {
    const ph = arms[a] && arms[a].pass_hat_k; if (!ph) continue;
    const pts = Object.keys(ph).map((k) => [x(+k), y(ph[k])]);
    g += `<path d="${pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ")}" fill="none" stroke-width="${a === "B" ? 2 : 3.5}" ${sty[a]}/>` + pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="${a === "B" ? 2.5 : 3.5}" fill="${a === "B" ? "#101828" : "#1D4ED8"}"/>`).join("");
    const last = pts[pts.length - 1];
    if (a === "B" && same("B", "S")) labels.push([`<text class="lab" x="${last[0] + 8}" y="${last[1] + 2}">No protection</text><text x="${last[0] + 8}" y="${last[1] + 17}">(same as Savepoint)</text>`]);
    else if (!(a === "S" && same("B", "S"))) labels.push([`<text class="lab" x="${last[0] + 8}" y="${last[1] + 4}">${esc(ARMS[a].name)}</text>`]);
  }
  labels.forEach(([svgText]) => { g += svgText; });
  let bars = "";
  ["B", "S", "R"].forEach((a, i) => {
    const m = arms[a]; if (!m) return;
    const yy = 12 + i * 52, w = W - 330, [lo, hi] = m.atomicity_ci95, col = a === "B" ? "#101828" : "#1D4ED8";
    bars += `<text class="lab" x="0" y="${yy + 16}">${esc(ARMS[a].name)}</text><rect x="150" y="${yy}" width="${w}" height="24" rx="4" fill="#F2F4F7"/><rect x="150" y="${yy}" width="${w * m.atomicity}" height="24" rx="4" fill="${col}"/><line x1="${150 + w * lo}" x2="${150 + w * hi}" y1="${yy + 12}" y2="${yy + 12}" stroke="#B42318" stroke-width="3"/><text x="${160 + w}" y="${yy + 17}">${pct(m.atomicity, 0)} (${pct(lo, 0)} to ${pct(hi, 0)})</text>`;
  });
  const rows = ["B", "S", "R"].filter((a) => arms[a]).map((a) => { const m = arms[a]; return `<tr><td><b>${esc(ARMS[a].name)}</b></td><td class="num" data-label="Runs">${m.n}</td><td class="num" data-label="Correct">${m.VS}</td><td class="num" data-label="Safe fail">${m.VF}</td><td class="num" data-label="False done">${m.IS}</td><td class="num" data-label="Mess left">${m.IF}</td><td class="num" data-label="Finished correctly">${pct(m.valid_success, 0)}</td><td class="num" data-label="Ended clean"><b>${pct(m.atomicity, 0)}</b></td></tr>`; }).join("");
  const c = R.catch, t = R.timings, f = R.fidelity;
  const seg = apps.map((a) => `<button type="button" data-bapp="${a}" aria-pressed="${benchState.app === a}">${esc(APPS[a].name)}</button>`).join("");
  const body = `<div class="field"><span class="label">App</span><div class="seg" role="group" aria-label="App">${seg}</div></div>
  <p class="hintline" style="margin-top:8px">${esc(APPS[benchState.app].kind)}. ${arms.B.workflows} tasks, ${arms.B.trials_per_workflow} attempts each, at three protection levels.</p>
  <section class="sect"><h2>How often a run ended clean</h2>
    <p class="lede">A run ends clean when it either finishes correctly or fails without changing anything. Higher is better. The red line is the 95% confidence range (Wilson interval): with only ${arms.B.n} runs per level, the true rate could sit anywhere inside it.</p>
    <div class="panel"><svg class="chart" viewBox="0 0 ${W} 170" role="img" aria-label="Share of runs that ended clean, per protection level">${bars}</svg></div></section>
  <section class="sect"><h2>Reliability over repeated attempts</h2>
    <p class="lede">If you ran the same task several times in a row, how likely is it that every run is correct? Real work needs this to stay high. ${same("B", "S") ? "The first two lines overlap because Savepoint (without retry) finishes the same tasks as the unprotected agent; what it changes is what the failed runs leave behind. Retry is what lets more runs finish." : ""} Technical name: pass^k.</p>
    <div class="panel"><svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Chance that all attempts in a row are correct">${g}</svg>
      <div class="keyrow"><span><i class="d"></i>No protection</span><span><i class="b"></i>Savepoint</span><span><i class="b dot"></i>Savepoint + retry</span></div></div></section>
  <section class="sect"><h2>Outcome counts</h2><p class="lede">How each run ended. See <a href="#/glossary">the glossary</a> for the five outcomes.</p>
    <div class="panel flush"><table class="stack"><thead><tr><th>Protection</th><th class="num">Runs</th><th class="num">Correct</th><th class="num">Safe fail</th><th class="num">False done</th><th class="num">Mess left</th><th class="num">Finished correctly</th><th class="num">Ended clean</th></tr></thead><tbody>${rows}</tbody></table></div></section>
  <section class="sect"><h2>Checks and restores</h2><div class="panel"><dl class="defs">
    <dt>False “done” reports caught</dt><dd><b>${c.caught} of ${c.false_claims}</b> (${pct(c.catch_rate, 0)}). When the agent said done and was wrong, Savepoint noticed.</dd>
    <dt>Good results flagged by mistake</dt><dd><b>${c.false_alarms} of ${c.true_claims}</b>. Savepoint never rolled back a run that was actually right.</dd>
    <dt>Restores that were exact</dt><dd><b>${f.exact} of ${f.restores}</b>. After each undo the data was compared row by row with the checkpoint.</dd>
    <dt>Speed (95th percentile)</dt><dd>Taking a checkpoint: <b>${t.checkpoint_p95_ms} ms</b>. Restoring: <b>${t.restore_p95_ms} ms</b>.</dd>
    <dt>Time cost</dt><dd>Checkpoints and restores took ${pct(R.overhead.checkpoint_restore_share_of_wall, 1)} of the run time.</dd></dl></div></section>
  <section class="sect"><details class="disc"><summary>${icon("chevronDown", "s")} Technical definitions and assumptions</summary><div class="body">
    <p><b>Ended clean</b> = atomicity = (correct + safe fail) / runs. <b>False done</b> = invalid success: the system reported done and the data differs from the expected change set. <b>Mess left</b> = invalid failure: reported not done, but data changed. Outcomes are judged by an independent oracle that never reads Savepoint’s checks.</p>
    <p><b>pass^k</b> for one task with n attempts and c correct is C(c,k)/C(n,k), averaged over tasks.</p>
    <p>${esc(B.agent)}. Faults are injected on a fixed schedule and paired across protection levels. These figures describe runtime behaviour on a known failure mix, not model reliability.</p></div></details></section>`;
  return pageShell({ title: "Benchmark", lede: "The same tasks and the same injected failures, at three protection levels. Pick an app.", body });
}
function bindBenchmark() { $$("[data-bapp]").forEach((b) => b.addEventListener("click", () => { benchState.app = b.dataset.bapp; render(); })); }

const taskState = { app: "all", q: "" };
function viewTasks() {
  const list = B.workflows.filter((w) => (taskState.app === "all" || appOf(w.id) === taskState.app) && (w.title + " " + w.id).toLowerCase().includes(taskState.q.toLowerCase())).sort((a, b) => a.id.localeCompare(b.id));
  const segBtn = (val, label) => `<button type="button" data-tapp="${val}" aria-pressed="${taskState.app === val}">${esc(label)}</button>`;
  const rows = list.map((w) => {
    const c = parseContract(w), runs = B.runs.filter((r) => r.workflow_id === w.id);
    return `<tr><td><b>${esc(w.title)}</b><br><span class="subtle">${esc(APPS[appOf(w.id)].name)}${c.lookup ? " · read-only task" : ""}</span></td><td data-label="The agent is told">${esc(c.instruction)}</td>
      <td class="num" data-label="Safety checks">${c.safety}</td><td class="num" data-label="Goal checks">${c.goal}</td><td class="num" data-label="Runs">${runs.length}</td>
      <td><details class="disc"><summary>${icon("chevronDown", "s")} Rule file</summary><div class="body"><pre>${esc(w.yaml)}</pre></div></details></td></tr>`;
  }).join("");
  const body = `<div class="callout">${icon("info")}<div><p>Before an agent starts a task, a rule file says how to judge the result. <b>Safety checks</b> must hold after every change. <b>Goal checks</b> say what must be true when the agent reports done. A <b>frame</b> lists everything that must not change. Rule files are plain YAML; the full text is under “Rule file”.</p></div></div>
  <div class="filters" style="margin-top:20px"><div class="field"><span class="label">App</span><div class="seg" role="group" aria-label="App">${segBtn("all", "All apps")}${Object.keys(APPS).map((a) => segBtn(a, APPS[a].name)).join("")}</div></div>
    <div class="field"><label for="tq">Search tasks</label><input id="tq" type="search" placeholder="for example: delete, allergy, vendor" value="${esc(taskState.q)}"></div></div>
  <div class="panel flush"><table class="stack"><thead><tr><th>Task</th><th>What the agent is told</th><th class="num">Safety checks</th><th class="num">Goal checks</th><th class="num">Runs</th><th>Rules</th></tr></thead><tbody>${rows || `<tr><td colspan="6" class="muted">No tasks match.</td></tr>`}</tbody></table></div>`;
  return pageShell({ title: "Tasks and rules", lede: `${B.workflows.length} tasks across three apps, each with a written rule file.`, body });
}
function bindTasks() {
  $$("[data-tapp]").forEach((b) => b.addEventListener("click", () => { taskState.app = b.dataset.tapp; render(); }));
  const q = $("#tq"); if (q) q.addEventListener("input", () => { taskState.q = q.value; const pos = q.selectionStart; render(); const n = $("#tq"); n.focus(); n.setSelectionRange(pos, pos); });
}

function viewHow() {
  const body = `
  <section class="sect" style="margin-top:0"><h2>The idea in one picture</h2><p class="lede">A database transaction lets you undo a half-finished change. Old screens give agents no such thing. Savepoint adds it from the outside.</p>
    <div class="panel"><svg class="chart" viewBox="0 0 760 150" role="img" aria-label="Timeline: checkpoint, agent steps, risky click with checkpoint, check fails, restore">
      <line x1="30" y1="75" x2="730" y2="75" stroke="#D0D5DD" stroke-width="2"/>
      <g fill="#EFF4FF" stroke="#1D4ED8" stroke-width="2"><path d="M70 55 90 75 70 95 50 75z"/><path d="M330 55 350 75 330 95 310 75z"/></g>
      <g fill="#FFFFFF" stroke="#475467" stroke-width="2"><circle cx="190" cy="75" r="12"/><circle cx="260" cy="75" r="12"/><circle cx="410" cy="75" r="12"/></g>
      <circle cx="500" cy="75" r="14" fill="#FEF3F2" stroke="#B42318" stroke-width="2"/><path d="m493 68 14 14M507 68l-14 14" stroke="#B42318" stroke-width="2" fill="none"/>
      <path d="M500 105 C 500 140, 90 140, 90 100" stroke="#1D4ED8" stroke-width="2.5" fill="none" stroke-dasharray="6 4"/><path d="m84 106 6-8 6 8" stroke="#1D4ED8" stroke-width="2.5" fill="none"/>
      <g font-size="12" fill="#475467" font-family="Inter,system-ui,sans-serif"><text x="30" y="30">Checkpoint</text><text x="150" y="40">Agent steps</text><text x="268" y="30">Checkpoint before a risky click</text><text x="395" y="40">Agent says done</text><text x="450" y="30" fill="#B42318" font-weight="600">Check fails</text><text x="230" y="146" fill="#1D4ED8" font-weight="600">Restore the checkpoint</text></g></svg></div></section>
  <section class="sect"><h2>Step by step</h2><div class="panel flush"><table><tbody>
    <tr><td><b>1. Checkpoint</b></td><td class="muted">The data the app keeps (database rows and files), plus the browser session and the page you are on, is saved. This happens at the start, and again just before any click on a risky control such as Save, Delete or OK. If nothing changed since the last checkpoint, it is skipped.</td></tr>
    <tr><td><b>2. Safety checks</b></td><td class="muted">After each step that changed data, rules that must always hold are tested (for example, “no amount is negative”). A failure stops the run immediately.</td></tr>
    <tr><td><b>3. Goal and frame checks</b></td><td class="muted">When the agent reports done, Savepoint tests what must now be true (“the amount is 1250.00 and a note exists”) and that nothing else changed (a diff of the data against the start, minus the changes the task allows).</td></tr>
    <tr><td><b>4. Restore</b></td><td class="muted">On any failure the checkpoint is restored. In the retry mode the agent is told why and tries again from the last good checkpoint, up to twice.</td></tr>
    <tr><td><b>5. Proof</b></td><td class="muted">After the restore, every monitored row is fingerprinted column by column and compared with the checkpoint. Any difference marks the run “Restore failed”. None did in ${results.fidelity.restores} restores.</td></tr></tbody></table></div></section>
  <section class="sect"><h2>For engineers</h2>
    <div class="two"><details class="disc"><summary>${icon("chevronDown", "s")} What exactly is saved and compared</summary><div class="body"><p>Per app adapter: the monitored tables (SQLite backup for ClaimDesk; a consistent read of the monitored MySQL and PostgreSQL tables for OpenMRS and iDempiere), a file-volume archive, the Playwright storage state and the URL. The digest is a per-row, per-column blake2b hash, with volatile columns (timestamps, uuids, generated ids) excluded.</p></div></details>
      <details class="disc"><summary>${icon("chevronDown", "s")} How "false done" is judged</summary><div class="body"><p>An oracle, separate from Savepoint’s own checks, replays the clean script once to get the expected change set, then compares each run’s final data with it. Oracle and validators never import each other (a test enforces it), so Savepoint cannot grade its own homework.</p></div></details>
      <details class="disc"><summary>${icon("chevronDown", "s")} Protection levels</summary><div class="body"><p><b>No protection</b>: the agent runs alone. <b>Savepoint</b> (atomic): on any failure restore the first checkpoint. <b>Savepoint + retry</b>: on a safety-check failure restore the last checkpoint before the bad step, append the reason, and let the agent retry (at most twice); a false done is retried from the start.</p></div></details>
      <details class="disc"><summary>${icon("chevronDown", "s")} Where to read more</summary><div class="body"><p><a href="https://github.com/MayaDispeler/savepoint" target="_blank" rel="noopener">The code</a> includes the written spec, the 30 rule files and <code>docs/validation.md</code>, which lists every acceptance check as pass, adapted or partial.</p></div></details></div></section>`;
  return pageShell({ title: "How it works", lede: "Savepoint wraps an agent in a transaction layer: save, check, undo, prove.", body });
}

function viewGlossary() {
  const terms = [
    ["Agent", "Software that operates another program by looking at its screen and clicking and typing, like a person would. Here it is a script, not an AI model."],
    ["Checkpoint", "A saved copy of the data, taken so it can be restored."],
    ["Restore (rollback)", "Putting the data back to a checkpoint."],
    ["Task rules (contract)", "A short YAML file that says how to judge one task: safety checks, goal checks and what must not change."],
    ["Safety check (invariant)", "Something that must be true after every change, such as “no amount is negative”."],
    ["Goal check", "Something that must be true when the agent says done, such as “the amount is 1250.00”."],
    ["Frame check", "A diff of the data against the start. Everything the task is allowed to change is removed; anything left is an unexpected change."],
    ["False done (invalid success)", "The agent said done but the data is wrong. The most dangerous failure, because nobody is warned."],
    ["Safe fail (valid failure)", "The run did not finish, but the data is exactly as it was before."],
    ["Mess left (invalid failure)", "The run stopped partway and left half-finished changes."],
    ["Ended clean (atomicity)", "Correct or safe fail. All-or-nothing: the task either fully happened or did not happen at all."],
    ["pass^k", "The chance that k attempts in a row are all correct. It falls fast as k grows, which is why repeated reliability matters."],
    ["Digest", "A fingerprint of every monitored row and column, used to prove a restore was exact."],
    ["Oracle", "An independent judge that compares final data with the expected change set, without reading Savepoint’s checks."],
    ["Scripted agent", "A fixed click script that can be told to fail in four ways (stop, wrong value, skip save, say done early). It makes runs repeatable and free."],
  ].map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("");
  const body = `<div class="panel"><dl class="defs">${terms}</dl></div>
  <section class="sect"><h2>Limits</h2><div class="callout warn">${icon("alert")}<div>
    <p>The agent in every test is a script that fails on purpose, not an AI model. The numbers show what Savepoint does with known failures; they do not measure any model.</p>
    <p>The “live Claude run” was simulated through the real agent loop. No model was called and nothing was spent.</p>
    <p>ClaimDesk 98 is a fake app built for safe testing. OpenMRS and iDempiere are real open-source apps run with their demo data, 5 attempts per task (10 on ClaimDesk). iDempiere’s screens were slow: 15 of its 150 runs ended in a UI timeout and were rolled back cleanly.</p>
    <p>Rollback covers the tables a task’s rules monitor, not the whole database. Apps with outside effects (email, payments) are out of scope. Idea credit: LegacyWorld (arXiv 2608.14131).</p></div></div></section>
  <section class="sect"><h2>Run it yourself</h2><div class="panel"><pre>git clone https://github.com/MayaDispeler/savepoint
cd savepoint
uv sync &amp;&amp; uv run playwright install chromium
uv run pytest -q                                  # 60 tests, no model calls
uv run python -m savepoint.bench.cli run          # ClaimDesk benchmark, about 10 minutes</pre></div></section>`;
  return pageShell({ title: "Glossary and limits", lede: "Every term used in this app, in plain words, and what the numbers do and do not show.", body });
}

// ---------- router ----------
function parseHash() {
  const h = location.hash.replace(/^#\/?/, "");
  const [path, qs] = h.split("?");
  return { parts: path.split("/").filter(Boolean), query: Object.fromEntries(new URLSearchParams(qs || "")) };
}
function render() {
  const { parts, query } = parseHash();
  let route = parts[0] || "", html;
  if (!B) { $("#main").innerHTML = `<div class="callout bad">${icon("alert")}<p><b>DATA_MISSING</b> data/bundle.js did not load.</p></div>`; return; }
  const views = { "": viewOverview, results: viewResults, benchmark: viewBenchmark, tasks: viewTasks, how: viewHow, glossary: viewGlossary };
  if (route === "run") html = viewRun(parts[1]);
  else if (route === "try") html = viewTry(query);
  else html = (views[route] || viewOverview)();
  const nav = route === "run" ? "results" : views[route] || route === "try" ? route : "";
  renderNav(nav);
  const main = $("#main"); main.innerHTML = html;
  $("#side").classList.remove("open"); $("#menu").setAttribute("aria-expanded", "false");
  if (route === "results") bindResults();
  if (route === "run") bindRun();
  if (route === "benchmark") bindBenchmark();
  if (route === "tasks") bindTasks();
  if (route === "try") bindTry(query);
  document.title = ({ "": "Savepoint: undo for AI agents", try: "Try it", results: "Test results", run: "Run detail", benchmark: "Benchmark", tasks: "Tasks and rules", how: "How it works", glossary: "Glossary and limits" }[route] || "Savepoint") + (route ? " | Savepoint" : "");
}
let lastRoute = null;
window.addEventListener("hashchange", () => { const r = parseHash().parts[0] || ""; const changed = r !== lastRoute; lastRoute = r; render(); if (changed) window.scrollTo(0, 0); });
function boot() {
  $("#mark").innerHTML = icon("undo", "l"); $("#mark-top").innerHTML = icon("undo", "l");
  $("#l-gh").innerHTML = icon("code", "s") + " Source on GitHub"; $("#l-hf").innerHTML = icon("external", "s") + " Hugging Face Space";
  $("#menu").addEventListener("click", () => { const o = $("#side").classList.toggle("open"); $("#menu").setAttribute("aria-expanded", String(o)); });
  lastRoute = parseHash().parts[0] || "";
  render();
}
boot();
