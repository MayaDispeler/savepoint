"""Golden runs (FR21): replay the clean scripted path once and keep the normalized state diff."""
from savepoint.agent.actuator import Actuator
from savepoint.agent.scripted import ScriptedAgent, Terminal
from savepoint.bench import oracle


def compute_golden(contract, ctx) -> dict:
    s0 = ctx.adapter.reset(contract.fixture)
    page = ctx.new_page()
    act = Actuator(page)
    agent = ScriptedAgent(contract.id, contract.params, "none", base_url=ctx.base_url)
    while True:
        a = agent.next_action(None)
        if isinstance(a, Terminal):
            break
        act.execute(a)
    final = ctx.adapter.digest()
    ctx.close()
    return oracle.normalize(s0, final)
