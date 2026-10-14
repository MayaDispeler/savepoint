"""Write the simulated-model transcripts. Elements are recorded by selector and turned into pixel coordinates at
replay time, so the transcript does not depend on the machine's fonts. Run: uv run python scripts/record_sim.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "recorded"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    transcript = [
        {"name": "computer", "input": {"action": "left_click", "target": 'a:text-is("CL-10428")'}},
        {"name": "computer", "input": {"action": "left_click", "target": "textarea[name=body]"}},
        {"name": "computer", "input": {"action": "type", "text": "reviewed by supervisor"}},
        {"name": "computer", "input": {"action": "left_click", "target": "#save-note"}},
        {"name": "report_outcome", "input": {"status": "done", "summary": "Added the review note and saved it."}},
    ]
    (OUT / "add_note_only.json").write_text(json.dumps(
        {"workflow": "claimdesk.add_note_only", "viewport": [1366, 768], "transcript": transcript}, indent=2),
        encoding="utf-8")
    print("wrote add_note_only transcript")


if __name__ == "__main__":
    main()
