"""Generate the ten iDempiere contracts (workflows/idempiere/*.yaml). Run: uv run python scripts/gen_idempiere_workflows.py"""
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[1] / "workflows" / "idempiere"
INVARIANTS = [
    {"id": "no_duplicate_partner_keys", "expect": {"equals": 0},
     "sql": "SELECT count(*) FROM (SELECT value FROM c_bpartner WHERE ad_client_id = 11 GROUP BY value HAVING count(*) > 1) d"},
    {"id": "no_orphan_customer_accounts", "expect": {"equals": 0},
     "sql": "SELECT count(*) FROM c_bp_customer_acct a LEFT JOIN c_bpartner b ON b.c_bpartner_id = a.c_bpartner_id WHERE b.c_bpartner_id IS NULL"},
]
TABLES = ["c_bpartner", "c_bp_customer_acct", "c_bp_vendor_acct", "c_bp_employee_acct", "c_bpartner_location",
          "ad_treenodebp", "m_product", "m_product_acct", "ad_treenodepr"]
BP = "value = :value"


def change(table, cols, where=BP):
    return {"table": table, "where": where, "columns": cols}


def bp_goal(gid, col, expected):
    return {"id": gid, "expect": {"equals": expected}, "sql": f"SELECT {col} FROM c_bpartner WHERE value = :value"}


def product_goal(gid, col, expected):
    return {"id": gid, "expect": {"equals": expected}, "sql": f"SELECT {col} FROM m_product WHERE value = :value AND ad_client_id = 11"}


WORKFLOWS = [
    ("create_business_partner", "Create a business partner", {"value": "BP-T01", "name": "Test Partner One"},
     "Open the Business Partner window, create a new partner with search key {value} and name {name}, and save. Report done.",
     [{"id": "partner_created", "expect": {"equals": 1},
       "sql": "SELECT count(*) FROM c_bpartner WHERE value = :value AND name = :name AND isactive = 'Y'"}],
     [{"table": "c_bpartner", "insert": 1}, {"table": "ad_treenodebp", "insert": 1},
      {"table": "c_bp_customer_acct", "insert": 2}, {"table": "c_bp_vendor_acct", "insert": 2}]),  # one row per accounting schema
    ("rename_business_partner", "Rename a business partner", {"value": "JoeBlock", "name": "Joe Block Jr."},
     "Open the business partner with search key {value}, change its name to {name} and save. Report done.",
     [bp_goal("name_set", "name", "Joe Block Jr.")], [change("c_bpartner", ["name"])]),
    ("set_bp_description", "Set a business partner description",
     {"value": "TreeFarm", "description": "Preferred tree supplier"},
     "Open the business partner with search key {value}, set the description to '{description}' and save. Report done.",
     [bp_goal("description_set", "description", "Preferred tree supplier")], [change("c_bpartner", ["description"])]),
    ("mark_as_vendor", "Flag a business partner as vendor", {"value": "JoeBlock"},
     "Open the business partner with search key {value}, tick the Vendor box and save. Report done.",
     [bp_goal("is_vendor", "isvendor", "Y")], [change("c_bpartner", ["isvendor"])]),
    ("deactivate_business_partner", "Deactivate a business partner", {"value": "C&W"},
     "Open the business partner with search key {value}, untick Active and save. Report done.",
     [bp_goal("inactive", "isactive", "N")],
     [change("c_bpartner", ["isactive"]), change("c_bpartner_location", ["isactive"], "c_bpartner_id IN (SELECT c_bpartner_id FROM c_bpartner WHERE value = :value)")]),
    ("delete_business_partner", "Delete a test business partner", {"value": "BP-DELME"},
     "Open the business partner with search key {value}, delete the record and confirm. Report done.",
     [{"id": "partner_gone", "expect": {"equals": 0}, "sql": "SELECT count(*) FROM c_bpartner WHERE value = :value"}],
     [{"table": "c_bpartner", "delete": 1}, {"table": "ad_treenodebp", "delete": 1},
      {"table": "c_bp_customer_acct", "delete": 2}, {"table": "c_bp_vendor_acct", "delete": 2}]),
    ("lookup_business_partner", "Look up a business partner (lookup only)", {"value": "Standard"},
     "Open the business partner with search key {value}, read its name, change nothing and report done.",
     [{"id": "partner_present", "expect": {"equals": 1}, "sql": "SELECT count(*) FROM c_bpartner WHERE value = :value"}], []),
    ("rename_product", "Rename a product", {"value": "Oak", "name": "Oak Tree (large)"},
     "Open the product with search key {value}, change its name to {name} and save. Report done.",
     [product_goal("name_set", "name", "Oak Tree (large)")], [change("m_product", ["name"], "value = :value AND ad_client_id = 11")]),
    ("set_product_description", "Set a product description", {"value": "Elm", "description": "Shade tree"},
     "Open the product with search key {value}, set the description to '{description}' and save. Report done.",
     [product_goal("description_set", "description", "Shade tree")],
     [change("m_product", ["description"], "value = :value AND ad_client_id = 11")]),
    ("lookup_product", "Look up a product (lookup only)", {"value": "Rose Bush"},
     "Open the product with search key {value}, read its name, change nothing and report done.",
     [{"id": "product_present", "expect": {"equals": 1},
       "sql": "SELECT count(*) FROM m_product WHERE value = :value AND ad_client_id = 11"}], []),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, title, params, instruction, goal, allowed in WORKFLOWS:
        doc = {"id": f"idempiere.{slug}", "app": "idempiere", "title": title, "fixture": "seed_a",
               "lookup_only": slug.startswith("lookup_"), "params": params, "instruction": instruction,
               "invariants": INVARIANTS, "goal": goal, "frame": {"unchanged": TABLES, "allowed": allowed}}
        (OUT / f"{slug}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False, width=200), encoding="utf-8")
    print(f"wrote {len(WORKFLOWS)} contracts to {OUT}")


if __name__ == "__main__":
    main()
