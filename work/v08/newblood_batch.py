"""v0.8 camera fresh-blood batch driver: three cases that have never seen a camera.

Copied from `work/v07/e2_batch.py` (SPEC §14: v0.7's instruments are sealed) and changed in
exactly five places, each required by `configs/experiment/v08_newblood_preregistration.json`:

* **three cases instead of two, one case per cell** -- c2/c4/c5 have no archived camera frame at
  all (v0.7's M1), so each cell carries its own matched denominator (2) and a cell's reading cannot
  be diluted by its neighbours';
* the archive root (`v08/newblood`) and the bound (**427** requests, composed from the c3 peak of
  56 per episode because there is no profile of their own);
* the **repair** is already in the code, so the batch measures a loop that no longer dead-ends on
  a held orphan -- and the driver reports the orphan count per cell, because "the dead end is gone"
  and "the cell became non-zero" are two different readings;
* per-episode **episode-level and row-level readings are both carried**, with their labels, since
  v0.7's document gate caught them being conflated;
* cell order: the zero-cost cells of a case run before that case's vlm cell, so a dead endpoint
  still leaves the rest of the batch on disk (v0.3 SPEC §8.3).

The per-episode split read, the budget-stop book check and the two-ledger spend are v0.7's code,
unchanged -- this batch changes the questions, not the bookkeeping of the answers.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/czx/embodied-agent-robot-agent-embodied-agent-4")

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
PY = "/home/czx/miniforge3/envs/embodied/bin/python"
ARCHIVE = "/home/czx/embodied-agent-batches/v08/newblood"
SEAT = "configs/models/agnes-vision-r4.yaml"
BOUND = 427  # configs/experiment/v08_newblood_preregistration.json spend_bound.requests
CAPS = 48  # D4''''': unchanged from E2'''' -- one variable moves per batch
REPEATS = 2

#: (case, channel, arm, cap) -- the zero-cost channels first inside each case
CELLS = [
    ("lh_c2_displaced_completion", "privileged", "full", None),
    ("lh_c2_displaced_completion", "stub", "wo_vlm", CAPS),
    ("lh_c2_displaced_completion", "vlm", "full", CAPS),
    ("lh_c4_failed_grasp_recovery", "privileged", "full", None),
    ("lh_c4_failed_grasp_recovery", "stub", "wo_vlm", CAPS),
    ("lh_c4_failed_grasp_recovery", "vlm", "full", CAPS),
    ("lh_c5_release_deviation", "privileged", "full", None),
    ("lh_c5_release_deviation", "stub", "wo_vlm", CAPS),
    ("lh_c5_release_deviation", "vlm", "full", CAPS),
]
ORPHAN = "no pending goal names it"


def run_cell(*, case_id, channel, arm, repeats, out_root, store, lib, cap):
    cmd = [PY, "-m", "embodied_agent.cli", "evaluate",
           "--set", "long_horizon",
           "--planner", "rule",
           "--modes", "B",
           "--repeats", str(repeats),
           "--out-root", out_root,
           "--perceive", channel,
           "--ablation", arm,
           "--experience-store", store,
           "--skill-memory", lib,
           "--cases", case_id,
           "--model-config", SEAT,
           "--frozen",
           "--no-frames"]
    if cap is not None:
        cmd += ["--http-cap", str(cap), "--perception-cap", str(cap)]
    env = {**os.environ, "PYTHONPATH": "."}
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if "pybullet" not in ln]
    return {"cmd": " ".join(cmd[2:]), "rc": r.returncode,
            "wall_s": round(time.time() - t0, 2), "said": tail[-4:]}


def _episode_evidence(ep_dir: str) -> dict:
    """Both readings v0.8's criteria name separately: the **episode-level** terminal reason and
    the **row-level** unbound-row shape. They were conflated in v0.7's first draft and the
    document gate caught it, so both are carried here under their own keys."""
    row = {"unbound_progress_rows": 0, "rounds": 0,
           "perception_requests": 0, "decision_requests": 0,
           "http_requests_from_context": 0, "held_orphan": False}
    ev = os.path.join(ep_dir, "events.jsonl")
    if os.path.exists(ev):
        with open(ev, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "decision_context":
                    payload = event.get("payload") or {}
                    row["rounds"] += 1
                    row["unbound_progress_rows"] += sum(
                        1 for p in (payload.get("progress") or [])
                        if "entity_binding" in (p.get("unmeasured") or []))
                    budget = payload.get("budget") or {}
                    row["perception_requests"] = budget.get("perception_requests_used")
                    row["decision_requests"] = budget.get("decision_requests_used")
                    row["http_requests_from_context"] = budget.get("http_requests_used")
    sp = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            summary = json.load(f)
        result = summary.get("result") or {}
        reason = str(result.get("termination_reason") or "")
        row.update({"episode_terminal_status": result.get("terminal_status"),
                    "episode_failure_type": result.get("failure_type"),
                    "episode_termination_reason": reason or None,
                    "objects_completed": result.get("objects_completed"),
                    "objects_total": result.get("objects_total"),
                    "http_requests": result.get("http_requests"),
                    "artifacts_note": (result.get("artifacts") or {}).get("note"),
                    "perception": (summary.get("perception") or {}).get("grounding_map_sha256"),
                    "held_orphan": ORPHAN in reason})
    return row


def read_cell(out_root: str) -> dict:
    run_dirs = [p for p in sorted(glob.glob(os.path.join(out_root, "*")))
                if os.path.isdir(os.path.join(p, "episodes"))]
    if not run_dirs:
        return {"episodes": 0, "why": "no run directory", "out_root": out_root}
    rd = run_dirs[-1]
    eps = sorted(glob.glob(os.path.join(rd, "episodes", "*")))
    per_ep = []
    for ep in eps:
        reading = {"episode_id": os.path.basename(ep)}
        reading.update(_episode_evidence(ep))
        per_ep.append(reading)
    outcomes = {}
    sp = os.path.join(rd, "run_summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            outcomes = json.load(f).get("outcomes", {})
    manifest = {}
    mp = os.path.join(rd, "manifest.json")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            m = json.load(f)
        manifest = {"budget_caps": m.get("budget_caps"),
                    "model": m.get("model"), "offline": m.get("offline"),
                    "code_commit": (m.get("code") or {}).get("commit")}
    successes = sum(1 for r in per_ep if r.get("episode_terminal_status") == "success")
    orphans = [r["episode_id"] for r in per_ep if r.get("held_orphan")]
    budget_stops = [r["episode_id"] for r in per_ep
                    if r.get("episode_failure_type") == "BUDGET_EXHAUSTED"]
    return {"run_dir": rd, "episodes": len(per_ep), "outcomes": outcomes,
            "successes": successes, "nonzero": successes >= 1,
            "per_episode": per_ep, "manifest": manifest,
            "held_orphan_episodes": orphans, "budget_stop_episodes": budget_stops,
            "http_requests": sum(r.get("http_requests") or 0 for r in per_ep),
            "unbound_rows": sum(r.get("unbound_progress_rows", 0) for r in per_ep)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=ARCHIVE)
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--bound", type=int, default=BOUND)
    args = ap.parse_args()

    os.makedirs(args.out_root, exist_ok=True)
    report = {"spec": "Continuous-Decision-Embodied-Agent-SPEC-v0.8.md §6",
              "prereg": "configs/experiment/v08_newblood_preregistration.json",
              "phase": "P4-newblood-formal", "seat": SEAT, "bound": args.bound,
              "table": "v2 (frozen_long_horizon_v2.json, b9fce17fbbf6)",
              "repair": "v0.8 D2''''' held-orphan bookkeeping fix (cb1c1c2)",
              "expected_readings": {
                  "held_orphan_should_stop_appearing": "RQ23's comparison point; not the same "
                                                      "reading as a cell becoming non-zero",
                  "zero_is_legal": "an all-zero camera reading generalises 'the camera channel "
                                   "does not work' from 2 cases to 5 measured cases",
                  "ceiling": "a BUDGET_EXHAUSTED episode is a demand reading (c3 precedent 49-56)"},
              "cells": []}

    total_req = 0
    for case_id, channel, arm, cap in CELLS:
        key = f"{case_id.split('_')[1]}_{channel}"
        cell = os.path.join(args.out_root, key)
        if glob.glob(os.path.join(cell, "*", "episodes")):
            print(f"[newblood] {key} already ran; a finished cell is never re-run", flush=True)
            reading = read_cell(cell)
            report["cells"].append({"key": key, "case_id": case_id, "channel": channel,
                                    "summary": reading, "run": {"reconstructed": True}})
            total_req += reading.get("http_requests", 0)
            continue
        os.makedirs(cell, exist_ok=True)
        store = os.path.join(cell, "store.jsonl")
        lib = os.path.join(cell, "lib.jsonl")
        open(store, "a").close()
        open(lib, "a").close()
        print(f"[newblood] === {key} ({case_id}, {args.repeats} repeats, caps {cap}) ===", flush=True)
        run = run_cell(case_id=case_id, channel=channel, arm=arm, repeats=args.repeats,
                       out_root=cell, store=store, lib=lib, cap=cap)
        reading = read_cell(cell)
        report["cells"].append({"key": key, "case_id": case_id, "channel": channel,
                                "summary": reading, "run": run})
        total_req += reading.get("http_requests", 0)
        print(f"      rc={run['rc']} {run['wall_s']}s eps={reading.get('episodes')} "
              f"successes={reading.get('successes')} outcomes={reading.get('outcomes')} "
              f"http={reading.get('http_requests')} unbound={reading.get('unbound_rows')} "
              f"orphans={reading.get('held_orphan_episodes')} "
              f"budget_stops={reading.get('budget_stop_episodes')} "
              f"cumulative={total_req}/{args.bound}", flush=True)
        with open(os.path.join(args.out_root, "newblood_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        if total_req > args.bound:
            print(f"[newblood] bound {args.bound} hit at {total_req} requests; stopping before the "
                  f"next cell (pre-registered stop rule)", flush=True)
            break

    with open(os.path.join(args.out_root, "newblood_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    camera = [c for c in report["cells"] if c["channel"] in ("stub", "vlm")]
    nonzero = [c["key"] for c in camera if c["summary"].get("nonzero")]
    orphans = {c["key"]: c["summary"]["held_orphan_episodes"] for c in camera
               if c["summary"].get("held_orphan_episodes")}
    print(f"[newblood] total requests {total_req} / bound {args.bound}")
    print(f"[newblood] RQ22: non-zero camera cells = {nonzero or 'none'}")
    print(f"[newblood] RQ23: held-orphan episodes = {orphans or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())