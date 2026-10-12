"""How many objects each v1 case assigns to each tray, from the frozen table's hidden truth.

v0.7 P2 needs this because D4'''' ruled c3's two yellows into an explicit **group** declaration,
and a group can only express the hidden truth when its members share a target. Read here rather
than assumed: the answer decides whether that ruling is executable as stated.
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(REPO, "configs", "experiment", "frozen_long_horizon_v1.json"),
          encoding="utf-8") as f:
    table = json.load(f)

print(f"{'case':<30}{'per-tray counts':<44}{'max':>5}  (MAX_OBJECTS_PER_REGION = 3)")
for case in table["cases"]:
    counts = collections.Counter(a["target_id"] for a in case["hidden_eval_spec"]["assignments"])
    print(f"{case['task_id']:<30}{str(dict(sorted(counts.items()))):<44}"
          f"{max(counts.values()):>5}")

print("\nc3 的两件黄分别被送到:")
for case in table["cases"]:
    if case["task_id"] != "lh_c3_capacity_and_shift":
        continue
    by_colour = collections.defaultdict(list)
    for obj in case["objects"]:
        by_colour[obj["attributes"]["color"]].append(obj["entity_id"])
    assignment = {a["entity_id"]: a["target_id"] for a in case["hidden_eval_spec"]["assignments"]}
    for entity_id in by_colour["yellow"]:
        print(f"   {entity_id} -> {assignment[entity_id]}")