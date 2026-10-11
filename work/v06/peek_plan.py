"""What the model-seat episodes' `plan` records actually carry.

H1's first cell reported `derivation_ran = 0` for all ten episodes, which would be the headline
("no denominator"). Before that can be written up as a reading it has to be ruled out as an
instrument artefact: if the derivation's rows live under a key this instrument does not read, then
"no denominator" is a bug wearing a finding's clothes. So: print the `plan` payload's own keys and
the first subgoal/dependency, if any.
"""
from __future__ import annotations

import glob
import json
import os
import sys

root = sys.argv[1]
run_dirs = [p for p in sorted(glob.glob(os.path.join(root, "*"))) if os.path.isdir(p)]
for ep in sorted(glob.glob(os.path.join(run_dirs[-1], "episodes", "*"))):
    kinds = {}
    for line in open(os.path.join(ep, "events.jsonl"), encoding="utf-8"):
        if not line.strip():
            continue
        event = json.loads(line)
        kinds[event.get("type")] = kinds.get(event.get("type"), 0) + 1
    print("===", os.path.basename(ep), {k: v for k, v in sorted(kinds.items())
                                         if k in ("plan", "plan_revision", "skill_call",
                                                  "decision_context", "terminated_blocked")})
    for line in open(os.path.join(ep, "events.jsonl"), encoding="utf-8"):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") not in ("plan", "plan_revision"):
            continue
        payload = event.get("payload") or {}
        print("   ", event["type"], "payload keys:", sorted(payload))
        for key in ("subgoals", "rows", "steps", "dependencies", "edges", "provenance"):
            value = payload.get(key)
            if value:
                print(f"      {key}: {json.dumps(value, ensure_ascii=False)[:400]}")
        break