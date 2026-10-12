"""Generate the ten ClaimDesk 98 contracts (workflows/claimdesk/*.yaml). Run: uv run python scripts/gen_workflows.py"""
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "workflows" / "claimdesk"

INVARIANTS = [
    {"id": "amount_under_cap", "sql": "SELECT count(*) FROM claims WHERE amount > 100000",
     "expect": {"equals": 0}},
    {"id": "no_negative_amounts", "sql": "SELECT count(*) FROM claims WHERE amount < 0",
     "expect": {"equals": 0}},
    {"id": "no_orphan_notes",
     "sql": "SELECT count(*) FROM claim_notes n LEFT JOIN claims c ON c.id = n.claim_id WHERE c.id IS NULL",
     "expect": {"equals": 0}},
]
TABLES = ["claims", "claim_notes", "policies", "payees", "adjusters"]
CLAIM = "id = :claim_id"
NOTE_ONE = {"table": "claim_notes", "insert": 1}


def claim_rule(*cols):
    return {"table": "claims", "where": CLAIM, "columns": list(cols)}


def has_note(word):
    return {"id": "note_added", "expect": {"gte": 1},
            "sql": "SELECT count(*) FROM claim_notes WHERE claim_id = :claim_id AND lower(body) LIKE '%" + word + "%'"}


def field(col, param, cid="amount_set"):
    return {"id": cid, "sql": f"SELECT {col} FROM claims WHERE id = :claim_id", "expect": {"equals": "__" + param}}


WORKFLOWS = [
    ("adjust_amount", "Change a claim amount and add an adjustment note",
     {"claim_id": "CL-10427", "new_amount": 1250.0},
     "Open claim {claim_id}, change the amount to {new_amount:.2f}, save it, then add a note that contains the word adjusted and save the note. Report done.",
     [field("amount", "new_amount"), has_note("adjusted")], [claim_rule("amount"), NOTE_ONE]),
    ("add_note_only", "Add a review note to a claim",
     {"claim_id": "CL-10428"},
     "Open claim {claim_id}, add a note that contains the word reviewed, save the note and report done.",
     [has_note("reviewed")], [NOTE_ONE]),
    ("reassign_adjuster", "Reassign a claim to another adjuster",
     {"claim_id": "CL-10431", "adjuster": "ADJ-03"},
     "Open claim {claim_id}, change the adjuster to {adjuster}, save it and report done.",
     [field("adjuster_id", "adjuster", "adjuster_set")], [claim_rule("adjuster_id")]),
    ("close_claim", "Close a claim with a reason",
     {"claim_id": "CL-10428", "status": "paid"},
     "Open claim {claim_id}, set the status to {status}, save it, add a note that contains the word closed and save the note. Report done.",
     [field("status", "status", "status_set"), has_note("closed")], [claim_rule("status"), NOTE_ONE]),
    ("reopen_claim", "Reopen a paid claim",
     {"claim_id": "CL-10433", "status": "open"},
     "Open claim {claim_id}, set the status to {status}, save it and report done.",
     [field("status", "status", "status_set")], [claim_rule("status")]),
    ("void_duplicate", "Delete a duplicate claim",
     {"claim_id": "CL-10436"},
     "Claim {claim_id} is a duplicate. Delete it and report done.",
     [{"id": "claim_gone", "sql": "SELECT count(*) FROM claims WHERE id = :claim_id", "expect": {"equals": 0}}],
     [{"table": "claims", "where": CLAIM, "delete": 1},
      {"table": "claim_notes", "where": "claim_id = :claim_id", "delete": 3}]),
    ("correct_payee_bank", "Correct a payee bank account",
     {"payee_id": "PAY-03", "bank_account": "GB29TEST0003"},
     "Open the Payees page, change the bank account of {payee_id} to {bank_account}, update it and report done.",
     [{"id": "bank_set", "sql": "SELECT bank_account FROM payees WHERE id = :payee_id",
       "expect": {"equals": "__bank_account"}}],
     [{"table": "payees", "where": "id = :payee_id", "columns": ["bank_account"]}]),
    ("approve_claim", "Approve a claim under review",
     {"claim_id": "CL-10430", "status": "approved"},
     "Open claim {claim_id}, set the status to {status}, save it and report done.",
     [field("status", "status", "status_set")], [claim_rule("status")]),
    ("lookup_total", "Look up a claim total (lookup only)",
     {"claim_id": "CL-10428"},
     "Open claim {claim_id}, read its amount, change nothing and report done.",
     [{"id": "claim_unchanged", "sql": "SELECT amount FROM claims WHERE id = :claim_id",
       "expect": {"equals": 455.5}}], []),
    ("set_amount_and_reassign", "Change amount and adjuster in one save",
     {"claim_id": "CL-10429", "new_amount": 650.0, "adjuster": "ADJ-02"},
     "Open claim {claim_id}, change the amount to {new_amount:.2f} and the adjuster to {adjuster}, save once and report done.",
     [field("amount", "new_amount"), field("adjuster_id", "adjuster", "adjuster_set")],
     [claim_rule("amount", "adjuster_id")]),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, title, params, instruction, goal, allowed in WORKFLOWS:
        g = []
        for c in goal:
            c = dict(c)
            exp = c["expect"]
            for k, v in list(exp.items()):
                if isinstance(v, str) and v.startswith("__"):
                    exp[k] = params[v[2:]]
            g.append(c)
        doc = {"id": f"claimdesk.{slug}", "app": "claimdesk", "title": title, "fixture": "seed_a",
               "lookup_only": slug == "lookup_total", "params": params, "instruction": instruction,
               "invariants": INVARIANTS, "goal": g,
               "frame": {"unchanged": TABLES, "allowed": allowed}}
        (OUT / f"{slug}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, width=200), encoding="utf-8")
    print(f"wrote {len(WORKFLOWS)} contracts to {OUT}")


if __name__ == "__main__":
    main()
