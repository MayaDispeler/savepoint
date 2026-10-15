"""Does OpenMRS show stale data after a DB-level restore? Reset, then read the edit page twice."""
from playwright.sync_api import sync_playwright

from savepoint.adapters.openmrs import OpenMrsAdapter

a = OpenMrsAdapter()
a.reset("seed_a")
URL = "http://localhost:8080/openmrs/registrationapp/editSection.page?patientId=7&sectionId=demographics&appId=referenceapplication.registrationapp.registerPatient"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
    a.base_url = "http://localhost:8080"
    a.login(pg)
    for i in range(3):
        pg.goto(URL)
        pg.wait_for_timeout(2500 * (i + 1))
        print(i, "given field:", repr(pg.input_value("input[name=givenName]")), "| crumb:", pg.inner_text(".breadcrumb, #breadcrumbs")[:40].replace("\n", " "))
    b.close()
