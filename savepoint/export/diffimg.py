"""Screenshot diff (A9): greyscale absolute difference, threshold 24, percentage of changed pixels."""
import io

from PIL import Image, ImageChops

from savepoint.export.redact import write_png

THRESHOLD = 24
TILE = 32


def pixel_diff_pct(a_png: bytes, b_png: bytes) -> float:
    a = Image.open(io.BytesIO(a_png)).convert("L")
    b = Image.open(io.BytesIO(b_png)).convert("L").resize(a.size)
    diff = ImageChops.difference(a, b).point(lambda v: 255 if v > THRESHOLD else 0)
    changed = diff.histogram()[255]
    return round(changed / (a.size[0] * a.size[1]) * 100, 2)


def write_overlay(a_png: bytes, b_png: bytes, path: str) -> str:
    """Outline 32 px tiles with any changed pixel in signal blue (#2447C9) on the 'after' image."""
    a = Image.open(io.BytesIO(a_png)).convert("L")
    b_rgb = Image.open(io.BytesIO(b_png)).convert("RGB").resize(a.size)
    diff = ImageChops.difference(a, b_rgb.convert("L")).point(lambda v: 255 if v > THRESHOLD else 0)
    px, w, h = diff.load(), *a.size
    out = b_rgb.copy()
    op = out.load()
    for ty in range(0, h, TILE):
        for tx in range(0, w, TILE):
            if any(px[x, y] for y in range(ty, min(ty + TILE, h)) for x in range(tx, min(tx + TILE, w))):
                for x in range(tx, min(tx + TILE, w)):
                    op[x, ty] = op[x, min(ty + TILE, h) - 1] = (0x24, 0x47, 0xC9)
                for y in range(ty, min(ty + TILE, h)):
                    op[tx, y] = op[min(tx + TILE, w) - 1, y] = (0x24, 0x47, 0xC9)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return write_png(buf.getvalue(), path)
