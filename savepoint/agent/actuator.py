"""Playwright actuator for computer-use toolset member calls (FR06) at 1366x768.

Members: screenshot, click, type, key, scroll, wait. Scripted agents may address elements by CSS
selector (`selector`) instead of pixel coordinates; the risky-step probe handles both.
"""
import re

VIEWPORT = {"width": 1366, "height": 768}

_NAME_JS = """(el) => {
  if (!el) return '';
  const n = el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('title') || '';
  return n.trim().slice(0, 60);
}"""


class Actuator:
    def __init__(self, page):
        self.page = page

    def target_name(self, action: dict) -> str:
        """Accessible name or text of the element an action would hit (A1)."""
        t = action["type"]
        try:
            if t == "click" and action.get("selector"):
                return self.page.eval_on_selector(action["selector"], _NAME_JS)
            if t == "click" and "x" in action:
                return self.page.evaluate(
                    "([x,y]) => { const el = document.elementFromPoint(x,y); return (" + _NAME_JS + ")(el); }",
                    [action["x"], action["y"]])
            if t == "key" and action.get("key") == "Enter":
                return self.page.evaluate("() => (" + _NAME_JS + ")(document.activeElement)")
        except Exception:  # noqa: BLE001 - a failed probe must not stop the run; treated as not risky
            return ""
        return ""

    def is_risky(self, action: dict, patterns: list[str]) -> bool:
        name = self.target_name(action)
        return bool(name) and any(re.search(p, name, re.IGNORECASE) for p in patterns)

    def execute(self, action: dict) -> str:
        t, p = action["type"], self.page
        if t == "goto":
            p.goto(action["url"])
        elif t == "click":
            if action.get("selector"):
                p.click(action["selector"], timeout=5000)
            else:
                p.mouse.click(action["x"], action["y"])
        elif t == "fill":
            p.fill(action["selector"], str(action["value"]), timeout=5000)
        elif t == "select":
            p.select_option(action["selector"], str(action["value"]), timeout=5000)
        elif t == "click_until":  # wizard helper: press Next until the target control is visible
            for _ in range(action.get("max", 8)):
                if p.is_visible(action["until"]):
                    break
                p.click(action["selector"], timeout=5000)
                p.wait_for_timeout(300)
        elif t == "type":
            p.keyboard.type(action["text"])
        elif t == "key":
            p.keyboard.press(action["key"])
        elif t == "scroll":
            p.mouse.wheel(0, action.get("dy", 400))
        elif t == "wait":
            p.wait_for_timeout(action.get("ms", 500))
        elif t == "screenshot":
            return "screenshot"
        else:
            raise ValueError(f"unsupported action {t}")
        return "ok"

    def screenshot_bytes(self, redaction_selectors: list[str]) -> bytes:
        """Screenshot with every redaction selector blurred first (FR30). Use export.redact for disk writes."""
        css = ", ".join(redaction_selectors)
        handle = None
        if css:
            handle = self.page.add_style_tag(content=f"{css}{{filter: blur(8px) !important}}")
        try:
            return self.page.screenshot()
        finally:
            if handle:
                handle.evaluate("el => el.remove()")
