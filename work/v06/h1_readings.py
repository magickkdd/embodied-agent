"""H1 readings: the joint conditional rate, and whether the stop rule really fired.

Separated from `h1_batch.py` and importable by it, so there is one implementation of the
reading. Two things it exists to get right, both of which the first run of the batch got wrong:

1. **where the plan's rows live.** The `plan` / `plan_revision` records do not carry `subgoals`
   or `dependencies` at the top level -- they carry a rendered `view`, and the rows and the edges
   are `view["rows"]` and `view["dependencies"]` (`planning/view.py:plan_view`). Reading the top
   level finds nothing and reports "the derivation never ran", which is a finding's shape worn by
   an instrument bug. The first H1 cell reported `derivation_ran = 0` for all ten episodes on the
   strength of that wrong key;
2. **what "3 quota deaths" has to mean.** The pre-registration's stop rule says *three
   consecutive* 429/quota errors; the driver counted a cell's total. The total is the bigger
   number and it is easier to hit, so this file also computes the **longest consecutive run** in
   episode order, and that is the number the stop claim rests on.

Nothing here spends: it reads the archives the batch already wrote.
"""
from __future__ import annotations

import collections
import glob
import json
import os


def read_cell(out_root: str) -> dict:
    """One cell as the archive states it: outcomes, the H1 factors, and the quota run length."""
    run_dirs = [p for p in sorted(glob.glob(os.path.join(out_root, "*")))
                if os.path.isdir(os.path.join(p, "episodes"))]
    if not run_dirs:
        return {"episodes": 0, "why": "no run directory", "out_root": out_root}
    rd = run_dirs[-1]

    outcomes, per_ep = {}, []
    sp = os.path.join(rd, "run_summary.json")
    if os.path.exists(sp):
        outcomes = json.load(open(sp, encoding="utf-8")).get("outcomes", {})
    for ep in sorted(glob.glob(os.path.join(rd, "episodes", "*"))):
        row = {"episode_id": os.path.basename(ep)}
        rows, dependencies, kinds, skill_calls = 0, 0, [], 0
        for line in open(os.path.join(ep, "events.jsonl"), encoding="utf-8"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") in ("plan", "plan_revision"):
                # the rows and the edges live in the rendered view, not at the top level
                view = (event.get("payload") or {}).get("view") or {}
                rows += len(view.get("rows") or [])
                for dep in (view.get("dependencies") or []):
                    dependencies += 1
                    kinds.append(str((dep or {}).get("kind") or ""))
            elif event.get("type") == "skill_call":
                skill_calls += 1
        row.update({"plan_rows": rows, "dependencies": dependencies,
                    "dependency_kinds": dict(collections.Counter(kinds)),
                    "skill_calls": skill_calls,
                    "derivation_ran": rows > 0,
                    "trigger": any(k in ("state", "resource") for k in kinds),
                    "survived_to_the_step": skill_calls > 0})
        ep_sp = os.path.join(ep, "episode_summary.json")
        if os.path.exists(ep_sp):
            result = (json.load(open(ep_sp, encoding="utf-8")).get("result") or {})
            row.update({"terminal_status": result.get("terminal_status"),
                        "failure_type": result.get("failure_type"),
                        "objects_completed": result.get("objects_completed"),
                        "objects_total": result.get("objects_total"),
                        "http_requests": result.get("http_requests"),
                        "decision_rounds": result.get("decision_rounds")})
            row["grounded_and_executed"] = row.get("terminal_status") == "success"
        per_ep.append(row)

    # quota deaths in episode order, and the longest consecutive run among them
    quota_sequence = []
    for ep in sorted(glob.glob(os.path.join(rd, "episodes", "*"))):
        mc = os.path.join(ep, "model_calls.jsonl")
        if not os.path.exists(mc):
            continue
        for line in open(mc, encoding="utf-8"):
            if not line.strip():
                continue
            rec = json.loads(line)
            err = str(rec.get("error") or "")
            quota_sequence.append(bool(not rec.get("ok")
                                       and ("429" in err or "quota" in err.lower())))
    gc = os.path.join(rd, "goal_resolutions", "goal_calls.jsonl")
    if os.path.exists(gc):
        for line in open(gc, encoding="utf-8"):
            if line.strip():
                quota_sequence.append("429" in line)
    longest = current = 0
    for hit in quota_sequence:
        current = current + 1 if hit else 0
        longest = max(longest, current)

    manifest = {}
    mp = os.path.join(rd, "manifest.json")
    if os.path.exists(mp):
        m = json.load(open(mp, encoding="utf-8"))
        manifest = {"budget_caps": m.get("budget_caps"),
                    "budget_profile_max_http": sorted({(p or {}).get("max_http_requests")
                                                       for p in (m.get("budget_profile") or {}).values()}),
                    "model": m.get("model"), "perception": m.get("perception"),
                    "code_commit": (m.get("code") or {}).get("commit")}

    denominator = [r for r in per_ep if r.get("derivation_ran") and r.get("trigger")]
    joint_successes = [r for r in denominator if r.get("grounded_and_executed")]
    h1 = {"episodes": len(per_ep),
          "derivation_ran": sum(1 for r in per_ep if r.get("derivation_ran")),
          "trigger": sum(1 for r in per_ep if r.get("trigger")),
          "survived_to_the_step": sum(1 for r in per_ep if r.get("survived_to_the_step")),
          "grounded_and_executed": sum(1 for r in per_ep if r.get("grounded_and_executed")),
          "joint_denominator": len(denominator),
          "joint_successes": len(joint_successes),
          "joint_rate": (len(joint_successes) / len(denominator)) if denominator else None,
          "note": ("no denominator: no episode both ran the derivation and met its trigger, so "
                   "there is no rate to report" if not denominator else None)}
    return {"run_dir": rd, "outcomes": outcomes, "per_episode": per_ep, "manifest": manifest,
            "quota_deaths_total": sum(quota_sequence), "quota_longest_consecutive": longest,
            "h1": h1}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="/home/czx/embodied-agent-batches/v06/h1")
    args = ap.parse_args()

    cells = []
    for cell in sorted(glob.glob(os.path.join(args.archive, "*"))):
        if not os.path.isdir(os.path.join(cell, "episodes")) and \
                not glob.glob(os.path.join(cell, "*", "episodes")):
            continue
        reading = read_cell(cell)
        reading["cell"] = os.path.basename(cell)
        cells.append(reading)

    out = {"archive": args.archive, "cells": cells}
    path = os.path.join(args.archive, "h1_readings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for cell in cells:
        h1 = cell["h1"]
        print(f"=== {cell['cell']}  episodes={h1['episodes']} outcomes={cell['outcomes']}")
        print(f"    derivation_ran={h1['derivation_ran']} trigger={h1['trigger']} "
              f"survived={h1['survived_to_the_step']} success={h1['grounded_and_executed']}")
        print(f"    joint = {h1['joint_successes']}/{h1['joint_denominator']} "
              f"rate={h1['joint_rate']} {h1['note'] or ''}")
        print(f"    quota deaths total={cell['quota_deaths_total']} "
              f"longest consecutive run={cell['quota_longest_consecutive']}")
        for row in cell["per_episode"]:
            print(f"      {row['episode_id']:<34}{str(row.get('terminal_status')):<22}"
                  f"rows={row['plan_rows']:<4}deps={row['dependencies']:<3}"
                  f"kinds={row['dependency_kinds']} skills={row['skill_calls']:<3}"
                  f"http={row.get('http_requests')}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())