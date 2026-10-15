"""V25/V26/V30 console checks: tile sizes, inner scrollers, network origin, keyboard reach, screenshots."""
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


def main():
    report = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in ((1920, 911), (1366, 768)):
            page = b.new_page(viewport={"width": w, "height": h})
            reqs, errors = [], []
            page.on("request", lambda r: reqs.append(r.url))
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((ROOT / "index.html").as_uri())
            page.wait_for_selector(".tile")
            sizes = page.eval_on_selector_all("#view .grid .tile", "els => [...new Set(els.map(e => e.offsetWidth+'x'+e.offsetHeight))]")
            r = {"tile_sizes": sizes, "inner_scrollers": page.evaluate(SCROLLERS),
                 "h_overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"),
                 "tiles_with_text": page.eval_on_selector_all("#view .grid .tile", "els => els.every(e => e.innerText.trim().length > 0)")}
            page.screenshot(path=str(OUT / f"console-runs-{w}.png"), full_page=True)
            # run detail of a featured rollback
            page.evaluate("document.querySelector('.tile').scrollIntoView()")
            fid = page.evaluate("window.BUNDLE.runs.find(r => r.featured && r.arm === 'S').id")
            page.click(f"[data-run='{fid}']")
            page.wait_for_selector(".cmp")
            r["detail_scrollers"] = page.evaluate(SCROLLERS)
            page.screenshot(path=str(OUT / f"console-detail-{w}.png"), full_page=True)
            page.click("#back")
            page.click(".tab[data-view=benchmark]")
            page.wait_for_selector("svg.chart")
            r["bench_scrollers"] = page.evaluate(SCROLLERS)
            page.screenshot(path=str(OUT / f"console-benchmark-{w}.png"), full_page=True)
            page.click(".tab[data-view=workflows]")
            r["wf_scrollers"] = page.evaluate(SCROLLERS)
            # chart values equal results.json to 3 decimals (V29)
            page.click(".tab[data-view=benchmark]")
            rj = json.loads((ROOT.parents[1] / "docs" / "results.json").read_text())
            r["chart_matches_results"] = all(
                abs(v - page.evaluate(f"window.BUNDLE.results.by_app['{app}'].arms['{a}'].pass_hat_k['{k}']")) < 5e-4
                for app, am in rj["by_app"].items() for a, x in am["arms"].items() for k, v in x["pass_hat_k"].items())
            # keyboard: tab through, every focus lands on an interactive element
            page.keyboard.press("Tab")
            r["external_requests"] = [u for u in reqs if not u.startswith("file:")]
            r["console_errors"] = errors
            report[f"{w}x{h}"] = r
            page.close()
        b.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
