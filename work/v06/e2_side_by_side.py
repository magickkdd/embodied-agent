"""Side-by-side: what the v0.5 E2'' archive said about the same episodes.

E2''''s stub cell now dies of `REPEATED_INVALID` on c1 with zero unbound rows, where E2'' had
unbound rows -- if that is a move rather than a regression it has to be read off the old archive
rather than remembered. This reads both archives and prints the fields that decide it:
terminal_status, failure_type, objects_completed/total, unbound rows, http_requests.
"""
from __future__ import annotations

import glob
import json
import os

ARCHIVES = {
    "v05/E2''": "/home/czx/embodied-agent-batches/v05/e2",
    "v06/E2'''": "/home/czx/embodied-agent-batches/v06/e2",
}


def _unbound(ep_dir: str) -> int:
    ev = os.path.join(ep_dir, "events.jsonl")
    if not os.path.exists(ev):
        return -1
    n = 0
    for line in open(ev, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "decision_context":
            n += sum(1 for p in ((event.get("payload") or {}).get("progress") or [])
                     if "entity_binding" in (p.get("unmeasured") or []))
    return n


for label, root in ARCHIVES.items():
    print("===", label)
    for cell in sorted(glob.glob(os.path.join(root, "long_horizon_*"))):
        runs = [p for p in sorted(glob.glob(os.path.join(cell, "*")))
                if os.path.isdir(os.path.join(p, "episodes"))]
        if not runs:
            continue
        channel = os.path.basename(cell).replace("long_horizon_", "")
        for ep in sorted(glob.glob(os.path.join(runs[-1], "episodes", "*"))):
            sp = os.path.join(ep, "episode_summary.json")
            if not os.path.exists(sp):
                continue
            result = (json.load(open(sp, encoding="utf-8")).get("result") or {})
            print(f"  {channel:<11}{os.path.basename(ep):<36}"
                  f"{str(result.get('terminal_status')):<8}{str(result.get('failure_type')):<20}"
                  f"obj={result.get('objects_completed')}/{result.get('objects_total')} "
                  f"http={result.get('http_requests')} "
                  f"invalid={result.get('identical_invalid_attempts')} "
                  f"unbound={_unbound(ep)}")