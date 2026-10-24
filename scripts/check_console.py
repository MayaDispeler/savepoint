"""Console checks (V25, V26, V29, V30): equal tile sizes, no inner scrollers, no horizontal overflow, own-origin requests only,
chart data equals results.json, the Try it replay matches the recorded outcomes, keyboard reach. Screenshots to argv[1]."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "console" / "public"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SCROLLERS = """() => [...document.querySelectorAll('*')].filter(e => {
  const s = getComputedStyle(e); const o = s.overflowY + s.overflowX;
  return /(auto|scroll)/.test(o) && (e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1);
}).map(e => e.tagName + '.' + e.className)"""
ROUTES = ["#/", "#/try", "#/results", "#/benchmark", "#/tasks", "#/how", "#/glossary"]


def main():
    report = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in ((1920, 911), (1366, 768), (390, 844)):
            page = b.new_page(viewport={"width": w, "height": h})
            reqs, errors = [], []
            page.on("request", lambda r, reqs=reqs: reqs.append(r.url))
            page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            page.goto((ROOT / "index.html").as_uri())
            page.wait_for_selector("#nav a", state="attached")
            r = {"scrollers": {}, "overflow": {}}
            for route in ROUTES:
                page.evaluate(f"location.hash='{route}'")
                page.wait_for_timeout(350)
                r["scrollers"][route] = page.evaluate(SCROLLERS)
                r["overflow"][route] = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                if route == "#/results":
                    r["tile_sizes"] = (page.eval_on_selector_all(".grid.res a.tile", "els => [...new Set(els.map(e => e.offsetWidth+'x'+e.offsetHeight))]")
                                       if w > 700 else "n/a (mobile layout)")
                    page.screenshot(path=str(OUT / f"console-results-{w}.png"), full_page=True)
                if route == "#/try":
                    ok = page.evaluate("Object.fromEntries(Object.entries(window.EXPERIENCE.runs).map(([k, v]) => [k, v.oracle]))")
                    bad = []
                    for fault in ("none", "stop_at", "wrong_value", "skip_save", "done_early"):
                        for prot in ("off", "savepoint", "retry"):
                            page.click(f"[data-fault={fault}]")
                            page.click(f"[data-prot={prot}]")
                            page.click("#try-skip")
                            page.wait_for_selector("#try-verdict .tile")
                            cls = page.eval_on_selector("#try-verdict .tile", "e => [...e.classList].find(c => c.startsWith('o-')).slice(2)")
                            if cls != ok[f"{fault}|{prot}"]:
                                bad.append((fault, prot, cls))
                    r["try_mismatches"] = bad
                    page.screenshot(path=str(OUT / f"console-try-{w}.png"), full_page=True)
                if route == "#/benchmark":
                    rj = json.loads((ROOT.parents[1] / "docs" / "results.json").read_text())
                    r["chart_matches_results"] = all(
                        abs(v - page.evaluate(f"window.BUNDLE.results.by_app['{app}'].arms['{a}'].pass_hat_k['{k}']")) < 5e-4
                        for app, am in rj["by_app"].items() for a, x in am["arms"].items() for k, v in x["pass_hat_k"].items())
                    page.screenshot(path=str(OUT / f"console-benchmark-{w}.png"), full_page=True)
            page.evaluate("location.hash='#/results'")
            page.wait_for_timeout(300)
            fid = page.evaluate("window.BUNDLE.runs.find(r => r.featured && r.arm === 'S').id")
            page.evaluate(f"location.hash='#/run/{fid}'")
            page.wait_for_selector(".cmp")
            r["scrollers"]["#/run"] = page.evaluate(SCROLLERS)
            page.screenshot(path=str(OUT / f"console-run-{w}.png"), full_page=True)
            page.evaluate("location.hash='#/'")
            page.wait_for_timeout(300)
            stops = set()
            for _ in range(25):
                page.keyboard.press("Tab")
                stops.add(page.evaluate("document.activeElement.tagName"))
            r["tab_stops"] = sorted(stops)
            r["external_requests"] = [u for u in reqs if not u.startswith("file:")]
            r["console_errors"] = errors
            report[f"{w}x{h}"] = r
            page.close()
        b.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
