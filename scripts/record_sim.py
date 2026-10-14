"""Record coordinates for the simulated-model transcripts on a live ClaimDesk (1366x768).
Run: uv run python scripts/record_sim.py"""
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from savepoint.adapters.claimdesk import ClaimDeskAdapter
from savepoint.adapters.server import ClaimDeskServer

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "recorded"


def centre(page, selector):
    box = page.locator(selector).first.bounding_box()
    return [round(box["x"] + box["width"] / 2), round(box["y"] + box["height"] / 2)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db = str(Path(tempfile.mkdtemp()) / "cd.db")
    ClaimDeskAdapter("http://127.0.0.1:5011", db).reset("seed_a")
    with ClaimDeskServer(db, 5011, save_delay_ms=300) as server, sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={"width": 1366, "height": 768}).new_page()
        page.goto(server.url + "/login")
        page.click("button[type=submit]")
        page.goto(server.url + "/claims")
        link = centre(page, 'a:text-is("CL-10428")')
        page.click('a:text-is("CL-10428")')
        page.wait_for_selector("textarea[name=body]")
        note = centre(page, "textarea[name=body]")
        save = centre(page, "#save-note")
        b.close()
    transcript = [
        {"name": "computer", "input": {"action": "left_click", "coordinate": link}},
        {"name": "computer", "input": {"action": "left_click", "coordinate": note}},
        {"name": "computer", "input": {"action": "type", "text": "reviewed by supervisor"}},
        {"name": "computer", "input": {"action": "left_click", "coordinate": save}},
        {"name": "report_outcome", "input": {"status": "done", "summary": "Added the review note and saved it."}},
    ]
    (OUT / "add_note_only.json").write_text(json.dumps({"workflow": "claimdesk.add_note_only", "viewport": [1366, 768],
                                                         "transcript": transcript}, indent=2), encoding="utf-8")
    print("recorded", note, save)


if __name__ == "__main__":
    main()
