"""Step-by-step view of one scenario under one defence, for a live demo.

    python demo.py attack_redirect_intention ours
    python demo.py attack_redirect_intention ours_fooled
"""
import sys

from agents import run_pipeline
from env import Environment
from run import DEFENCES, evaluate
from attacks import ALL_SCENARIOS as SCENARIOS

def main(scenario_id="attack_redirect_intention", defence="ours"):
    sc = next(s for s in SCENARIOS if s["id"] == scenario_id)
    gw, env, trace = DEFENCES[defence](), Environment(email=dict(sc["email"])), []
    print(f"task:  {sc['task']['instruction']}")
    print(f"email: from {sc['email']['from']}\n       {sc['email']['body']}\n")
    run_pipeline(env, sc["task"], gw, trace)
    for t in trace:
        if t["type"] == "message":
            print(f"  {t['from']:>10} -> {t['to']:<10} {t['content'][:70]!r}")
        else:
            mark = "ALLOW" if t["allowed"] else ("ESCALATE" if t.get("escalated") else "BLOCK")
            print(f"  {mark:>10}    {t['tool']}({t['args'].get('to', t['args'].get('name', ''))})")
            print(f"{'':16}{t['reason']}")
    print(f"\noutbox: {[m['to'] for m in env.outbox]}")
    print(f"result: {evaluate(sc, env, trace)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
