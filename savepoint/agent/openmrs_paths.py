"""Golden click paths for the OpenMRS Reference Application 2.12 workflows (scripted agent)."""

REG = "/openmrs/registrationapp/registerPatient.page?appId=referenceapplication.registrationapp.registerPatient"
EDIT = "/openmrs/registrationapp/editSection.page?patientId={pid}&sectionId={sec}&appId=referenceapplication.registrationapp.registerPatient"
DASH = "/openmrs/coreapps/clinicianfacing/patient.page?patientId={pid}"
NEXT = {"type": "click", "selector": "#next-button"}


def goto(path):
    return {"type": "goto", "path": path}


def register(given, family, gender="Female", day="12", month="4", year="1990", wrong_family=None):
    fam = {"type": "fill", "selector": "input[name=familyName]", "value": family}
    if wrong_family:
        fam["wrong"] = wrong_family
    return [
        goto(REG),
        {"type": "fill", "selector": "input[name=givenName]", "value": given}, fam, NEXT,
        {"type": "select", "selector": "#gender-field", "value": gender}, NEXT,
        {"type": "fill", "selector": "#birthdateDay-field", "value": day},
        {"type": "select", "selector": "#birthdateMonth-field", "value": month},
        {"type": "fill", "selector": "#birthdateYear-field", "value": year}, NEXT,
        {"type": "fill", "selector": "#address1", "value": "12 Test Street"},
        {"type": "fill", "selector": "#cityVillage", "value": "Pune"},
        {"type": "fill", "selector": "#stateProvince", "value": "MH"},
        {"type": "fill", "selector": "#country", "value": "India"},
        {"type": "fill", "selector": "#postalCode", "value": "411001"}, NEXT,
        NEXT, NEXT,
        {"type": "click", "selector": "#submit", "commit": True},
        {"type": "wait", "ms": 3000},
    ]


def edit_section(pid, section, field_sel, value, wrong, nexts):
    return [
        goto(EDIT.format(pid=pid, sec=section)),
        {"type": "fill", "selector": field_sel, "value": value, "wrong": wrong}, *([NEXT] * nexts),
        {"type": "click", "selector": "#submit", "commit": True},
        {"type": "wait", "ms": 3000},
    ]


def start_visit(pid):
    return [goto(DASH.format(pid=pid)),
            {"type": "click", "selector": '[id="org.openmrs.module.coreapps.createVisit"]'},
            {"type": "click", "selector": "#start-visit-with-visittype-confirm", "commit": True},
            {"type": "wait", "ms": 3000}]


def steps(slug: str, p: dict) -> list[dict]:
    pid = p.get("patient_id")
    if slug == "onboard_patient":
        return register(p["given"], p["family"], wrong_family="Rao")
    if slug == "update_family_name":
        return edit_section(pid, "demographics", "input[name=familyName]", p["family"], "Wrongname", 3)
    if slug == "update_given_name":
        return edit_section(pid, "demographics", "input[name=givenName]", p["given"], "Wrongname", 3)
    if slug == "update_address":
        return edit_section(pid, "contactInfo", "#address1", p["address1"], "999 Wrong Road", 2)
    if slug == "add_allergy":
        return [goto(f"/openmrs/allergyui/allergy.page?patientId={pid}"),
                {"type": "click", "selector": f"#allergen-{p['allergen']}", "wrong_selector": "#allergen-71617"},
                {"type": "click", "selector": f"#severity-{p['severity']}"},
                {"type": "click", "selector": "#addAllergyBtn", "commit": True},
                {"type": "wait", "ms": 3000}]
    if slug == "start_visit":
        return start_visit(pid)
    if slug == "end_visit":
        return [goto(DASH.format(pid=pid)),
                {"type": "click", "selector": 'a[id="referenceapplication.realTime.endVisit"]:visible'},
                {"type": "click", "selector": "button:has-text('Yes'):visible", "commit": True},
                {"type": "wait", "ms": 3000}]
    if slug == "delete_patient":
        return [goto(DASH.format(pid=pid)),
                {"type": "click", "selector": '[id="org.openmrs.module.coreapps.deletePatient"]'},
                {"type": "fill", "selector": "#delete-reason", "value": "duplicate record"},
                {"type": "click", "selector": "#delete-patient-creation-dialog button.confirm", "commit": True},
                {"type": "wait", "ms": 3000}]
    if slug == "capture_vitals":
        return [goto(DASH.format(pid=pid)),
                {"type": "click", "selector": 'a[id="referenceapplication.realTime.vitals"]:visible'},
                {"type": "fill", "selector": "#w8", "value": str(p["height"])}, NEXT,
                {"type": "fill", "selector": "#w10", "value": str(p["weight"]), "wrong": "65"}, NEXT, NEXT,
                {"type": "fill", "selector": "#w12", "value": "36.8"}, NEXT,
                {"type": "fill", "selector": "#w14", "value": "72"}, NEXT,
                {"type": "fill", "selector": "#w16", "value": "16"}, NEXT,
                {"type": "fill", "selector": "#w18", "value": "120"},
                {"type": "fill", "selector": "#w20", "value": "80"}, NEXT, NEXT,
                {"type": "click", "selector": "#submit", "commit": True},
                {"type": "wait", "ms": 3000}]
    if slug == "lookup_patient":
        return [goto(DASH.format(pid=pid)), {"type": "wait", "ms": 500}]
    raise KeyError(slug)
