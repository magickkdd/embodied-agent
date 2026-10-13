"""Print the event-type census and the goal-side records of one orphan episode, so the RQ21
instrument can be written against the archive's real shapes rather than against a guess.

Usage: PYTHONPATH=. <py> <episode_dir>
"""
from __future__ import annotations

import collections
import json
import os
import sys

ep_dir = sys.argv[1]
events = []
for line in open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8"):
    if line.strip():
        events.append(json.loads(line))
print("event census:", dict(collections.Counter(e["type"] for e in events)))

for kind in ("task_understanding", "obligation_check"):
    for event in events:
        if event["type"] == kind:
            print(f"\n=== {kind} (seq {event['sequence']})")
            print(json.dumps(event["payload"], ensure_ascii=False, indent=1)[:1800])
            break

print("\n=== per-round goal-side rows (decision_context)")
for event in events:
    if event["type"] != "decision_context":
        continue
    payload = event["payload"]
    rows = [(r.get("entity_id"), r.get("target_id"), r.get("value"),
             (r.get("unmeasured") or [])) for r in (payload.get("progress") or [])]
    print(f"  round {payload.get('round_index')}: {rows}")

print("\n=== skill calls and their feedback")
for event in events:
    if event["type"] in ("skill_call", "execution_feedback"):
        payload = json.dumps(event.get("payload"), ensure_ascii=False)
        print(f"  {event['type']:<18} seq {event['sequence']:>3} {payload[:220]}")