"""Simulated Claude client (V07 stand-in). Replays a recorded transcript of computer-tool calls through the real
ClaudeAgent loop, with token usage taken from the PRD A8 cost model. No network and no real model call: every run
made with it is labelled `-simulated` and its model cost is recorded as 0.
"""
import json
from pathlib import Path
from types import SimpleNamespace as NS

from savepoint.agent.budget import EST_PER_STEP_IN, EST_PER_STEP_OUT, EST_PREFIX

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recorded"


class SimulatedClient:
    """Duck-types `client.messages.create`. Each call returns the next recorded tool_use block."""

    def __init__(self, transcript: list[dict]):
        self.transcript = list(transcript)
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        step = self.calls
        self.calls += 1
        item = self.transcript.pop(0)
        usage = NS(input_tokens=EST_PREFIX + EST_PER_STEP_IN * (step + 1), output_tokens=EST_PER_STEP_OUT,
                   cache_read_input_tokens=0, cache_creation_input_tokens=0)
        block = NS(type="tool_use", id=f"sim_{step}", name=item["name"], input=item["input"])
        return NS(content=[block], usage=usage)


def load(workflow_slug: str) -> list[dict]:
    return json.loads((FIXTURES / f"{workflow_slug}.json").read_text(encoding="utf-8"))["transcript"]
