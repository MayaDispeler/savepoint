"""Probe the iDempiere ZK UI: login, then dump what is visible after each step."""
import json

from playwright.sync_api import sync_playwright

DUMP = """() => [...document.querySelectorAll('input,select,textarea,button,a,[role=button],[role=treeitem],.z-tab,.z-menuitem')]
  .filter(e => e.offsetParent !== null).slice(0, 60).map(e => (e.tagName + '|' + (e.id||'') + '|' + (e.className||'').toString().slice(0,40) + '|' + (e.innerText||e.value||e.title||'').trim().slice(0,40)))"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
    pg.set_default_timeout(30000)
    pg.goto("http://localhost:8080/webui/")
    pg.wait_for_selector("input[type=password]")
    pg.locator("input[type=text]").first.fill("GardenAdmin")
    pg.locator("input[type=password]").first.fill("GardenAdmin")
    pg.click("button:has-text('OK')")
    pg.wait_for_timeout(4000)
    pg.screenshot(path="/tmp/id-after-login.png")
    print("after login:", json.dumps(pg.evaluate(DUMP), indent=0)[:1800])
    pg.click("button.btn-ok")
    pg.wait_for_timeout(8000)
    pg.screenshot(path="/tmp/id-desktop.png")
    print("desktop:", json.dumps(pg.evaluate(DUMP), indent=0)[:2500])
    b.close()
