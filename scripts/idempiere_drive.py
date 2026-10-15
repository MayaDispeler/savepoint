"""Drive the iDempiere ZK UI from a JSON action list (discovery tool). Usage: idempiere_drive.py <actions.json>"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DUMP = """() => [...document.querySelectorAll('input,select,textarea,button,a.z-toolbarbutton,[role=button],.z-tab,.z-menuitem,label')]
  .filter(e => e.offsetParent !== null).slice(0, 90).map(e => (e.tagName + '|' + (e.id||'') + '|' + (e.className||'').toString().slice(0,32) + '|' + (e.title||'') + '|' + (e.innerText||e.value||'').trim().slice(0,36)))"""


def main():
    actions = json.loads(Path(sys.argv[1]).read_text())
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
        pg.set_default_timeout(20000)
        pg.goto("http://localhost:8080/webui/")
        pg.wait_for_selector("input[type=password]")
        pg.wait_for_timeout(2000)
        pg.locator("input[type=text]").first.fill("GardenAdmin")
        pg.locator("input[type=password]").first.fill("GardenAdmin")
        pg.click("button:has-text('OK')")
        pg.wait_for_function("document.querySelector('.desktop-hometab') || [...document.querySelectorAll('input')].some(i => i.value === 'GardenWorld Admin')", timeout=60000)
        if not pg.locator(".desktop-hometab").count():
            pg.wait_for_timeout(1500)
            pg.click("button.btn-ok")
        pg.wait_for_selector(".desktop-hometab", timeout=60000)
        pg.wait_for_timeout(2000)
        for a in actions:
            k, v = next(iter(a.items()))
            print('>>', k, str(v)[:60], flush=True)
            try:
                if k == "click_text":
                    pg.locator(f"text='{v}' >> visible=true").first.click()
                elif k == "click":
                    pg.locator(v).first.click()
                elif k == "wait":
                    pg.wait_for_timeout(v)
                elif k == "fill_label":
                    pg.locator(f"xpath=//label[normalize-space()='{v[0]}']/following::input[1]").first.fill(v[1])
                elif k == "type":
                    pg.keyboard.type(v)
                elif k == "key":
                    pg.keyboard.press(v)
                elif k == "shot":
                    pg.screenshot(path=f"/tmp/idd-{v}.png")
                elif k == "dump":
                    print(f"--- dump {v}")
                    print("\n".join(pg.evaluate(DUMP)))
                elif k == "text":
                    print(f"--- text {v}:", pg.inner_text("body")[:900].replace("\n", " | "))
            except Exception as e:  # noqa: BLE001
                print("ACTION FAILED", a, str(e)[:160])
                pg.screenshot(path="/tmp/idd-fail.png")
                break
        b.close()


if __name__ == "__main__":
    main()
