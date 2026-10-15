"""iDempiere adapter (PostgreSQL, GardenWorld demo client). Sandbox: default credentials GardenAdmin / GardenAdmin.

Ids come from `ad_sequence`; only the sequences of the monitored entities are restored, so a restore reproduces the same new ids.
"""
from typing import ClassVar

from savepoint.adapters.sql import SqlAdapter

DEFAULT_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/idempiere"
_ACCT = "c_bpartner_id,c_acctschema_id"
_TABLES = {
    "c_bpartner": "c_bpartner_id", "c_bp_customer_acct": _ACCT, "c_bp_vendor_acct": _ACCT,
    "c_bp_employee_acct": _ACCT, "c_bpartner_location": "c_bpartner_location_id",
    "ad_treenodebp": "ad_tree_id,node_id", "m_product": "m_product_id",
    "m_product_acct": "m_product_id,c_acctschema_id", "ad_treenodepr": "ad_tree_id,node_id",
    "ad_sequence": "ad_sequence_id",
}


class IdempiereAdapter(SqlAdapter):
    app_id = "idempiere"
    dialect = "postgresql"
    connect_args: ClassVar[dict] = {"options": "-c search_path=adempiere"}
    monitored_tables: ClassVar[dict[str, str]] = _TABLES
    # Rewinding every sequence would make iDempiere reuse ids that session, log and workflow tables already hold.
    row_filters: ClassVar[dict[str, str]] = {"ad_sequence": "name IN ('C_BPartner', 'M_Product', 'C_BPartner_Location')"}
    volatile_columns: ClassVar[dict[str, list[str]]] = {
        t: ["created", "updated", "createdby", "updatedby", f"{t}_uu"] for t in _TABLES}
    risky_patterns: ClassVar[list[str]] = [
        r"(?i)\b(save|submit|post|delete|void|complete|confirm|ok|yes|apply|merge|update|process|deactivate)\b"]
    redaction_selectors: ClassVar[list[str]] = []

    def __init__(self, base_url: str = "http://localhost:8080", url: str = DEFAULT_URL,
                 baseline_path: str = "idempiere-baseline.pkl"):
        super().__init__(base_url, url, baseline_path)

    def login(self, page):
        """ZK login: user and password; some sessions then show a client / role / organisation screen."""
        page.goto(self.base_url + "/webui/")
        page.wait_for_selector("input[type=password]", timeout=60000)
        page.wait_for_timeout(2000)
        page.locator("input[type=text]").first.fill("GardenAdmin")
        page.locator("input[type=password]").first.fill("GardenAdmin")
        page.click("button:has-text('OK')")
        page.wait_for_function("document.querySelector('.desktop-hometab') || [...document.querySelectorAll('input')].some(i => i.value === 'GardenWorld Admin')", timeout=60000)
        if not page.locator(".desktop-hometab").count():
            page.wait_for_timeout(1500)
            page.click("button.btn-ok")
        page.wait_for_selector(".desktop-hometab", timeout=60000)
        page.wait_for_selector("text='Business Partner' >> visible=true", timeout=60000)  # favourites loaded
        page.wait_for_timeout(1500)
