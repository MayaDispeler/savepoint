"""Probe: complete the OpenMRS registration wizard end to end, report selectors and the resulting URL."""
import json

from playwright.sync_api import sync_playwright

B = "http://localhost:8080/openmrs"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
    pg.set_default_timeout(15000)
    pg.goto(B + "/login.htm"); pg.fill("#username", "admin"); pg.fill("#password", "Admin123")
    pg.click("#sessionLocation li:first-child"); pg.click("#loginButton"); pg.wait_for_timeout(2500)
    pg.goto(B + "/registrationapp/registerPatient.page?appId=referenceapplication.registrationapp.registerPatient")
    pg.wait_for_timeout(2500)
    pg.fill("input[name=givenName]", "Asha"); pg.fill("input[name=familyName]", "Rao"); pg.click("#next-button")
    pg.select_option("#gender-field", "Female"); pg.click("#next-button")
    pg.fill("#birthdateDay-field", "12"); pg.select_option("#birthdateMonth-field", "4"); pg.fill("#birthdateYear-field", "1990"); pg.click("#next-button")
    for _ in range(8):
        vis = pg.evaluate("[...document.querySelectorAll('input,select,button')].filter(e=>e.offsetParent).map(e=>e.id||e.name)")
        print("visible:", vis)
        for fid, val in (("address1", "12 Test Street"), ("cityVillage", "Pune"), ("stateProvince", "MH"), ("country", "India"), ("postalCode", "411001")):
            if fid in vis: pg.fill("#" + fid, val)
        if "phoneNumber" in vis: pg.fill("input[name=phoneNumber]", "9000000001")
        if "confirmation" in " ".join(map(str, vis)) or "submit" in vis:
            break
        pg.click("#next-button"); pg.wait_for_timeout(500)
    pg.screenshot(path="/tmp/probe-confirm.png")
    print("body:", pg.inner_text("#confirmation")[:300] if pg.locator("#confirmation").count() else pg.inner_text("body")[:300])
    pg.click("#submit"); pg.wait_for_timeout(5000)
    print("after submit:", pg.url)
    pg.screenshot(path="/tmp/probe-dash.png")
    print(json.dumps(pg.evaluate("[...document.querySelectorAll('a,button')].filter(e=>e.offsetParent).map(e=>(e.id||'')+'|'+(e.innerText||'').trim().slice(0,40)+'|'+(e.getAttribute('href')||'').slice(0,80))")[:60], indent=0))
    b.close()
