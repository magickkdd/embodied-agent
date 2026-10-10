"""v0.5 A1: print the per-round evidence for the items that never bound.

`a1_attribute.json` already holds every per-round row; this only selects the decisive ones
so the evidence chain can be quoted in the phase log without pasting the whole file. The
selection is the criteria's own: items with at least one unbound round.

Usage:  PYTHONPATH=. <py> work/v05/a1_evidence.py [channel]
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    with open(os.path.join(REPO, "work", "v05", "a1_attribute.json"), encoding="utf-8") as f:
        report = json.load(f)
    modes = collections.Counter()
    for cell in report["cells"]:
        if only and cell["channel"] != only:
            continue
        for item in cell["items"]:
            if not item["rounds_unbound"]:
                continue
            print(f"\n{cell['channel']} / {cell['episode_id']} / item{item['index']} "
                  f"{item['declared']} -> {item['target']}")
            for row in item["rounds"]:
                modes[row["mode"]] += 1
                print(f"   r{row['round']:<2} v{row['state_version']:<3} "
                      f"bound={str(row['bound']):<5} value={str(row['value']):<7} "
                      f"actionable={str(row['actionable']):<5} "
                      f"frame detections of that colour={row['detections_in_frame']} "
                      f"mode={row['mode']}")
    print(f"\n== per-round modes over every item with an unbound round "
          f"[{only or 'all channels'}]: {dict(modes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())