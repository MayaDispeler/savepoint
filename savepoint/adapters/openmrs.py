"""OpenMRS Reference Application 2.12 adapter (MySQL). Sandbox: demo data, default credentials admin / Admin123."""
from typing import ClassVar

from savepoint.adapters.sql import SqlAdapter

DEFAULT_URL = "mysql+pymysql://root:openmrs@127.0.0.1:3306/openmrs"
_VOL = ["uuid", "date_created", "date_changed", "date_voided"]


class OpenMrsAdapter(SqlAdapter):
    app_id = "openmrs"
    dialect = "mysql"
    monitored_tables: ClassVar[dict[str, str]] = {
        "person": "person_id", "person_name": "person_name_id", "person_address": "person_address_id",
        "person_attribute": "person_attribute_id", "patient": "patient_id",
        "patient_identifier": "patient_identifier_id", "visit": "visit_id", "encounter": "encounter_id",
        "obs": "obs_id", "allergy": "allergy_id", "allergy_reaction": "allergy_reaction_id",
        "relationship": "relationship_id",
    }
    volatile_columns: ClassVar[dict[str, list[str]]] = {
        "person": [*_VOL], "person_name": [*_VOL], "person_address": [*_VOL], "person_attribute": [*_VOL],
        "patient": [*_VOL],
        "patient_identifier": [*_VOL, "identifier"],  # OpenMRS ID is generated from a sequence the restore does not rewind
        "visit": [*_VOL, "date_started", "date_stopped"],
        "encounter": [*_VOL, "encounter_datetime"], "obs": [*_VOL, "obs_datetime"],
        "allergy": [*_VOL], "allergy_reaction": ["uuid"], "relationship": [*_VOL],
    }
    risky_patterns: ClassVar[list[str]] = [
        r"(?i)\b(save|submit|post|delete|void|complete|confirm|ok|yes|apply|merge|update|end visit|start visit)\b"]
    redaction_selectors: ClassVar[list[str]] = []

    def __init__(self, base_url: str = "http://localhost:8080", url: str = DEFAULT_URL,
                 baseline_path: str = "openmrs-baseline.pkl"):
        super().__init__(base_url, url, baseline_path)

    def login(self, page):
        page.goto(self.base_url + "/openmrs/login.htm")
        page.fill("#username", "admin")
        page.fill("#password", "Admin123")
        page.click("#sessionLocation li:first-child")
        page.click("#loginButton")
        page.wait_for_url("**/home.page")
