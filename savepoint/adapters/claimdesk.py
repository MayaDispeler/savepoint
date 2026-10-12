import importlib.util
from pathlib import Path
from typing import ClassVar

from savepoint.adapters.base import AppAdapter, SqliteMixin
from savepoint.snapshot.digest import Digest

_SEED = Path(__file__).resolve().parents[2] / "apps" / "claimdesk" / "seed.py"


def _load_seed():
    spec = importlib.util.spec_from_file_location("claimdesk_seed", _SEED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ClaimDeskAdapter(SqliteMixin, AppAdapter):
    app_id = "claimdesk"
    monitored_tables: ClassVar[dict[str, str]] = {
        "claims": "id", "claim_notes": "id", "policies": "id", "payees": "id", "adjusters": "id"}
    volatile_columns: ClassVar[dict[str, list[str]]] = {"claims": ["updated_at"], "claim_notes": ["created_at"]}
    risky_patterns: ClassVar[list[str]] = [
        r"(?i)\b(save|submit|post|delete|void|complete|confirm|ok|yes|apply|merge|update|close claim)\b"]
    redaction_selectors: ClassVar[list[str]] = ["input[name=bank_account]"]

    def __init__(self, base_url: str, db_path: str, files_dir: str | None = None):
        super().__init__(base_url)
        self.db_path = db_path
        self.files_dir = files_dir

    def reset(self, fixture: str = "seed_a") -> Digest:
        if fixture != "seed_a":
            raise ValueError(f"unknown fixture: {fixture}")
        _load_seed().build(self.db_path)
        return self.digest()
