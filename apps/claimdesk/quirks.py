"""Six planted legacy quirks (FR03). Enabled by env QUIRKS (comma list, default all)."""
import os

ALL = ("modal_confirm", "tab_trap", "slow_save", "silent_validation", "session_timeout", "two_page_grid")


def enabled(name: str) -> bool:
    raw = os.environ.get("QUIRKS")
    if raw is None:
        return True
    return name in {q.strip() for q in raw.split(",") if q.strip()}


def session_timeout_s() -> int:
    return int(os.environ.get("SESSION_TIMEOUT_S", "600"))


def grid_page_size() -> int:
    return 150 if enabled("two_page_grid") else 1000


def save_delay_ms() -> int:
    # SAVE_DELAY_MS overrides the 3 s default (the benchmark with a scripted agent uses a shorter one)
    return int(os.environ.get("SAVE_DELAY_MS", "3000")) if enabled("slow_save") else 0
