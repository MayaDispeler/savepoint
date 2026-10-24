"use strict";
// "Try it" tab: replays a REAL recorded run (data/experience.js, made by scripts/make_experience_data.py).
// The user picks what goes wrong and whether Savepoint is on; nothing here is invented or simulated by hand.
const X = window.EXPERIENCE;
const FAULTS = [
  ["none", "Nothing goes wrong", "The agent follows the instructions exactly."],
  ["stop_at", "It stops halfway", "The agent gives up before finishing."],
  ["wrong_value", "It types a wrong value", "A slipped decimal: 125000.00 instead of 1250.00."],
  ["skip_save", "It skips the last Save", "It types the note but never saves it, then says done."],
  ["done_early", "It says done too early", "It reports done after only half the work."],
];
const PROTECTION = [
  ["off", "No protection", "The agent runs on its own."],
  ["savepoint", "Savepoint on", "Checkpoints, checks, and rollback on failure."],
  ["retry", "Savepoint + retry", "On failure, restore the last good state and let the agent try again."],
];
const CHECK_TEXT = {
  amount_under_cap: "the amount stays under 100,000", no_negative_amounts: "no amount is negative",
  no_orphan_notes: "no note is left without a claim", amount_set: "the amount is 1250.00",
  note_added: "a note was added", frame: "nothing else changed",
};
const WANT = { amount: 1250.0, noteWord: "adjusted" };
const money = (n) => Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const tryState = { fault: "wrong_value", prot: "off", timer: null, shown: 0, token: 0 };

function problems(st) {
  const p = [];
  if (Math.abs(st.amount - WANT.amount) > 0.001) p.push(st.amount === X.initial.amount ? "the amount was never changed" : `the amount is ${money(st.amount)}, not ${money(WANT.amount)}`);
  if (!st.notes.some((n) => n.toLowerCase().includes(WANT.noteWord))) p.push("the note was never saved");
  return p;
}

function verdict(run) {
  const wrong = problems(run.events[run.events.length - 1].state);
  const reported = run.arm === "B" ? run.agent_status === "done" : ["committed", "retried_committed"].includes(run.savepoint);
  const cls = run.oracle;
  const d = OUT[cls];
  let head, body;
  if (cls === "VS" && run.retries) { head = "Caught, fixed, finished."; body = "Savepoint noticed the problem, restored the last good state, and the agent finished the job correctly on its second try."; }
  else if (cls === "VS") { head = "Job done correctly."; body = "The record has the new amount and the note. Savepoint checked both before accepting the agent's “done”."; }
  else if (cls === "VF") { head = "Failed safely."; body = "The job did not finish, but Savepoint restored the record to exactly how it was. Nothing is left half-done."; }
  else if (cls === "IS") { head = "The agent said “done” — but the record is wrong."; body = `Nobody was warned. In the record: ${wrong.join(" and ")}. This is the failure Savepoint exists to stop.`; }
  else { head = "Failed and left a mess."; body = `The agent stopped, and the record was left half-finished: ${wrong.join(" and ")}. Someone has to clean it up by hand.`; }
  return { cls, d, head, body, reported };
}

function recHtml(st, flash, banner) {
  const bad = problems(st);
  const changed = (a, b) => (flash && a !== b ? " flash" : "");
  return `<div class="rec" role="group" aria-label="The claims record">
    <div class="rec-title">ClaimDesk 98 — Claim ${esc(X.claim)}</div>
    <div class="rec-row"><span>Amount</span><b id="rec-amount" class="${changed(0, 1)}">${money(st.amount)}</b></div>
    <div class="rec-row"><span>Status</span><b>${esc(st.status)}</b></div>
    <div class="rec-row"><span>Notes (${st.notes.length})</span><b>${st.notes.length ? esc(st.notes.join(" · ")) : "none"}</b></div>
    <div class="rec-banner" id="rec-banner">${banner || ""}</div></div>`;
}

function viewTry() {
  if (!X) return `<div class="card err"><b>EXPERIENCE_MISSING</b> data/experience.js was not found.</div>`;
  const seg = (items, key) => items.map(([v, label, hint]) =>
    `<button type="button" class="seg-btn" data-${key}="${v}" aria-pressed="${tryState[key === "fault" ? "fault" : "prot"] === v}" title="${esc(hint)}">${esc(label)}</button>`).join("");
  return `<div class="card hero"><h2>What happens when an AI agent fails halfway?</h2>
    <p>Many companies run daily work on old software that has no API. An AI agent can click through its screens, but if it fails midway, or says “done” when it isn’t, the record is left broken and someone fixes it by hand.</p>
    <p><b>Savepoint</b> is a safety net around the agent. It saves the record before risky clicks, checks the result when the agent says “done”, and restores the record if anything is wrong.</p>
    <p class="muted">Below is the real thing, recorded. The task: <i>${esc(X.instruction)}</i> Choose what goes wrong, then switch Savepoint on and off.</p></div>
  <div class="card"><div class="ctl"><div><h3>1. What goes wrong?</h3><div class="seg" id="seg-fault" role="group" aria-label="What goes wrong">${seg(FAULTS, "fault")}</div></div>
    <div><h3>2. Protection</h3><div class="seg" id="seg-prot" role="group" aria-label="Protection">${seg(PROTECTION, "prot")}</div></div></div>
    <div class="ctl-actions"><button type="button" class="primary" id="try-play">▶ Play</button><button type="button" id="try-skip">Skip to the end</button></div></div>
  <div class="row2"><div class="card"><h3>The record</h3><div id="rec-wrap"></div></div>
    <div class="card"><h3>What happened</h3><ol class="ev" id="ev" aria-live="polite"></ol></div></div>
  <div class="card" id="try-verdict" aria-live="polite"></div>
  <div class="card"><h3>This is a replay of a real recorded run</h3>
    <p class="muted">Every step above came from the Savepoint runtime driving the real ClaimDesk 98 app (a claims screen I built for safe testing), with a scripted agent that fails on purpose — not an AI model. The same checks ran on two real open-source apps, OpenMRS (hospital records) and iDempiere (ERP). <b>600 runs, every restore exact.</b></p>
    <p><button type="button" data-goto="runs">See all 600 test results</button> <button type="button" data-goto="benchmark">See the benchmark</button></p></div>`;
}

function evHtml(e, run) {
  const li = (cls, icon, word, text) => `<li class="evi ${cls}"><span class="evw">${icon} ${word}</span><span>${text}</span></li>`;
  if (e.t === "step") return li("", "→", "Agent", esc(e.text));
  if (e.t === "checkpoint") return li("cp", "◆", "Savepoint", e.kind === "initial" ? "saved a checkpoint of the record at the start" : "saved a checkpoint before a risky click");
  if (e.t === "agent") return li("", "✓", "Agent", e.status === "done" ? "says <b>done</b>" : "<b>gives up</b>: it cannot finish");
  if (e.t === "restore") return li("rs", "↺", "Savepoint", `restored the record to ${esc(e.to)}. Rows different after restore: <b>${e.rows_differ}</b>${e.exact ? " (exact)" : ""}`);
  if (e.t === "check") {
    const bad = e.results.filter((r) => !r.passed);
    const what = e.phase === "invariant" ? "safety checks after the change" : e.phase === "goal" ? "checking the result against the task" : "checking nothing else changed";
    if (!bad.length) return li("ok", "✓", "Savepoint", `${what}: all passed`);
    return li("bad", "✕", "Savepoint", `${what}: <b>failed</b> — ${bad.map((r) => esc(CHECK_TEXT[r.id] || r.id) + (r.observed != null && r.id !== "frame" ? ` (found ${esc(Array.isArray(r.observed) ? r.observed.join(", ") : r.observed)})` : "")).join("; ")}`);
  }
  return "";
}

function shotsHtml(run) {
  if (!run.shots || run.shots.length < 2) return "";
  return `<details class="shots"><summary>Show the real screens before and after the restore</summary><div class="shotgrid">
    <figure><img alt="Screen before the restore" src="experience/${esc(run.shots[0])}"><figcaption>Before the restore</figcaption></figure>
    <figure><img alt="Screen after the restore" src="experience/${esc(run.shots[1])}"><figcaption>After the restore</figcaption></figure></div></details>`;
}

function showVerdict(run) {
  const v = verdict(run);
  const again = run.protection === "off" && v.cls !== "VS"
    ? `<p><button type="button" class="primary" id="try-on">Turn Savepoint on and replay</button></p>` : "";
  $("#try-verdict").innerHTML = `<div class="hint"><div class="tile o-${v.cls}">${svg(v.d.icon)}<span>${v.d.word}</span></div>
    <div><b>${esc(v.head)}</b><br>${esc(v.body)}</div></div>${again}${shotsHtml(run)}`;
  const on = $("#try-on"); if (on) on.addEventListener("click", () => { tryState.prot = "savepoint"; syncSeg(); playTry(false); });
}

function syncSeg() {
  document.querySelectorAll("[data-fault]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.fault === tryState.fault)));
  document.querySelectorAll("[data-prot]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.prot === tryState.prot)));
}

function playTry(instant) {
  const run = X.runs[`${tryState.fault}|${tryState.prot}`];
  clearTimeout(tryState.timer);
  const token = ++tryState.token;
  const list = $("#ev"), wrap = $("#rec-wrap");
  list.innerHTML = ""; $("#try-verdict").innerHTML = "";
  wrap.innerHTML = recHtml(run.events[0].state, false, "Original record");
  const events = run.events.slice(1);
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let i = 0, last = run.events[0].state, lastBanner = "";
  const step = () => {
    if (token !== tryState.token) return;
    if (i >= events.length) return;
    const e = events[i++];
    const html = evHtml(e, run);
    if (html) list.insertAdjacentHTML("beforeend", html);
    if (e.state) {
      const changed = JSON.stringify(e.state) !== JSON.stringify(last);
      const banner = e.t === "restore" ? "↺ Restored by Savepoint" : e.t === "checkpoint" ? "◆ Checkpoint saved" : "";
      wrap.innerHTML = recHtml(e.state, changed, banner); last = e.state;
      if (e.t === "restore") lastBanner = banner;
    }
    if (e.t === "end") { wrap.innerHTML = recHtml(e.state, false, lastBanner); showVerdict(run); return; }
    if (instant || reduce) step(); else tryState.timer = setTimeout(step, e.t === "check" || e.t === "restore" ? 1100 : 750);
  };
  step();
}

function bindTry() {
  if (!X) return;
  document.querySelectorAll("[data-fault]").forEach((b) => b.addEventListener("click", () => { tryState.fault = b.dataset.fault; syncSeg(); playTry(false); }));
  document.querySelectorAll("[data-prot]").forEach((b) => b.addEventListener("click", () => { tryState.prot = b.dataset.prot; syncSeg(); playTry(false); }));
  $("#try-play").addEventListener("click", () => playTry(false));
  $("#try-skip").addEventListener("click", () => playTry(true));
  document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => { state.view = b.dataset.goto; render(); window.scrollTo(0, 0); }));
  playTry(false);
}
