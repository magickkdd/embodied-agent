"""v0.6 Q1, step 0: what the single counter is actually made of, on the archives.

`BudgetLedger.http_requests` is one number for two different spends (a decision round's
request and a camera look's request, with its retries), and the per-episode cap of 32 is
checked against that sum. Before anyone rules on what the number means (SPEC §5 Q1, D2'''),
the number has to be taken apart: how much of each cell's spend is perception, how much is
decision, and whether the per-episode deaths sat on the perception side or the decision side.

Reads the v0.4 and v0.5 E2 archives read-only; costs nothing; writes
`work/v06/q1_split.json`. Every row is derivable from `model_calls.jsonl` alone, and the
instrument checks its own arithmetic (per-cell made = attributed + unattributed) so a
miscount cannot pass as a finding.

Usage:  PYTHONPATH=. <py> work/v06/q1_split.py
"""
from __future__ import annotations

import collections
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
CHANNELS = ("privileged", "stub", "vlm")
#: E2's three cells seat the *rule* policy, so they carry no decision requests at all. The
#: only corpus in the archive that spends decisions is E1's model seat, and Q1's split has
#: to be able to speak about both compositions -- a cap priced against one and applied to
#: the other is exactly the "bound that hides the breach" the v0.5 P5' lesson named.
MODEL_SEAT_ROOT = os.path.join(BATCHES, "v04", "e1", "long_horizon_full")
#: every spend the loop can make that is not a perception look; a rule-policy cell has
#: neither, which is itself the reading (its 0/0 split is why the cap never bound it)
DECISION_KINDS = ("decision", "plan", "goal", "goal_resolution", "refine", "repair")


def _run_dir(root: str, channel: str) -> str:
    cell = os.path.join(root, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(cell) if os.path.isdir(os.path.join(cell, d, "episodes"))]
    return os.path.join(cell, runs[-1])


def episode_split(ep_dir: str) -> dict:
    """Requests by kind, per episode, straight out of `model_calls.jsonl`."""
    by_kind: collections.Counter = collections.Counter()
    calls: collections.Counter = collections.Counter()
    retries = tokens = 0
    mc = os.path.join(ep_dir, "model_calls.jsonl")
    if os.path.exists(mc):
        with open(mc, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                kind = str(rec.get("kind") or "unknown")
                n = int(rec.get("http_requests_this_call") or 0)
                by_kind[kind] += n
                calls[kind] += 1
                retries += max(0, n - 1)
                usage = rec.get("usage") or {}
                tokens += int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
    made = sum(by_kind.values())
    attributed = 0
    sp = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            attributed = int(((json.load(f).get("result") or {}).get("http_requests")) or 0)
    return {
        "requests_by_kind": dict(by_kind),
        "calls_by_kind": dict(calls),
        "requests_made": made,
        "requests_attributed": attributed,
        "requests_unattributed": made - attributed,
        "perception_requests": sum(v for k, v in by_kind.items() if k.startswith("perceive")),
        "decision_requests": sum(v for k, v in by_kind.items() if not k.startswith("perceive")),
        "retries_beyond_first": retries,
        "tokens": tokens,
    }


def main() -> int:
    out = {"read_from": {k: v for k, v in ARCS.items()}, "cells": []}
    for arc, root in ARCS.items():
        for channel in CHANNELS:
            run = _run_dir(root, channel)
            rows = []
            for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
                row = episode_split(os.path.join(run, "episodes", ep))
                row["episode_id"] = ep
                rows.append(row)
            made = sum(r["requests_made"] for r in rows)
            attributed = sum(r["requests_attributed"] for r in rows)
            cell = {
                "archive": arc, "channel": channel, "run": os.path.basename(run),
                "episodes": rows,
                "made": made, "attributed": attributed, "unattributed": made - attributed,
                "perception_requests": sum(r["perception_requests"] for r in rows),
                "decision_requests": sum(r["decision_requests"] for r in rows),
                "arithmetic_ok": made == attributed + sum(r["requests_unattributed"] for r in rows),
            }
            out["cells"].append(cell)
            print(f"\n== {arc} / {channel}  made={made} attributed={attributed} "
                  f"unattributed={made - attributed} "
                  f"perception={cell['perception_requests']} decision={cell['decision_requests']}")
            for r in rows:
                print(f"   {r['episode_id']:<36} made={r['requests_made']:<4} "
                      f"attr={r['requests_attributed']:<4} unattr={r['requests_unattributed']:<4} "
                      f"perception={r['perception_requests']:<4} decision={r['decision_requests']:<4} "
                      f"by_kind={r['requests_by_kind']} retries={r['retries_beyond_first']}")
    grand_made = sum(c["made"] for c in out["cells"])
    grand_perc = sum(c["perception_requests"] for c in out["cells"])
    grand_dec = sum(c["decision_requests"] for c in out["cells"])

    # ---- the second composition: a model seat, where decisions cost requests too
    seat = {"root": MODEL_SEAT_ROOT, "runs": []}
    if os.path.isdir(MODEL_SEAT_ROOT):
        for run in sorted(os.listdir(MODEL_SEAT_ROOT)):
            ep_root = os.path.join(MODEL_SEAT_ROOT, run, "episodes")
            if not os.path.isdir(ep_root):
                continue
            rows = [episode_split(os.path.join(ep_root, ep))
                    for ep in sorted(os.listdir(ep_root))]
            seat["runs"].append({
                "run": run, "episodes": len(rows),
                "made": sum(r["requests_made"] for r in rows),
                "attributed": sum(r["requests_attributed"] for r in rows),
                "perception_requests": sum(r["perception_requests"] for r in rows),
                "decision_requests": sum(r["decision_requests"] for r in rows),
                "per_episode_decision": sorted({r["decision_requests"] for r in rows}),
                "per_episode_perception": sorted({r["perception_requests"] for r in rows}),
                "kinds": sorted({k for r in rows for k in r["requests_by_kind"]}),
            })
    seat["made"] = sum(r["made"] for r in seat["runs"])
    seat["perception"] = sum(r["perception_requests"] for r in seat["runs"])
    seat["decision"] = sum(r["decision_requests"] for r in seat["runs"])
    out["model_seat"] = seat

    out["grand"] = {"made": grand_made, "perception": grand_perc, "decision": grand_dec,
                    "split_ok": grand_made == grand_perc + grand_dec}
    print(f"\nGRAND made={grand_made} perception={grand_perc} decision={grand_dec} "
          f"split_ok={out['grand']['split_ok']}")
    print("\n== model seat (E1' long_horizon_full) -- the composition with decisions")
    for r in seat["runs"]:
        print(f"   {r['run'][:52]:<52} eps={r['episodes']:<3} made={r['made']:<5} "
              f"perception={r['perception_requests']:<5} decision={r['decision_requests']:<5} "
              f"per-episode decision={r['per_episode_decision']} kinds={r['kinds']}")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q1_split.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())