"""Browser session capture: Playwright storage state plus current URL."""
from pathlib import Path


def capture(page, out_dir: str) -> tuple[str, str]:
    """Return (storage_state_path, url)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(out_dir) / "storage_state.json")
    page.context.storage_state(path=path)
    url = page.url
    (Path(out_dir) / "url.txt").write_text(url, encoding="utf-8")
    return path, url
