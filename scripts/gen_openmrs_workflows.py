"""Generate the ten OpenMRS contracts (workflows/openmrs/*.yaml). Run: uv run python scripts/gen_openmrs_workflows.py"""
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "workflows" / "openmrs"
INVARIANTS = [
    {"id": "identifiers_unique", "expect": {"equals": 0},
     "sql": "SELECT count(*) FROM (SELECT identifier FROM patient_identifier WHERE voided = 0 GROUP BY identifier HAVING count(*) > 1) d"},
    {"id": "no_orphan_names", "expect": {"equals": 0},
     "sql": "SELECT count(*) FROM person_name n LEFT JOIN person p ON p.person_id = n.person_id WHERE p.person_id IS NULL"},
]
TABLES = ["person", "person_name", "person_address", "person_attribute", "patient", "patient_identifier", "visit",
          "encounter", "obs", "allergy", "allergy_reaction", "relationship"]
P = "person_id = :patient_id"


def rule(table, where=P, **kw):
    return {"table": table, "where": where, **kw}


WORKFLOWS = [
    ("onboard_patient", "Register a new patient", {"given": "Neha", "family": "Kulkarni"},
     "Register a new patient named {given} {family}, female, born 12 April 1990, living at 12 Test Street, Pune. Do not start a visit. Report done.",
     [{"id": "patient_registered", "expect": {"equals": 1},
       "sql": "SELECT count(*) FROM person_name n JOIN patient p ON p.patient_id = n.person_id WHERE n.given_name = :given AND n.family_name = :family AND n.voided = 0"}],
     [{"table": t, "insert": 1} for t in ("person", "person_name", "person_address", "patient", "patient_identifier")]),
    ("update_family_name", "Correct a patient's family name", {"patient_id": 7, "family": "Rao-Menon"},
     "Open the registration summary of patient {patient_id}, change the family name to {family}, confirm and report done.",
     [{"id": "family_set", "expect": {"equals": "Rao-Menon"},
       "sql": "SELECT family_name FROM person_name WHERE person_id = :patient_id AND voided = 0"}],
     [rule("person_name", columns=["voided", "voided_by", "date_voided", "void_reason", "changed_by"], insert=1)]),
    ("update_given_name", "Correct a patient's given name", {"patient_id": 7, "given": "Ashalata"},
     "Open the registration summary of patient {patient_id}, change the given name to {given}, confirm and report done.",
     [{"id": "given_set", "expect": {"equals": "Ashalata"},
       "sql": "SELECT given_name FROM person_name WHERE person_id = :patient_id AND voided = 0"}],
     [rule("person_name", columns=["voided", "voided_by", "date_voided", "void_reason", "changed_by"], insert=1)]),
    ("update_address", "Correct a patient's address", {"patient_id": 7, "address1": "44 Lake View Road"},
     "Open the contact information of patient {patient_id}, change the first address line to {address1}, confirm and report done.",
     [{"id": "address_set", "expect": {"equals": "44 Lake View Road"},
       "sql": "SELECT address1 FROM person_address WHERE person_id = :patient_id AND voided = 0"}],
     [rule("person_address", columns=["voided", "voided_by", "date_voided", "void_reason", "changed_by", "address1"], insert=1)]),
    ("add_allergy", "Record an allergy", {"patient_id": 7, "allergen": 162298, "severity": 1498},
     "Open the allergies page of patient {patient_id}, record allergen concept {allergen} with severity {severity} and save. Report done.",
     [{"id": "allergy_recorded", "expect": {"equals": 1},
       "sql": "SELECT count(*) FROM allergy WHERE patient_id = :patient_id AND coded_allergen = :allergen AND voided = 0"}],
     [{"table": "allergy", "insert": 1}, {"table": "allergy_reaction", "insert": 3}]),
    ("start_visit", "Start a visit", {"patient_id": 8},
     "Open the dashboard of patient {patient_id}, start a visit and confirm. Report done.",
     [{"id": "visit_open", "expect": {"equals": 1},
       "sql": "SELECT count(*) FROM visit WHERE patient_id = :patient_id AND date_stopped IS NULL AND voided = 0"}],
     [{"table": "visit", "insert": 1}]),
    ("end_visit", "End the active visit", {"patient_id": 9},
     "Open the dashboard of patient {patient_id}, end the active visit and confirm. Report done.",
     [{"id": "no_open_visit", "expect": {"equals": 0},
       "sql": "SELECT count(*) FROM visit WHERE patient_id = :patient_id AND date_stopped IS NULL AND voided = 0"}],
     [rule("visit", where="patient_id = :patient_id", columns=["date_stopped", "changed_by", "date_changed"])]),
    ("delete_patient", "Delete a duplicate patient record", {"patient_id": 10},
     "Patient {patient_id} is a duplicate. Delete the patient record with the reason 'duplicate record' and report done.",
     [{"id": "patient_voided", "expect": {"equals": 1},
       "sql": "SELECT voided FROM patient WHERE patient_id = :patient_id"}],
     [rule("patient", where="patient_id = :patient_id", columns=["voided", "voided_by", "date_voided", "void_reason"]),
      rule("person", columns=["voided", "voided_by", "date_voided", "void_reason"]),
      rule("person_name", columns=["voided", "voided_by", "date_voided", "void_reason"]),
      rule("person_address", columns=["voided", "voided_by", "date_voided", "void_reason"]),
      rule("patient_identifier", where="patient_id = :patient_id", columns=["voided", "voided_by", "date_voided", "void_reason"])]),
    ("mark_deceased", "Mark a patient deceased", {"patient_id": 11},
     "Open the dashboard of patient {patient_id}, mark the patient deceased and confirm. Report done.",
     [{"id": "patient_dead", "expect": {"equals": 1}, "sql": "SELECT dead FROM person WHERE person_id = :patient_id"}],
     [rule("person", columns=["dead", "death_date", "cause_of_death", "changed_by", "date_changed"])]),
    ("lookup_patient", "Look up a patient (lookup only)", {"patient_id": 7},
     "Open the dashboard of patient {patient_id}, read the patient identifier, change nothing and report done.",
     [{"id": "patient_present", "expect": {"gte": 1},
       "sql": "SELECT count(*) FROM patient_identifier WHERE patient_id = :patient_id AND voided = 0"}], []),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, title, params, instruction, goal, allowed in WORKFLOWS:
        doc = {"id": f"openmrs.{slug}", "app": "openmrs", "title": title, "fixture": "seed_a",
               "lookup_only": slug == "lookup_patient", "params": params, "instruction": instruction,
               "invariants": INVARIANTS, "goal": goal, "frame": {"unchanged": TABLES, "allowed": allowed}}
        (OUT / f"{slug}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, width=200), encoding="utf-8")
    print(f"wrote {len(WORKFLOWS)} contracts to {OUT}")


if __name__ == "__main__":
    main()
