"""Local JSONL span exporter (FR31). One line per span: run, step, checkpoint, restore, validation."""
import json
import os
import time
from contextlib import contextmanager


def trace_path() -> str:
    return os.environ.get("SAVEPOINT_TRACES", "traces.jsonl")


@contextmanager
def span(name: str, **attrs):
    t0 = time.time()
    try:
        yield
    finally:
        with open(trace_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"name": name, "start": t0, "ms": int((time.time() - t0) * 1000), **attrs},
                               default=str) + "\n")
