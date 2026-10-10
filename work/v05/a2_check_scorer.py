"""v0.5 A2, criterion check: the instrument's edges are the shipped scorer's edges.

The A2 criteria fix "trigger" to the definition the scorer uses, and the check that keeps
the two from drifting is: on the same episode, the edge set this instrument derives equals
the `detail.dependency_edges` the scorer wrote into `lh_score/long_horizon_v0.json`. Without
it, "3 triggers in 187" is a number produced by an instrument nobody else has run, and a
reader has no way to tell it from the v0.4 report's 1/34 except by trusting it.

Usage:  PYTHONPATH=. <py> work/v05/a2_check_scorer.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = "/home/czx/embodied-agent-batches/v04/e1/lh_score/long_horizon_v0.json"


def main() -> int:
    with open(os.path.join(HERE, "a2_scan.json"), encoding="utf-8") as f:
        scan = json.load(f)
    mine = {r["episode_id"]: sorted(e.split("!")[0] for e in r["edges"])
            for r in scan["v04"]["rows"]}
    with open(SCORE, encoding="utf-8") as f:
        score = json.load(f)

    episodes = []
    for run in (score.get("runs") or []):
        for ep in (run.get("episodes") or []):
            episodes.append({"run": run.get("run_id"), **ep})
    print(f"scorer file: {SCORE}  runs={len(score.get('runs') or [])} episodes={len(episodes)}")
    compared = 0
    mismatches = []
    for ep in episodes:
        eid = ep.get("episode_id")
        detail = ep.get("detail") or {}
        theirs = sorted(detail.get("dependency_edges") or [])
        if eid not in mine:
            continue
        compared += 1
        if theirs != mine[eid]:
            mismatches.append((eid, mine[eid], theirs))
    print(f"compared {compared} episodes; mismatches: {len(mismatches)}")
    for eid, a, b in mismatches:
        print(f"  {eid}\n    instrument={a}\n    scorer    ={b}")
    print(f"instrument trigger count (v04 model seat): "
          f"{sum(1 for r in scan['v04']['rows'] if r['triggered'])}")
    print("OK" if not mismatches else "MISMATCH")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())