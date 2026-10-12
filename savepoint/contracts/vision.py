"""Screen checks (FR17): ask a vision model a yes/no question about a screenshot. Advisory unless required."""
import base64


class VisionChecker:
    def __init__(self, client, model: str = "claude-haiku-5-5", budget=None, run_id: str = ""):
        self.client, self.model, self.budget, self.run_id = client, model, budget, run_id

    def ask(self, png: bytes, question: str) -> bool:
        resp = self.client.messages.create(
            model=self.model, max_tokens=5,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(png).decode()}},
                {"type": "text", "text": f"{question} Answer with only yes or no."}]}])
        if self.budget is not None:
            self.budget.record(self.run_id, self.model, resp.usage)
        text = "".join(getattr(b, "text", "") for b in resp.content).strip().lower()
        return text.startswith("yes")
