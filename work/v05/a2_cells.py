"""v0.5 A2 step 0: which v0.3 E1 cells are model-seat, and how many episodes each holds.

The SPEC's merged corpus is "v0.3 E1 153 episodes + v0.4 E1' 34 = 187 model-seat
episodes", but `long_horizon_full` alone holds only 12 of them. This script enumerates every
E1 cell in both roots with its planner, its seat and its episode count, so the corpus the
criteria name is a counted set of directories rather than a number copied from a report. It
prints and stops -- the scan proper is `a2_scan.py`.

Usage:  PYTHONPATH=. <py> work/v05/a2_cells.py
"""
from __future__ import annotations

import collections
import json
import os

BATCHES = "/home/czx/embodied-agent-batches"
ROOTS = {"v03": os.path.join(BATCHES, "v03", "e1"),
         "v04": os.path.join(BATCHES, "v04", "e1")}


def main() -> None:
    for tag, root in ROOTS.items():
        print(f"\n===== {tag} :: {root}")
        for cell in sorted(os.listdir(root)):
            cell_dir = os.path.join(root, cell)
            if not os.path.isdir(cell_dir):
                continue
            for run in sorted(os.listdir(cell_dir)):
                run_dir = os.path.join(cell_dir, run)
                manifest_path = os.path.join(run_dir, "manifest.json")
                ep_root = os.path.join(run_dir, "episodes")
                if not os.path.exists(manifest_path) or not os.path.isdir(ep_root):
                    continue
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                model = manifest.get("model") or {}
                episodes = sorted(os.listdir(ep_root))
                outcomes = collections.Counter()
                for ep in episodes:
                    path = os.path.join(ep_root, ep, "episode_summary.json")
                    if os.path.exists(path):
                        with open(path, encoding="utf-8") as f:
                            summary = json.load(f)
                        result = summary.get("result") or {}
                        outcomes[f"{result.get('terminal_status')}/"
                                 f"{result.get('failure_type')}"] += 1
                print(f"  {cell:<34} {run[:52]:<52} "
                      f"planner={manifest.get('planner')} "
                      f"seat={model.get('provider')}/{model.get('model')} "
                      f"perception={(manifest.get('perception') or {}).get('channel')} "
                      f"episodes={len(episodes)} {dict(outcomes)}")


if __name__ == "__main__":
    main()