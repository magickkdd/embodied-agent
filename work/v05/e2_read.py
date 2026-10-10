"""v0.5 P4: the E2'' cell table, and the same table re-derived from E2' for the side-by-side.

The pre-registration asks for two things that must not be merged: the per-cell readings on the
matched denominator, and the mechanism check (progress rows that could not bind an assignment
at all). Both are re-derived here from the two archives by the same code, so the comparison is
not "the v0.4 report said" against "the v0.5 batch said".

Usage:  PYTHONPATH=. <py> work/v05/e2_read.py
"""
from __future__ import annotations

import glob
import json
import os

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
CHANNELS = ("privileged", "stub", "vlm")


def _run_dir(root: str, channel: str) -> str:
    cell = os.path.join(root, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(cell) if os.path.isdir(os.path.join(cell, d, "episodes"))]
    return os.path.join(cell, runs[-1])


def _read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def episode_rows(run_dir: str) -> list[dict]:
    rows = []
    for ep in sorted(os.listdir(os.path.join(run_dir, "episodes"))):
        ep_dir = os.path.join(run_dir, "episodes", ep)
        summary_path = os.path.join(ep_dir, "episode_summary.json")
        # An episode that died before it could write a summary has none -- that is what
        # `infrastructure_error` means on this runner, and the named cause is in the cell's
        # `errors.jsonl` (v0.4 R1). Skipping it would silently shrink the denominator.
        if not os.path.exists(summary_path):
            rows.append({"episode_id": ep, "status": "infrastructure_error",
                         "failure_type": None, "termination_reason": None,
                         "note": "no episode_summary.json: see the cell's errors.jsonl",
                         "objects": "-", "rounds": None, "rounds_logged": 0,
                         "unbound_progress_rows": 0, "blocked_events": 0,
                         "requests": None, "map_sha256": None, "commit": None})
            continue
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        result = summary.get("result") or {}
        rounds = unbound = blocked = 0
        for event in _read(os.path.join(ep_dir, "events.jsonl")):
            if event.get("type") == "decision_context":
                rounds += 1
                unbound += sum(1 for p in ((event.get("payload") or {}).get("progress") or [])
                               if "entity_binding" in (p.get("unmeasured") or []))
            elif event.get("type") == "terminated_blocked":
                blocked += 1
        rows.append({
            "episode_id": ep, "status": result.get("terminal_status"),
            "failure_type": result.get("failure_type"),
            "termination_reason": result.get("termination_reason"),
            "note": (result.get("artifacts") or {}).get("note"),
            "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}",
            "rounds": result.get("decision_rounds"), "rounds_logged": rounds,
            "unbound_progress_rows": unbound, "blocked_events": blocked,
            "requests": result.get("http_requests"),
            "map_sha256": (summary.get("perception") or {}).get("grounding_map_sha256"),
            "commit": ((summary.get("manifest") or {}).get("code") or {}).get("commit"),
        })
    return rows


def main() -> int:
    for arc, root in ARCS.items():
        print(f"\n================ {arc}  {root}")
        for channel in CHANNELS:
            run_dir = _run_dir(root, channel)
            rows = episode_rows(run_dir)
            outcomes = {}
            for r in rows:
                outcomes[r["status"]] = outcomes.get(r["status"], 0) + 1
            success = sum(1 for r in rows if r["status"] == "success")
            requests = sum(int(r["requests"] or 0) for r in rows)
            unbound = sum(r["unbound_progress_rows"] for r in rows)
            print(f"\n  {channel:<11} success {success}/{len(rows)}  outcomes={outcomes}  "
                  f"requests={requests}  unbound_rows={unbound}  run={os.path.basename(run_dir)}")
            for r in rows:
                print(f"     {r['episode_id']:<36} {r['status']}/{r['failure_type']} "
                      f"obj={r['objects']} rounds={r['rounds']} unbound={r['unbound_progress_rows']} "
                      f"req={r['requests']} blocked={r['blocked_events']} "
                      f"reason={(r['termination_reason'] or r['note'])!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())