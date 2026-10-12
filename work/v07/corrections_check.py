"""Two corrections the v0.7 document gate forced, verified from the archives before being written.

1. The **held-state orphan** (`holding X but no pending goal names it`) -- v0.7's report called it a
   single c3 episode; the gate found it in three. It is also present in v0.6's camera cell, which
   means v0.6's report attributed those episodes to #26 while their *terminal* reason was the
   orphan. Both readings are printed here before either document is corrected.
2. The **first look** -- the P1 log and the v0.7 report both say every episode's first look carries
   zero objects. The M1 profile says otherwise (it carries 4-5). The profile is the measurement;
   the sentence was written before the field existed.

Usage:  PYTHONPATH=. <py>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "m1_mismatch.json"), encoding="utf-8") as f:
    M1 = json.load(f)

print("=== 1. 每个集的首个观测携带几个物体（M1 档案原值）")
for case_id, reading in M1["cases"].items():
    for channel in ("stub", "vlm"):
        profile = reading["confirmed_discrimination"][channel]
        if not profile["looks"]:
            continue
        print(f"  {case_id:<30}{channel:<5}first_look={profile['first_look_objects']}  "
              f"objects_per_frame={profile['objects_per_frame']}")

print("\n=== 2. 各代相机格每一集的终止理由（无 failure_type 的那些）")
ARCHIVES = {
    "v06/E2''' (v1 表)": "/home/czx/embodied-agent-batches/v06/e2",
    "v07/E2'''' (v2 表)": "/home/czx/embodied-agent-batches/v07/e2",
}
for label, root in ARCHIVES.items():
    print("---", label)
    cell = os.path.join(root, "long_horizon_vlm")
    runs = [p for p in sorted(os.listdir(cell)) if os.path.isdir(os.path.join(cell, p, "episodes"))]
    if not runs:
        continue
    for ep in sorted(os.listdir(os.path.join(cell, runs[-1], "episodes"))):
        path = os.path.join(cell, runs[-1], "episodes", ep, "episode_summary.json")
        if not os.path.exists(path):
            continue
        result = json.load(open(path, encoding="utf-8")).get("result") or {}
        print(f"  {ep:<34}{str(result.get('terminal_status')):<8}"
              f"{str(result.get('failure_type') or '-'):<20}"
              f"obj={result.get('objects_completed')}/{result.get('objects_total')} "
              f"http={result.get('http_requests'):<4} reason={result.get('termination_reason')}")