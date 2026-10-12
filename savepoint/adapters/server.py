"""Start and stop the local ClaimDesk 98 server (one sandbox app at a time, NFR08)."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "apps" / "claimdesk"


class ClaimDeskServer:
    def __init__(self, db_path: str, port: int = 5001, save_delay_ms: int = 300, quirks: str | None = None):
        self.db_path, self.port, self.save_delay_ms, self.quirks = db_path, port, save_delay_ms, quirks
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 30.0):
        env = dict(os.environ, CLAIMDESK_DB=self.db_path, PORT=str(self.port),
                   SAVE_DELAY_MS=str(self.save_delay_ms), PYTHONUNBUFFERED="1")
        if self.quirks is not None:
            env["QUIRKS"] = self.quirks
        self.proc = subprocess.Popen([sys.executable, "app.py"], cwd=APP_DIR, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(self.url + "/healthz", timeout=1).read()
                return self
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        self.stop()
        raise TimeoutError("ClaimDesk did not become healthy")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
