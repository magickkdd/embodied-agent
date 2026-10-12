"""v0.7 E2'''' formal batch driver: the same three channels, on the v2 table.

Copied from `work/v06/e2_batch.py` (SPEC §14: v0.6's instruments are sealed) and changed in
exactly four places, each required by `configs/experiment/v07_e2_preregistration.json` rather than
by taste:

* the archive root, the bound (**235** requests, derived from the v2 demand profile: four spending
  episodes at the measured per-case maxima 36 and 56, plus four goal parses, x1.25) and the
  report file names;
* the bound's *basis* moved from "re-price after Q1" to "read it off the profile the table now
  carries" (P-D), which is the difference between a bound and a guess;
* the batch's task table is **v2** (frozen in v0.7 P2), so the rows this writes are c1's
  colour-only declaration and c3's two same-coloured bodies -- and the archive records
  `budget_caps` plus the manifest hash so a row is traceable to the declaration it ran under;
* the pre-registered risk that `stub` dies of `REPEATED_INVALID` again is carried into the report
  as an expected reading rather than as a surprise.

Everything else -- the per-episode split read off the last `decision_context`, the budget-stop
book check, the cell order (the two zero-cost channels first, v0.3 SPEC §8.3) -- is v0.6's, so a
cell that dies at the endpoint still leaves the rest of the batch on disk.
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
ARCHIVE = "/home/czx/embodied-agent-batches/v07/e2"
SEAT = "configs/models/agnes-vision-r4.yaml"
BOUND = 235  # configs/experiment/v07_e2_preregistration.json spend_bound.requests
CAPS = 48  # D5'''': camera cells keep v0.6's 48/48; privileged is not repriced

CHANNELS = [("privileged", "full", None), ("stub", "wo_vlm", CAPS), ("vlm", "full", CAPS)]
SETS = [("long_horizon", ["lh_c1_shared_pair_restore", "lh_c3_capacity_and_shift"])]


def run_cell(*, set_name, cases, channel, arm, repeats, out_root, store, lib, cap):
    cmd = [PY, "-m", "embodied_agent.cli", "evaluate",
           "--set", set_name,
           "--planner", "rule",
           "--modes", "B",
           "--repeats", str(repeats),
           "--out-root", out_root,
           "--perceive", channel,
           "--ablation", arm,
           "--experience-store", store,
           "--skill-memory", lib,
           "--cases", ",".join(cases),
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
    """What ended the episode, how often the goal side could not bind an assignment at all, and
    the Q1 split as the last round left it.

    The split is read from the final `decision_context`'s budget payload because that is where
    `BudgetLedger.remaining_payload()` lands every round -- the ledger is not a separate file. An
    episode that died before its first round reports zeros, which is the honest reading of "no
    context was ever built", not a missed measurement.
    """
    row = {"unbound_progress_rows": 0, "rounds": 0, "blocked_events": 0,
           "perception_requests": 0, "decision_requests": 0,
           "http_requests_from_context": 0}
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
                    row["rounds"] += 1
                    payload = event.get("payload") or {}
                    row["unbound_progress_rows"] += sum(
                        1 for p in (payload.get("progress") or [])
                        if "entity_binding" in (p.get("unmeasured") or []))
                    budget = payload.get("budget") or {}
                    row["perception_requests"] = budget.get("perception_requests_used")
                    row["decision_requests"] = budget.get("decision_requests_used")
                    row["http_requests_from_context"] = budget.get("http_requests_used")
                elif event.get("type") == "terminated_blocked":
                    row["blocked_events"] += 1
    sp = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            summary = json.load(f)
        result = summary.get("result") or {}
        row.update({"terminal_status": result.get("terminal_status"),
                    "failure_type": result.get("failure_type"),
                    "termination_reason": result.get("termination_reason"),
                    "objects_completed": result.get("objects_completed"),
                    "objects_total": result.get("objects_total"),
                    "artifacts_note": (result.get("artifacts") or {}).get("note"),
                    "perception": (summary.get("perception") or {}).get("grounding_map_sha256")})
    return row


def read_cell(out_root):
    run_dirs = [p for p in sorted(glob.glob(os.path.join(out_root, "*")))
                if os.path.isdir(os.path.join(p, "episodes"))]
    if not run_dirs:
        return {"episodes": 0, "why": "no run directory", "out_root": out_root}
    rd = run_dirs[-1]
    eps = sorted(glob.glob(os.path.join(rd, "episodes", "*")))
    perception = prompt = completion = http = 0
    per_ep = []
    for ep in eps:
        types = {}
        ev = os.path.join(ep, "events.jsonl")
        if os.path.exists(ev):
            with open(ev, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        t = json.loads(line).get("type")
                        types[t] = types.get(t, 0) + 1
                    except json.JSONDecodeError:
                        pass
        p_rows = ep_prompt = ep_completion = ep_http = 0
        mc = os.path.join(ep, "model_calls.jsonl")
        if os.path.exists(mc):
            with open(mc, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    p_rows += 1
                    usage = rec.get("usage") or {}
                    ep_prompt += int(usage.get("prompt_tokens") or 0)
                    ep_completion += int(usage.get("completion_tokens") or 0)
                    ep_http += int(rec.get("http_requests_this_call") or 0)
        perception += int(types.get("perception", 0))
        prompt += ep_prompt
        completion += ep_completion
        http += ep_http
        row = {"episode_id": os.path.basename(ep),
               "perception": types.get("perception", 0),
               "ledger_rows": p_rows, "http_requests": ep_http,
               "prompt_tokens": ep_prompt, "completion_tokens": ep_completion}
        row.update(_episode_evidence(ep))
        per_ep.append(row)
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
        manifest = {"perception": m.get("perception"), "offline": m.get("offline"),
                    "model": m.get("model"), "frozen": m.get("frozen"),
                    "budget_caps": m.get("budget_caps"),
                    "budget_profile_max_http": sorted({(p or {}).get("max_http_requests")
                                                       for p in (m.get("budget_profile") or {}).values()}),
                    "code_commit": (m.get("code") or {}).get("commit"),
                    "code_dirty": (m.get("code") or {}).get("dirty")}
    ledger = []
    lp = os.path.join(rd, "errors.jsonl")
    if os.path.exists(lp):
        with open(lp, encoding="utf-8") as f:
            ledger = [json.loads(line) for line in f if line.strip()]
    infra_outcomes = {k: v for k, v in outcomes.items()
                      if k in ("infrastructure_error", "goal_resolution_error")}
    ledger_outcomes = {}
    for r in ledger:
        ledger_outcomes[r.get("outcome")] = ledger_outcomes.get(r.get("outcome"), 0) + 1
    r1_ok = sum(infra_outcomes.values()) == sum(ledger_outcomes.get(k, 0)
                                                for k in infra_outcomes)
    blocked_rows = [r for r in per_ep if r.get("terminal_status") == "failed"
                    and not r.get("failure_type")]
    r1_blocked_ok = all(r.get("termination_reason") for r in blocked_rows)
    budget_notes = [r for r in per_ep if "budget" in str(r.get("termination_reason") or "").lower()]
    wrong_book = [r.get("episode_id") for r in budget_notes
                  if not r.get("perception_requests")]
    return {"run_dir": rd, "episodes": len(eps), "perception_records": perception,
            "prompt_tokens": prompt, "completion_tokens": completion,
            "http_requests": http, "outcomes": outcomes, "manifest": manifest,
            "per_episode": per_ep,
            "budget_stops": {"episodes": [r.get("episode_id") for r in budget_notes],
                             "without_a_filled_perception_book": wrong_book},
            "r1_ledger": {"infra_outcomes": infra_outcomes,
                          "ledger_rows": ledger_outcomes, "covered": r1_ok},
            "r1_blocked": {"rows_without_failure_code": len(blocked_rows),
                           "all_state_a_reason": r1_blocked_ok}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=ARCHIVE)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--bound", type=int, default=BOUND)
    args = ap.parse_args()

    os.makedirs(args.out_root, exist_ok=True)
    report = {"spec": "Continuous-Decision-Embodied-Agent-SPEC-v0.7.md §6 E2''''",
              "prereg": "configs/experiment/v07_e2_preregistration.json",
              "phase": "P4-E2''''-formal", "seat": SEAT, "bound": args.bound,
              "table": "v2 (frozen_long_horizon_v2.json, b9fce17fbbf6)",
              "caps": {"camera_cells": {"http": CAPS, "perception": CAPS},
                       "privileged": "frozen budgets (D5'''') -- the control keeps E2''' identity"},
              "expected_risks": {
                  "stub": "REPEATED_INVALID on both c1 stub episodes (v0.6 measured it); a repeat "
                          "is evidence for principle 20, not a defect of this batch",
                  "c3_camera": "BUDGET_EXHAUSTED at the 48 ceiling (v0.6: 49-56 per episode) -- v2 "
                               "did not touch the demand, so this stop is expected to persist",
                  "zero_is_legal": "0/4 in a camera cell remains a legal reading"},
              "sets": {s: c for s, c in SETS}, "repeats": args.repeats,
              "channels": {c: a for c, a, _ in CHANNELS}, "cells": []}

    total_req = 0
    for set_name, cases in SETS:
        for channel, arm, cap in CHANNELS:
            key = f"{set_name}_{channel}"
            cell = os.path.join(args.out_root, key)
            os.makedirs(cell, exist_ok=True)
            store = os.path.join(cell, "store.jsonl")
            lib = os.path.join(cell, "lib.jsonl")
            open(store, "a").close()
            open(lib, "a").close()
            print(f"[E2''] === {key} (arm {arm}, caps {cap}, table v2) ===", flush=True)
            run = run_cell(set_name=set_name, cases=cases, channel=channel, arm=arm,
                           repeats=args.repeats, out_root=cell, store=store, lib=lib, cap=cap)
            summary = read_cell(cell)
            report["cells"].append({"key": key, "set": set_name, "channel": channel,
                                    "arm": arm, "cap": cap, "cases": cases, "run": run,
                                    "summary": summary})
            total_req += summary.get("http_requests", 0)
            s = summary
            print(f"      rc={run['rc']} {run['wall_s']}s  eps={s.get('episodes')} "
                  f"outcomes={s.get('outcomes')} perception={s.get('perception_records')} "
                  f"http={s.get('http_requests')} unbound_rows="
                  f"{sum(r.get('unbound_progress_rows', 0) for r in s.get('per_episode', []))} "
                  f"budget_stops={s.get('budget_stops', {}).get('episodes')} "
                  f"wrong_book={s.get('budget_stops', {}).get('without_a_filled_perception_book')} "
                  f"r1_covered={s.get('r1_ledger', {}).get('covered')}", flush=True)
            with open(os.path.join(args.out_root, "e2_quad_report.json"), "w",
                      encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
            if total_req > args.bound:
                print(f"[E2''] bound {args.bound} hit at {total_req} requests; "
                      f"stopping before the next cell (prereg stop rule)", flush=True)
                break
        if total_req > args.bound:
            break
    print(f"[E2''] total requests {total_req} / bound {args.bound}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())