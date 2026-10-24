"use strict";
// "Try it": replays a REAL recorded run (data/experience.js, made by scripts/make_experience_data.py).
// The visitor picks what goes wrong and whether Savepoint is on; nothing is staged by hand.
const FAULTS = [
  ["none", "Nothing goes wrong", "The agent follows the instructions exactly."],
  ["stop_at", "It stops halfway", "The agent gives up before finishing the job."],
  ["wrong_value", "It types a wrong value", "A slipped decimal: 125000.00 instead of 1250.00."],
  ["skip_save", "It skips the last Save", "It types the note but never saves it, then says done."],
  ["done_early", "It says done too early", "It reports done after doing only half the work."],
];
const PROTECTION = [
  ["off", "No protection", "The agent runs on its own, with nothing watching."],
  ["savepoint", "Savepoint", "Saves checkpoints, checks the result, and restores on any failure."],
  ["retry", "Savepoint + retry", "Same, and the agent gets another try from the last good state."],
];
const CHECK_TEXT = {
  amount_under_cap: "the amount stays under 100,000", no_negative_amounts: "no amount is negative",
  no_orphan_notes: "no note is left without a claim", amount_set: "the amount is 1250.00",
  note_added: "a note was added", frame: "nothing else changed",
};
const WANT = { amount: 1250.0, noteWord: "adjusted" };
const money = (n) => Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const tryState = { fault: "skip_save", prot: "off", timer: null, token: 0 };

function problems(st) {
  const p = [];
  if (Math.abs(st.amount - WANT.amount) > 0.001) p.push(st.amount === X.initial.amount ? "the amount was never changed" : `the amount is ${money(st.amount)}, not ${money(WANT.amount)}`);
  if (!st.notes.some((n) => n.toLowerCase().includes(WANT.noteWord))) p.push("the note was never saved");
  return p;
}

function verdict(run) {
  const wrong = problems(run.events[run.events.length - 1].state);
  const cls = run.oracle;
  let head, body, notice;
  if (cls === "VS" && run.retries) { head = "Caught, undone, and finished correctly."; body = "Savepoint noticed the problem, restored the last good state, and the agent finished the job on its second try."; notice = "Without retry this run would have ended as a safe fail. Retry turned it into a correct result."; }
  else if (cls === "VS") { head = "The job was done correctly."; body = "The record has the new amount and the note. Savepoint checked both before accepting the agent’s “done”."; notice = "Nothing went wrong here, so Savepoint stayed out of the way. Pick a failure above to see it act."; }
  else if (cls === "VF") { head = "It failed, but safely."; body = "The job did not finish, but Savepoint restored the record to exactly how it was. Nothing is left half-done."; notice = "Compare the record before and after: they are identical. Rows different after restore: 0."; }
  else if (cls === "IS") { head = "The agent said “done”, but the record is wrong."; body = `Nobody was warned. In the record: ${wrong.join(" and ")}. This is the failure Savepoint exists to stop.`; notice = "Turn Savepoint on and replay the same failure to see the difference."; }
  else { head = "It failed and left a mess."; body = `The agent stopped and the record is half-finished: ${wrong.join(" and ")}. Someone has to clean it up by hand.`; notice = "Turn Savepoint on and replay the same failure to see the difference."; }
  return { cls, head, body, notice };
}

function recHtml(st, flash, banner) {
  const prev = X.initial;
  return `<div class="rec" role="group" aria-label="The claims record">
    <div class="rec-title">ClaimDesk 98 — Claim ${esc(X.claim)}</div>
    <div class="rec-row"><span>Amount</span><b class="${flash && st.amount !== prev.amount ? "flash" : ""}">${money(st.amount)}</b></div>
    <div class="rec-row"><span>Status</span><b>${esc(st.status)}</b></div>
    <div class="rec-row"><span>Notes (${st.notes.length})</span><b class="${flash && st.notes.length ? "flash" : ""}">${st.notes.length ? esc(st.notes.join(" · ")) : "none"}</b></div>
    <div class="rec-banner">${banner || ""}</div></div>`;
}

function viewTry(query) {
  if (!X) return pageShell({ title: "Try it", body: `<div class="callout bad">${icon("alert")}<p><b>EXPERIENCE_MISSING</b> data/experience.js did not load.</p></div>` });
  if (query && FAULTS.some((f) => f[0] === query.fault)) tryState.fault = query.fault;
  if (query && PROTECTION.some((p) => p[0] === query.prot)) tryState.prot = query.prot;
  const seg = (items, key) => items.map(([v, label]) => `<button type="button" data-${key}="${v}" aria-pressed="${tryState[key] === v}">${esc(label)}</button>`).join("");
  const body = `
  <div class="callout">${icon("info")}<div><p><b>The task the agent was given</b></p><p>${esc(X.instruction)}</p><p class="muted">Below is a recording of the real Savepoint software running this task on a real (fake-data) claims app. You choose what goes wrong. The replay is real, not an animation.</p></div></div>
  <section class="sect"><div class="ctl">
    <div class="field"><span class="label">Step 1. What goes wrong?</span><div class="seg" id="seg-fault" role="group" aria-label="What goes wrong">${seg(FAULTS, "fault")}</div><span class="hintline" id="hint-fault"></span></div>
    <div class="field"><span class="label">Step 2. Protection</span><div class="seg" id="seg-prot" role="group" aria-label="Protection">${seg(PROTECTION, "prot")}</div><span class="hintline" id="hint-prot"></span></div></div>
    <div class="actions"><button type="button" class="btn primary" id="try-play">${icon("play", "s")} Play</button><button type="button" class="btn" id="try-skip">Skip to the end</button></div></section>
  <section class="sect"><div class="two">
    <div><h2>The record</h2><p class="lede" style="margin-bottom:12px">What is stored in the app. It changes as the agent works.</p><div id="rec-wrap"></div></div>
    <div><h2>What happened</h2><p class="lede" style="margin-bottom:12px">Blue lines are Savepoint. Grey lines are the agent. Green and red lines are checks.</p><ol class="ev" id="ev" aria-live="polite"></ol></div></div></section>
  <section class="sect"><div class="panel" id="try-verdict" aria-live="polite"><p class="muted" style="margin:0">The result appears here when the replay finishes.</p></div></section>
  <section class="sect"><h2>Keep going</h2><div class="actions" style="margin-top:8px"><a class="btn" href="#/results">See all 600 test runs ${icon("arrowRight", "s")}</a><a class="btn" href="#/benchmark">See the numbers ${icon("arrowRight", "s")}</a><a class="btn" href="#/how">How it works ${icon("arrowRight", "s")}</a></div>
    <p class="hintline" style="margin-top:12px">The agent here is a script that fails on purpose, not an AI model. The same checks ran on two real open-source apps, OpenMRS and iDempiere, in the test results.</p></section>`;
  return pageShell({ title: "Try it: break an AI agent, then undo it", lede: "Pick a failure, switch Savepoint on or off, and watch what happens to the data.", body });
}

function evHtml(e) {
  const li = (cls, ic, word, text) => `<li class="evi ${cls}"><span class="evw">${icon(ic, "s")}${word}</span><span>${text}</span></li>`;
  if (e.t === "step") return li("", "arrowRight", "Agent", esc(e.text));
  if (e.t === "checkpoint") return li("cp", "diamond", "Savepoint", e.kind === "initial" ? "saved a checkpoint of the record at the start" : "saved a checkpoint before a risky click");
  if (e.t === "agent") return li("", e.status === "done" ? "check" : "x", "Agent", e.status === "done" ? "says <b>done</b>" : "<b>gives up</b>: it cannot finish");
  if (e.t === "restore") return li("rs", "undo", "Savepoint", `restored the record to ${esc(e.to)}. Rows different after restore: <b>${e.rows_differ}</b>${e.exact ? " (exact)" : ""}`);
  if (e.t === "check") {
    const bad = e.results.filter((r) => !r.passed);
    const what = e.phase === "invariant" ? "safety checks after the change" : e.phase === "goal" ? "checking the result against the task" : "checking that nothing else changed";
    if (!bad.length) return li("ok", "check", "Check passed", `${what}: all passed`);
    return li("bad", "x", "Check failed", `${what} — ${bad.map((r) => esc(CHECK_TEXT[r.id] || r.id) + (r.observed != null && r.id !== "frame" ? ` (found ${esc(Array.isArray(r.observed) ? r.observed.join(", ") : r.observed)})` : "")).join("; ")}`);
  }
  return "";
}

function shotsHtml(run) {
  if (!run.shots || run.shots.length < 2) return "";
  return `<details class="disc" style="margin-top:12px"><summary>${icon("chevronDown", "s")} Show the real screens before and after the restore</summary><div class="body"><div class="shotgrid">
    <figure><img alt="Screen before the restore" src="experience/${esc(run.shots[0])}"><figcaption>Before the restore</figcaption></figure>
    <figure><img alt="Screen after the restore" src="experience/${esc(run.shots[1])}"><figcaption>After the restore</figcaption></figure></div></div></details>`;
}

function showVerdict(run) {
  const v = verdict(run);
  const again = run.protection === "off" && v.cls !== "VS" ? `<div class="actions" style="margin-top:12px"><button type="button" class="btn primary" id="try-on">Turn Savepoint on and replay this failure</button></div>` : "";
  $("#try-verdict").innerHTML = `<div class="verdict"><div class="tile o-${v.cls}">${icon(OUT[v.cls].icon)}<span>${OUT[v.cls].word}</span></div>
    <div><h3>${esc(v.head)}</h3><p style="margin:4px 0 0">${esc(v.body)}</p><p class="hintline" style="margin:6px 0 0">${esc(v.notice)}</p></div></div>${again}${shotsHtml(run)}`;
  const on = $("#try-on"); if (on) on.addEventListener("click", () => { tryState.prot = "savepoint"; syncSeg(); playTry(false); });
}

function syncSeg() {
  $$("[data-fault]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.fault === tryState.fault)));
  $$("[data-prot]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.prot === tryState.prot)));
  $("#hint-fault").textContent = FAULTS.find((f) => f[0] === tryState.fault)[2];
  $("#hint-prot").textContent = PROTECTION.find((p) => p[0] === tryState.prot)[2];
  history.replaceState(null, "", `#/try?fault=${tryState.fault}&prot=${tryState.prot}`);
}

function playTry(instant) {
  const run = X.runs[`${tryState.fault}|${tryState.prot}`];
  clearTimeout(tryState.timer);
  const token = ++tryState.token;
  const list = $("#ev"), wrap = $("#rec-wrap");
  list.innerHTML = ""; $("#try-verdict").innerHTML = `<p class="muted" style="margin:0">Replaying…</p>`;
  wrap.innerHTML = recHtml(run.events[0].state, false, "Original record");
  const events = run.events.slice(1);
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let i = 0, last = run.events[0].state, lastBanner = "";
  const step = () => {
    if (token !== tryState.token || i >= events.length) return;
    const e = events[i++];
    const html = evHtml(e);
    if (html) list.insertAdjacentHTML("beforeend", html);
    if (e.state) {
      const changed = JSON.stringify(e.state) !== JSON.stringify(last);
      const banner = e.t === "restore" ? `${icon("undo", "s")} Restored by Savepoint` : e.t === "checkpoint" ? `${icon("diamond", "s")} Checkpoint saved` : "";
      wrap.innerHTML = recHtml(e.state, changed, banner); last = e.state;
      if (e.t === "restore") lastBanner = banner;
    }
    if (e.t === "end") { wrap.innerHTML = recHtml(e.state, false, lastBanner); showVerdict(run); return; }
    if (instant || reduce) step(); else tryState.timer = setTimeout(step, e.t === "check" || e.t === "restore" ? 1100 : 700);
  };
  step();
}

function bindTry() {
  if (!X) return;
  $$("[data-fault]").forEach((b) => b.addEventListener("click", () => { tryState.fault = b.dataset.fault; syncSeg(); playTry(false); }));
  $$("[data-prot]").forEach((b) => b.addEventListener("click", () => { tryState.prot = b.dataset.prot; syncSeg(); playTry(false); }));
  $("#try-play").addEventListener("click", () => playTry(false));
  $("#try-skip").addEventListener("click", () => playTry(true));
  syncSeg();
  playTry(false);
}
