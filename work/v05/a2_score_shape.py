"""v0.5 A2 step 0b: the shape of the shipped scorer's output file.

`a2_check_scorer.py` needs to read the scorer's per-episode detail, and this prints what the
file actually holds before that reader is finished. Same status as the other step-0 scripts:
an input manifest, not a reading.

Usage:  PYTHONPATH=. <py> work/v05/a2_score_shape.py [path]
"""
from __future__ import annotations

import json
import sys

DEFAULT = "/home/czx/embodied-agent-batches/v04/e1/lh_score/long_horizon_v0.json"


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"{path}\ntop-level type={type(data).__name__}")
    if isinstance(data, dict):
        print(f"keys: {sorted(data)}")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: list of {len(value)}; first item keys="
                      f"{sorted(value[0]) if value and isinstance(value[0], dict) else None}")
            elif isinstance(value, dict):
                print(f"  {key}: dict keys={sorted(value)[:20]}")
            else:
                print(f"  {key}: {value!r}"[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())