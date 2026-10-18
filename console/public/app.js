"use strict";
// Static replay console. Reads window.BUNDLE (data/bundle.js); makes no network request (FR28).
const B = window.BUNDLE;
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ICON = {
  check: '<path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" stroke-width="2"/>',
  undo: '<path d="M4 6h6a3 3 0 010 6H6M4 6l2.5-2.5M4 6l2.5 2.5" fill="none" stroke="currentColor" stroke-width="2"/>',
  bang: '<path d="M8 3v6M8 12v1.5" fill="none" stroke="currentColor" stroke-width="2.2"/>',
  cross: '<path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="2"/>',
  broken: '<path d="M3 8h3M10 8h3M8 4l-1 3M9 9l-1 3" fill="none" stroke="currentColor" stroke-width="2"/>',
};
const OUT = {
  VS: { icon: "check", word: "Done", long: "valid success" },
  VF: { icon: "undo", word: "Clean fail", long: "clean failure, state untouched" },
  IS: { icon: "bang", word: "False done", long: "invalid success, said done but state is wrong" },
  IF: { icon: "cross", word: "Dirty fail", long: "invalid failure, partial change left behind" },
  RF: { icon: "broken", word: "Restore failed", long: "restore was not exact, quarantined" },
};
const ARMS = ["B", "S", "R"];
const ARM_NAME = { B: "B baseline, no Savepoint", S: "S atomic", R: "R savepoint_retry" };
const pct = (x) => (x == null ? "n/a" : (x * 100).toFixed(1) + "%");
const outcome = (r) => (r.sp_outcome === "rollback_failed" ? "RF" : r.oracle);
const svg = (n) => `<svg viewBox="0 0 16 16" aria-hidden="true">${ICON[n]}</svg>`;
const state = { view: "runs", runId: null };

function tile(r) {
  const o = outcome(r), d = OUT[o];
  const how = r.sp_outcome === "none" ? "no Savepoint" : r.sp_outcome.replace("_", " ");
  return `<button class="tile o-${o}" data-run="${r.id}" aria-label="Trial ${r.trial}, arm ${r.arm}, ${d.word.toLowerCase()}, ${how}">${svg(d.icon)}<span>${d.word}</span></button>`;
}

function summary() {
  const by = B.results.by_app || {};
  const fid = B.results.fidelity;
  const cards = Object.entries(by).map(([app, R]) => {
    const Bx = R.arms.B || {}, S = R.arms.S || {};
    return [app, `B ${pct(Bx.atomicity)} → S ${pct(S.atomicity)}`, `atomicity · false done ${Bx.IS ?? 0} → ${S.IS ?? 0} of ${S.n ?? 0}`];
  });
  cards.push(["Rollbacks exact", `${fid.exact} / ${fid.restores}`, "digest equals checkpoint after restore"]);
  $("#summary").innerHTML = cards.map(([t, v, h]) => `<div class="stat"><span>${esc(t)}</span><b>${v}</b><span>${h}</span></div>`).join("");
  $("#meta").textContent = `${B.agent} · ${B.runs.length} runs · generated ${B.generated}`;
}

function viewRuns() {
  const wfs = [...new Set(B.runs.map((r) => r.workflow_id))].sort();
  const quarantined = B.runs.filter((r) => r.quarantined);
  let h = `<div class="card"><h2>Runs</h2><p class="muted">Every run is one tile of the same size. Each tile has an icon and a word, so colour is never the only signal.</p><div class="hint">` +
    Object.entries(OUT).map(([k, d]) => `<div class="tile o-${k}" title="${esc(d.long)}">${svg(d.icon)}<span>${d.word}</span></div>`).join("") + "</div></div>";
  if (quarantined.length) {
    h += `<div class="card err"><h3>Quarantined (${quarantined.length})</h3><div class="grid" style="grid-template-columns:repeat(10,minmax(0,1fr))">${quarantined.map(tile).join("")}</div></div>`;
  }
  const apps = [...new Set(B.runs.map((r) => r.workflow_id.split(".")[0]))];
  for (const app of apps) {
    const appRuns = B.runs.filter((r) => r.workflow_id.startsWith(app + "."));
    const T = 10; // same column count for every app so all tiles are one size
    const cols = `style="grid-template-columns:260px repeat(${T},minmax(0,1fr))"`;
    h += `<h2 style="margin:24px 0 8px">${esc(APP_NAME[app] || app)}</h2>`;
    for (const arm of ARMS) {
      const runs = appRuns.filter((r) => r.arm === arm);
      if (!runs.length) continue;
      h += `<div class="card"><h3>Arm ${esc(ARM_NAME[arm])}</h3><div class="grid" ${cols}><div class="muted">Workflow \ trial</div>${[...Array(T).keys()].map((i) => `<div class="muted" style="text-align:center">${i + 1}</div>`).join("")}`;
      for (const wf of wfs.filter((w) => w.startsWith(app + "."))) {
        h += `<div class="wf">${esc(wf)}</div>`;
        for (let t = 1; t <= T; t++) {
          const r = runs.find((x) => x.workflow_id === wf && x.trial === t);
          h += r ? `<div>${tile(r)}</div>` : "<div></div>";
        }
      }
      h += "</div></div>";
    }
  }
  return h;
}

function viewRun(id) {
  const r = B.runs.find((x) => x.id === id);
  if (!r) return `<div class="card err">Run not found.</div>`;
  const o = outcome(r), d = OUT[o];
  const steps = B.steps.filter((s) => s.run_id === id).sort((a, b) => a.idx - b.idx);
  const cps = B.checkpoints.filter((c) => c.run_id === id);
  const vals = B.validations.filter((v) => v.run_id === id);
  const rbs = B.rollbacks.filter((x) => x.run_id === id);
  const cpAt = (i) => cps.filter((c) => c.step_idx === i);
  let tl = `<li class="cp"><span class="dia"></span>S0 checkpoint</li>`;
  for (const s of steps) {
    for (const c of cpAt(s.idx).filter((c) => c.kind !== "initial")) tl += `<li class="cp"><span class="dia"></span>checkpoint before step ${s.idx}</li>`;
    tl += `<li>${s.state_changed ? '<span class="dot" title="state changed"></span>' : ""}<b>${s.idx}</b> ${esc(s.type)} <span class="muted">${esc(String(s.target).slice(-40))}</span></li>`;
  }
  for (const rb of rbs) tl += `<li class="end">↺ restored to ${esc(rb.checkpoint_id.split(":")[1] === "0" ? "S0" : "step " + rb.checkpoint_id.split(":")[1])} (${esc(rb.reason.replace("_", " "))})</li>`;
  if (r.sp_outcome === "committed" || r.sp_outcome === "retried_committed") tl += `<li class="end">✓ committed</li>`;
  const checks = vals.length ? vals.map((v) => `<div class="chk ${v.passed ? "" : "bad"}"><b>${v.passed ? "Pass" : "Fail"}</b><span>${esc(v.check_id)} (${esc(v.phase)})${v.passed ? "" : ` expected ${esc(JSON.stringify(v.expected))}, got ${esc(JSON.stringify(v.observed))}`}</span></div>`).join("") : `<p class="muted">${r.arm === "B" ? "Arm B runs no validators." : "No validator ran: the run ended before any state change or done claim, so Savepoint only restored the checkpoint."}</p>`;
  let rbHtml = "";
  for (const rb of rbs) {
    rbHtml += `<h3>Rollback · ${esc(rb.reason.replace("_", " "))} · from step ${rb.from_step}</h3>`;
    if (rb.shot_before && rb.shot_after) {
      rbHtml += `<div class="cmp" id="cmp" style="--pos:50%"><img alt="Screen before restore" src="${esc(rb.shot_before)}"><img class="after" alt="Screen after restore" src="${esc(rb.shot_after)}"><div class="bar"></div></div><input type="range" min="0" max="100" value="50" id="slider" aria-label="Compare before and after">`;
    } else rbHtml += `<p class="muted">Screenshots are kept for featured runs only.</p>`;
    rbHtml += `<p>Rows differ after restore: <b>${rb.rows_differ}</b> · ${rb.exact ? "exact" : "NOT exact"} · restore ${rb.restore_ms} ms · screen diff ${rb.pixel_diff_pct}%</p>`;
  }
  return `<div class="card"><button id="back">← Runs</button>
    <h2 style="margin-top:12px">${esc(r.workflow_id)} · arm ${r.arm} · trial ${r.trial}</h2>
    <div class="hint"><div class="tile o-${o}">${svg(d.icon)}<span>${d.word}</span></div><div>${esc(d.long)}<br><span class="muted">fault: ${esc(r.fault)} · Savepoint: ${esc(r.sp_outcome.replace("_", " "))} · ${r.steps} steps · ${(r.wall_ms / 1000).toFixed(1)} s · model cost $${(r.cost_usd || 0).toFixed(2)}${r.retries ? ` · ${r.retries} retry` : ""}</span></div></div></div>
    <div class="card"><h3>Timeline</h3><ol class="tl" aria-label="Steps in reading order">${tl}</ol></div>
    <div class="row2"><div class="card">${rbHtml || "<h3>Rollback</h3><p class=\"muted\">No rollback in this run.</p>"}</div><div class="card"><h3>Validator checklist</h3>${checks}</div></div>`;
}

function line(points, cls) { return points.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" "); }

const APP_NAME = { claimdesk: "ClaimDesk 98 (synthetic claims app)", openmrs: "OpenMRS 2.12 (real hospital record system)", idempiere: "iDempiere 13 (real ERP)" };
function viewBenchmark() {
  const by = B.results.by_app || { all: B.results };
  return Object.entries(by).map(([app, R]) => benchApp(app, R)).join("");
}

function benchApp(app, R) {
  const arms = R.arms, W = 720, H = 300, L = 48, Rr = 90, T = 16, Bt = 36;
  const K = Math.max(2, ...Object.values(arms).map((a) => Object.keys(a.pass_hat_k).length));
  const x = (k) => L + ((k - 1) / (K - 1)) * (W - L - Rr), y = (v) => T + (1 - v) * (H - T - Bt);
  const style = { B: 'stroke="#14181D" stroke-dasharray="6 4"', S: 'stroke="#2447C9"', R: 'stroke="#2447C9" stroke-dasharray="2 3"' };
  let g = "";
  for (let v = 0; v <= 1.001; v += 0.25) g += `<line x1="${L}" x2="${W - Rr}" y1="${y(v)}" y2="${y(v)}" stroke="#DCE0E6"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(2)}</text>`;
  for (let k = 1; k <= K; k++) g += `<text x="${x(k)}" y="${H - 14}" text-anchor="middle">${k}</text>`;
  g += `<text x="${(L + W - Rr) / 2}" y="${H}" text-anchor="middle">k fresh trials in a row</text>`;
  const same = (a, b) => arms[a] && arms[b] && JSON.stringify(arms[a].pass_hat_k) === JSON.stringify(arms[b].pass_hat_k);
  const labelled = [];
  for (const a of ["S", "R", "B"]) { // B last so its dashed ink line stays visible on top of S
    const ph = arms[a]?.pass_hat_k; if (!ph) continue;
    const pts = Object.keys(ph).map((k) => [x(+k), y(ph[k])]);
    g += `<path d="${line(pts)}" fill="none" stroke-width="${a === "B" ? 2 : 3.5}" ${style[a]}/>`;
    g += pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="${a === "B" ? 2.5 : 3.5}" fill="${a === "B" ? "#14181D" : "#2447C9"}"/>`).join("");
    const last = pts[pts.length - 1];
    labelled.push([a === "B" && same("B", "S") ? "B = S" : a, last]);
  }
  for (const [t, last] of labelled) { if (t === "S" && same("B", "S")) continue; g += `<text class="lab" x="${last[0] + 8}" y="${last[1] + 4}">${t}</text>`; }
  let bars = "";
  ARMS.forEach((a, i) => {
    const m = arms[a]; if (!m) return;
    const yy = 20 + i * 44, w = W - 220, [lo, hi] = m.atomicity_ci95;
    bars += `<text class="lab" x="0" y="${yy + 14}">${a}</text><rect x="30" y="${yy}" width="${w}" height="20" fill="#F5F6F8" stroke="#DCE0E6"/><rect x="30" y="${yy}" width="${w * m.atomicity}" height="20" fill="${a === "B" ? "#14181D" : "#2447C9"}"/><line x1="${30 + w * lo}" x2="${30 + w * hi}" y1="${yy + 10}" y2="${yy + 10}" stroke="#B3261E" stroke-width="3"/><text x="${40 + w}" y="${yy + 15}">${pct(m.atomicity)} (${pct(lo)} to ${pct(hi)})</text>`;
  });
  const rows = ARMS.filter((a) => arms[a]).map((a) => { const m = arms[a]; return `<tr><td>${esc(ARM_NAME[a])}</td><td class="num">${m.n}</td><td class="num">${m.VS}</td><td class="num">${m.VF}</td><td class="num">${m.IS}</td><td class="num">${m.IF}</td><td class="num">${pct(m.valid_success)}</td><td class="num">${pct(m.atomicity)}</td></tr>`; }).join("");
  const c = R.catch, t = R.timings, f = R.fidelity;
  return `<h2 style="margin:24px 0 8px">${esc(APP_NAME[app] || app)}</h2><div class="card"><h2>pass^k</h2><p class="muted">Mean over workflows of the chance that k fresh trials all succeed. Dashed ink = B baseline, solid blue = S atomic, dotted blue = R retry. B and S overlap when they finish the same runs: Savepoint changes what the failed runs leave behind (see atomicity below), not how many succeed.</p>
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="pass^k by arm">${g}</svg></div>
    <div class="card"><h2>Atomicity with Wilson 95% interval</h2><svg class="chart" viewBox="0 0 ${W} 150" role="img" aria-label="Atomicity by arm">${bars}</svg></div>
    <div class="card"><h2>Outcome table</h2><table><thead><tr><th>Arm</th><th class="num">N</th><th class="num">Done (VS)</th><th class="num">Clean fail (VF)</th><th class="num">False done (IS)</th><th class="num">Dirty fail (IF)</th><th class="num">Valid success</th><th class="num">Atomicity</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="card"><h2>Metrics</h2><table><tbody>
      <tr><th>Catch rate (arm S)</th><td>${pct(c.catch_rate)} (${c.caught} of ${c.false_claims} false done claims)</td></tr>
      <tr><th>False-alarm rate (arm S)</th><td>${pct(c.false_alarm_rate)} (${c.false_alarms} of ${c.true_claims})</td></tr>
      <tr><th>Restore fidelity</th><td>${f.exact} of ${f.restores} exact</td></tr>
      <tr><th>Checkpoint p95 / restore p95</th><td>${t.checkpoint_p95_ms} ms / ${t.restore_p95_ms} ms (${t.checkpoints} checkpoints)</td></tr>
      <tr><th>Checkpoint and restore share of run time</th><td>${pct(R.overhead.checkpoint_restore_share_of_wall)}</td></tr></tbody></table>
    <p class="muted">Assumptions: ${esc(B.agent)}; ${esc(APP_NAME[app] || app)}; ${arms.B ? arms.B.workflows : "?"} workflows x ${arms.B ? arms.B.trials_per_workflow : "?"} trials per arm; faults injected on a fixed schedule, paired across arms. These numbers show runtime behaviour on a known failure mix. They are not a model's reliability.</p></div>`;
}

function viewWorkflows() {
  return B.workflows.sort((a, b) => a.id.localeCompare(b.id)).map((w) => {
    const rs = B.runs.filter((r) => r.workflow_id === w.id);
    const vs = (arm) => rs.filter((r) => r.arm === arm && r.oracle === "VS").length + "/" + rs.filter((r) => r.arm === arm).length;
    return `<div class="card"><h3>${esc(w.id)}</h3><p class="muted">${esc(w.title)} · valid success B ${vs("B")} · S ${vs("S")} · R ${vs("R")}</p><pre>${esc(w.yaml)}</pre></div>`;
  }).join("");
}

function render() {
  document.querySelectorAll(".tab").forEach((b) => {
    const on = b.dataset.view === (state.view === "run" ? "runs" : state.view);
    if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
  });
  const v = $("#view");
  v.innerHTML = state.view === "run" ? viewRun(state.runId) : state.view === "benchmark" ? viewBenchmark() : state.view === "workflows" ? viewWorkflows() : viewRuns();
  v.querySelectorAll("[data-run]").forEach((b) => b.addEventListener("click", () => { state.view = "run"; state.runId = b.dataset.run; render(); window.scrollTo(0, 0); v.focus(); }));
  const back = $("#back"); if (back) back.addEventListener("click", () => { state.view = "runs"; render(); });
  const sl = $("#slider"); if (sl) sl.addEventListener("input", () => $("#cmp").style.setProperty("--pos", sl.value + "%"));
}

function boot() {
  if (!B) { $("#view").innerHTML = '<div class="empty"><h2>No runs yet</h2><p class="muted">Run <code>make export</code> to build data/bundle.js.</p></div>'; return; }
  if (B.schema !== 1) { $("#view").innerHTML = `<div class="card err"><b>BUNDLE_SCHEMA</b> field "schema": expected 1, got ${esc(B.schema)}.</div>`; return; }
  summary();
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => { state.view = b.dataset.view; render(); }));
  render();
}
boot();
