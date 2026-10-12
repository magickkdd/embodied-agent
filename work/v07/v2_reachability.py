"""原则 21(a): the v2 cases must still be *doable* -- measured, not asserted.

P-A and P-B change what a case asks for, and the whole integrity risk of a re-adjudicated table
is that the re-adjudication quietly made a case easier (SPEC §4 principle 21, risk 1). The gate
named for it is (a): the privileged rule seat reaches 4/4 on every v2 cell. `privileged` spends
nothing and consults no model, so this is a **zero-cost measurement**, and it is run here before
the v2 freeze hash is trusted rather than after.

Same shape as E2''''s control cell: long-horizon, mode B, rule planner, privileged channel, two
repeats per case, so every cell has the matched denominator 4.

Usage:  PYTHONPATH=. <py> [--out /home/czx/embodied-agent-batches/v07/reachability]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
PY = "/home/czx/miniforge3/envs/embodied/bin/python"
CASES = ["lh_c1_shared_pair_restore", "lh_c3_capacity_and_shift"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/home/czx/embodied-agent-batches/v07/reachability")
    ap.add_argument("--cases", default=",".join(CASES))
    args = ap.parse_args()

    cases = [c for c in args.cases.split(",") if c.strip()]
    cmd = [PY, "-m", "embodied_agent.cli", "evaluate",
           "--set", "long_horizon", "--planner", "rule", "--modes", "B", "--repeats", "2",
           "--cases", ",".join(cases), "--out-root", args.out,
           "--perceive", "privileged", "--ablation", "full",
           "--frozen", "--no-frames"]
    started = os.path.exists(args.out)
    if started:
        print(f"{args.out} already exists; this cell has run before and will not be re-run")
    else:
        env = {**os.environ, "PYTHONPATH": "."}
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env)
        print(f"rc={result.returncode}")
        if result.returncode != 0:
            print("\n".join(ln for ln in (result.stdout + result.stderr).splitlines()[-8:]))
            return result.returncode

    runs = [p for p in sorted(glob.glob(os.path.join(args.out, "*")))
            if os.path.isdir(os.path.join(p, "episodes"))]
    reading = {"command": " ".join(cmd[2:]), "cases": cases, "cells": {}}
    for run in runs:
        outcomes = {}
        for ep in sorted(glob.glob(os.path.join(run, "episodes", "*"))):
            path = os.path.join(ep, "episode_summary.json")
            if not os.path.exists(path):
                outcomes.setdefault("infrastructure_error", []).append(os.path.basename(ep))
                continue
            result = json.load(open(path, encoding="utf-8")).get("result") or {}
            outcomes.setdefault(str(result.get("terminal_status")), []).append(
                os.path.basename(ep))
        reading["cells"][os.path.basename(run)] = {
            "outcomes": {k: sorted(v) for k, v in sorted(outcomes.items())},
            "successes": len(outcomes.get("success", []))}
    for name, cell in reading["cells"].items():
        print(f"  {name}: {cell['outcomes']}")

    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(here, "work", "v07", "reachability_v2.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reading, f, ensure_ascii=False, indent=1)
    ok = all(cell["successes"] == 4 for cell in reading["cells"].values()) and reading["cells"]
    print(f"原则 21(a): {'每格 4/4' if ok else 'NOT 4/4 -- 见读数'}")
    print(path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())