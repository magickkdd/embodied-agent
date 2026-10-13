"""Print one orphan episode's per-round timeline, for reading the drift round by round.

Usage: PYTHONPATH=. <py> <label-substring>
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "r21_orphan_attribution.json"), encoding="utf-8") as f:
    DATA = json.load(f)

needle = sys.argv[1]
for episode in DATA["episodes"]:
    if needle not in episode["label"]:
        continue
    print(f"=== {episode['label']}  held={episode['held_object']}  requests={episode['http_requests']}")
    print(f"    reason: {episode['termination_reason']}")
    for row in episode["timeline"]:
        print(f"  round {row['round']}:")
        print(f"      id-keyed rows   : {row['id_keyed']}")
        print(f"      attribute-keyed : {row['attribute_keyed']}")
        print(f"      frame colours   : {row['frame_colours']}")
        print("      drift rows whose colour the frame lacks: "
              f"{row['attribute_rows_whose_colour_the_frame_lacks']}")
        print(f"      values          : {row['values']}")
    print("    skill feedback: "
          f"{[(f['skill'], f['entity_id'], f['status']) for f in episode['skill_feedback']]}")
    a = episode["candidates"]["a_bookkeeping_defect"]
    print("    drift rounds whose frame DID carry the declared colour: "
          f"{a['drift_rounds_whose_frame_carried_the_declared_colour']}")