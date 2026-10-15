"""iDempiere 13 adapter (PostgreSQL, GardenWorld demo client). Sandbox: default credentials GardenAdmin / GardenAdmin."""
from typing import ClassVar

from savepoint.adapters.sql import SqlAdapter

DEFAULT_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/idempiere"
_VOL = ["created", "updated", "createdby", "updatedby"]


class IdempiereAdapter(SqlAdapter):
    app_id = "idempiere"
    dialect = "postgresql"
    monitored_tables: ClassVar[dict[str, str]] = {}
    volatile_columns: ClassVar[dict[str, list[str]]] = {}
    risky_patterns: ClassVar[list[str]] = [
        r"(?i)\b(save|submit|post|delete|void|complete|confirm|ok|yes|apply|merge|update|process|deactivate)\b"]
    redaction_selectors: ClassVar[list[str]] = []

    def __init__(self, base_url: str = "http://localhost:8080", url: str = DEFAULT_URL,
                 baseline_path: str = "idempiere-baseline.pkl"):
        super().__init__(base_url, url, baseline_path)

    def login(self, page):
        page.goto(self.base_url + "/webui/")
        page.wait_for_selector("input[type=text]", timeout=60000)
        inputs = page.locator("input[type=text], input[type=password]")
        inputs.nth(0).fill("GardenAdmin")
        inputs.nth(1).fill("GardenAdmin")
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
