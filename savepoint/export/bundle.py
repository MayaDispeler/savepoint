"""`make export` (FR24): replay bundle for the static console. Metadata for every run, redacted screenshots for
up to 12 featured runs. Screenshots were redacted when captured; this module only copies them."""
import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from savepoint.bench import report
from savepoint.ledger.db import (
    Ledger,
    checkpoints,
    rollbacks,
    runs,
    steps,
    validations,
    workflows,
)

MAX_FEATURED = 12


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def pick_featured(all_runs: list[dict], rbs: list[dict]) -> list[str]:
    """One run per (workflow, fault, reason) that has a rollback with a screenshot, S arm first."""
    by_run = {}
    for r in rbs:
        by_run.setdefault(r["run_id"], r)
    seen, out, per_app = set(), [], {}
    order = sorted(all_runs, key=lambda r: (r["arm"] != "S", r["workflow_id"], r["trial"]))
    for r in order:
        rb = by_run.get(r["id"])
        if not rb or not rb.get("shot_after"):
            continue
        app = r["workflow_id"].split(".")[0]
        key = (app, r["fault"], rb["reason"], r["arm"])
        if key in seen or per_app.get(app, 0) >= MAX_FEATURED // 3:  # spread the featured runs over the apps
            continue
        seen.add(key)
        per_app[app] = per_app.get(app, 0) + 1
        out.append(r["id"])
        if len(out) == MAX_FEATURED:
            break
    return out


def export(ledger: Ledger, out_dir: str = "console/public") -> dict:
    out = Path(out_dir)
    shots = out / "shots"
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(parents=True)
    (out / "data").mkdir(parents=True, exist_ok=True)
    all_runs, rbs = ledger.all_runs(), ledger.rows(rollbacks)
    featured = set(pick_featured(all_runs, rbs))
    with ledger.engine.begin() as c:
        c.execute(update(runs).values(featured=False))
        for rid in featured:
            c.execute(update(runs).where(runs.c.id == rid).values(featured=True))
    for rb in rbs:
        if rb["run_id"] in featured:
            for k in ("shot_before", "shot_after"):
                src = Path(rb[k])
                dst = shots / f"{rb['id']}-{k.split('_')[1]}.png"
                shutil.copyfile(src, dst)
                rb[k] = f"shots/{dst.name}"
        else:
            rb["shot_before"] = rb["shot_after"] = None
    step_rows = ledger.rows(steps)
    bundle = {
        "schema": 1, "generated": datetime.now().isoformat(timespec="seconds"),
        "agent": "scripted fault-injecting agent (not a language model)",
        "results": report.build(ledger),
        "runs": [{**{k: _iso(v) for k, v in r.items() if k != "verify_digest"}, "featured": r["id"] in featured}
                 for r in all_runs],
        "steps": [{"run_id": s["run_id"], "idx": s["idx"], "type": (s["action"] or {}).get("type"),
                   "target": ((s["action"] or {}).get("selector") or (s["action"] or {}).get("url") or ""),
                   "risky": s["risky"], "state_changed": s["state_changed"], "t_ms": s["t_ms"]}
                  for s in step_rows],
        "checkpoints": [{k: _iso(v) for k, v in c.items() if k in ("id", "run_id", "step_idx", "kind", "took_ms")}
                        for c in ledger.rows(checkpoints)],
        "validations": [{k: _iso(v) for k, v in v.items() if k != "pk"} for v in ledger.rows(validations)],
        "rollbacks": [{k: _iso(v) for k, v in r.items()} for r in rbs],
        "workflows": [{"id": w["id"], "title": w["title"], "yaml": w["contract_yaml"]}
                      for w in ledger.rows(workflows)],
    }
    text = json.dumps(bundle, default=str, separators=(",", ":"))
    # a .js wrapper so the static page also works from file:// (no network request needed)
    (out / "data" / "bundle.js").write_text("window.BUNDLE=" + text + ";", encoding="utf-8")
    (out / "data" / "bundle.json").write_text(text, encoding="utf-8")
    return {"featured": len(featured), "bytes": len(text), "runs": len(all_runs)}
