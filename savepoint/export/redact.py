"""The only module allowed to write images to disk (INV06, V28). Blurs redaction regions first."""
import io
from pathlib import Path

from PIL import Image


def capture(actuator, adapter, path: str) -> str:
    """Screenshot with the adapter's redaction selectors blurred, then write PNG."""
    data = actuator.screenshot_bytes(adapter.redaction_selectors)
    return write_png(data, path)


def write_png(data: bytes, path: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(data)).convert("RGB").save(path, format="PNG", optimize=True)
    return path
