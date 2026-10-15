"""Golden click paths for iDempiere (ZK web UI). Elements are found by their stable `title` attribute or text."""

BP = "text='Business Partner' >> visible=true"
PRODUCT = "text='Product' >> visible=true"
KEY = "input[title^='Search key'] >> visible=true"
NAME = "input[title^='Alphanumeric identifier'] >> visible=true"
DESC = "input[title^='Optional short description'], textarea[title^='Optional short description'] >> visible=true"
SAVE = "a[title^='Save Changes']"
FIND_OK = "button.btn-ok >> visible=true"


def click(sel, **kw):
    return {"type": "click", "selector": sel, **kw}


def fill(sel, value, wrong=None):
    s = {"type": "fill", "selector": sel, "value": value}
    if wrong is not None:
        s["wrong"] = wrong
    return s


WAIT = lambda ms=2500: {"type": "wait", "ms": ms}


def open_record(window, key):
    """Open a window and load the record with this search key through the lookup dialog."""
    return [click(window), WAIT(), fill(KEY, key), click(FIND_OK), WAIT(4000)]


def new_record(window):
    return [click(window), WAIT(), click("button.btn-new >> visible=true"), WAIT(4000)]


def save():
    return [click(SAVE, commit=True), WAIT(4000)]


def steps(slug: str, p: dict) -> list[dict]:
    if slug == "create_business_partner":
        return new_record(BP) + [fill(KEY, p["value"]), fill(NAME, p["name"], wrong="Wrong Name")] + save()
    if slug == "rename_business_partner":
        return open_record(BP, p["value"]) + [fill(NAME, p["name"], wrong="Wrong Name")] + save()
    if slug == "set_bp_description":
        return open_record(BP, p["value"]) + [fill(DESC, p["description"], wrong="wrong text")] + save()
    if slug == "mark_as_vendor":
        return open_record(BP, p["value"]) + [click("label:text-is('Vendor') >> visible=true"), WAIT(1000)] + save()
    if slug == "deactivate_business_partner":
        return open_record(BP, p["value"]) + [click("label:text-is('Active') >> visible=true"), WAIT(1000)] + save()
    if slug == "delete_business_partner":
        return open_record(BP, p["value"]) + [
            click("a[title^='Delete Record']"), WAIT(2500),
            click("button.btn-ok >> visible=true", commit=True), WAIT(4000)]
    if slug == "lookup_business_partner":
        return open_record(BP, p["value"])
    if slug == "rename_product":
        return open_record(PRODUCT, p["value"]) + [fill(NAME, p["name"], wrong="Wrong Name")] + save()
    if slug == "set_product_description":
        return open_record(PRODUCT, p["value"]) + [fill(DESC, p["description"], wrong="wrong text")] + save()
    if slug == "lookup_product":
        return open_record(PRODUCT, p["value"])
    raise KeyError(slug)
