"""Discovery helper for real apps: open URLs headless, dump interactive elements, save a screenshot.
Usage: uv run python scripts/explore.py <outdir> <login-steps-json|-> <url> [<url> ...]"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DUMP = """() => [...document.querySelectorAll('input,select,textarea,button,a[href],[role=button],[role=tab]')]
  .filter(e => e.offsetParent !== null).slice(0, 120).map(e => ({
    tag: e.tagName.toLowerCase(), id: e.id, name: e.getAttribute('name'), type: e.getAttribute('type'),
    text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().slice(0, 50),
    href: (e.getAttribute('href') || '').slice(0, 90)}))"""


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    a = sys.argv[2]
    login = None if a == "-" else json.loads(Path(a[1:]).read_text() if a.startswith("@") else a)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
        page.set_default_timeout(20000)
        for step in login or []:
            t = step["type"]
            if t == "goto":
                page.goto(step["url"])
            elif t == "fill":
                page.fill(step["selector"], step["value"])
            elif t == "click":
                page.click(step["selector"])
            elif t == "wait":
                page.wait_for_timeout(step["ms"])
        for i, url in enumerate(sys.argv[3:]):
            if url.startswith("click:"):
                page.click(url[6:])
                page.wait_for_timeout(1500)
            else:
                page.goto(url)
                page.wait_for_timeout(2500)
            name = f"{i:02d}"
            page.screenshot(path=str(out / f"{name}.png"))
            print(f"--- {name} {page.url} | {page.title()}")
            for e in page.evaluate(DUMP):
                print(json.dumps(e, ensure_ascii=False))
        b.close()


if __name__ == "__main__":
    main()
