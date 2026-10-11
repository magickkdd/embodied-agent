"""v0.6 H1 verification batch driver: the joint conditional rate, on the corrected reading.

`configs/experiment/v06_h1_preregistration.json` is the design; this is the execution. It is a
different shape from E2''' on purpose: two cells of one case each, twelve episodes per cell,
the **model seat** (`--planner deepseek`) on the privileged channel, because the reading only
exists on the arm that runs the planning derivation. The rule-policy cells cannot answer it --
their `plan` records carry 0 subgoals and 0 dependencies by construction (measured on E2''''s
archives, not assumed), so H1 is the only place this number can come from.

What is measured per episode, and why each part is reported separately:

* **`derivation_ran`** -- at least one `plan`/`plan_revision` record carries subgoals. This is
  the corrected reading from P1: the edges come from the deterministic derivation in
  `planning/subgoals.py`, not from the model writing them, so "the model observed a displacement"
  is really "the derivation saw one, and the episode lived long enough to reach it";
* **`trigger`** -- at least one dependency of kind `state` or `resource`, i.e. the world actually
  contained the displacement (a blocker in a region another body needs, or two bodies competing
  for one region);
* **`survived_to_the_step`** -- the episode executed at least one skill call after the plan it was
  given, so the edge had a step to govern;
* **`grounded_and_executed`** -- `terminal_status == "success"`, which is the numerator's
  counterpart: a success on an episode with no trigger says nothing about triggering.

The headline is the **joint** rate (success among trigger ∧ derivation_ran), and all three
factors ship beside it: a high joint rate on a low survival rate is a scheduling artefact, and
the pre-registration forbids reporting the joint rate alone. Zero triggers prints "no
denominator" rather than a rate -- the v0.5 #2 lesson, stated there and kept here.

Checkpoint unit is the cell (a finished cell is never re-run), and the stop rules are the
pre-registration's: three quota deaths, or the bound.

Usage:  PYTHONPATH=. <py> [--bound 930]
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/czx/embodied-agent-robot-agent-embodied-agent-4")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from h1_readings import read_cell  # noqa: E402  (one implementation of the reading; this file runs it)

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
PY = "/home/czx/miniforge3/envs/embodied/bin/python"
ARCHIVE = "/home/czx/embodied-agent-batches/v06/h1"
SEAT = "configs/models/bst_text_agnes.yaml"  # the seat E1' measured (agnes-2.5-flash): the
# 930-request bound is priced on E1''s per-episode composition, and a bound priced on one seat
# cannot govern a batch that runs on another. The pre-registration's first draft named
# `deepseek-v3.2.yaml`, which does not exist in configs/models/; corrected before any request.
BOUND = 930  # configs/experiment/v06_h1_preregistration.json spend_bound.requests
CAP = 48      # the total this stage's two batches share (D5'''); the perception cap is inert here
EPISODES_PER_CELL = 12
#: the cells, in the order that keeps the cheaper reading first: c2 is the case whose world has
#: the blocker-with-a-region form, c3 the capacity form, and D5''' ordered E2''' before both
CELLS = [("lh_c2_displaced_completion", "c2_deepseek_privileged"),
         ("lh_c3_capacity_and_shift", "c3_deepseek_privileged")]
QUOTA_STOP = 3  # consecutive-equivalent quota deaths; the pre-registration folded E1''s 8 into this


def run_cell(*, case_id: str, episodes: int, out_root: str, store: str, lib: str) -> dict:
    cmd = [PY, "-m", "embodied_agent.cli", "evaluate",
           "--set", "long_horizon",
           "--planner", "deepseek",
           "--modes", "B",
           "--repeats", str(episodes),
           "--cases", case_id,
           "--out-root", out_root,
           "--perceive", "privileged",
           "--ablation", "full",
           "--experience-store", store,
           "--skill-memory", lib,
           "--model-config", SEAT,
           "--http-cap", str(CAP),
           "--frozen",
           "--no-frames"]
    env = {**os.environ, "PYTHONPATH": "."}
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, env=env)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if "pybullet" not in ln]
    return {"cmd": " ".join(cmd[2:]), "rc": r.returncode,
            "wall_s": round(time.time() - t0, 2), "said": tail[-4:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=ARCHIVE)
    ap.add_argument("--episodes", type=int, default=EPISODES_PER_CELL)
    ap.add_argument("--bound", type=int, default=BOUND)
    args = ap.parse_args()

    os.makedirs(args.out_root, exist_ok=True)
    state_path = os.path.join(args.out_root, "h1_state.json")
    if os.path.exists(state_path):
        state = json.load(open(state_path, encoding="utf-8"))
    else:
        state = {"spec": "configs/experiment/v06_h1_preregistration.json",
                 "bound": args.bound, "cells": [], "spent_requests": 0,
                 "stopped": None, "stopped_because": None}

    # The archive, not the state file, is the record of what has run. This batch learned that the
    # hard way: the first invocation crashed its c2 cell on a case id that was not in the frozen
    # table, went on to run c3 (whose id *was* correct), and the state file was then deleted to
    # re-run c2 cleanly -- which lost c3's entry while c3's episodes stayed on disk. A driver whose
    # checkpoint lives only in a file it can delete will re-run a paid cell or, worse, forget one.
    for _case_id, _name in CELLS:
        if any(c["name"] == _name for c in state["cells"]):
            continue
        _cell_dir = os.path.join(args.out_root, _name)
        if glob.glob(os.path.join(_cell_dir, "*", "episodes")):
            _summary = read_cell(_cell_dir)
            state["cells"].append({
                "name": _name, "case_id": _case_id, "run": {"rc": None, "reconstructed": True},
                "summary": _summary,
                "spent_requests": sum(r.get("http_requests") or 0
                                      for r in _summary.get("per_episode", [])),
                "note": ("reconstructed from the archive, not from a state file: this cell ran in "
                         "an earlier invocation of this driver")})
            print(f"[H1] {args.out_root}: reconstructed {_name} from its archive "
                  f"({_summary.get('h1', {}).get('episodes')} episodes)", flush=True)
    state["spent_requests"] = sum(c.get("spent_requests") or 0 for c in state["cells"])
    if state.get("stopped") and all(
            any(c["name"] == name for c in state["cells"]) for _case_id, name in CELLS):
        pass  # both cells are on disk; the stop note stays as history, not as an order
    else:
        state["stopped"] = None

    report = {"spec": "Continuous-Decision-Embodied-Agent-SPEC-v0.6.md §6 H1",
              "prereg": "configs/experiment/v06_h1_preregistration.json",
              "phase": "P4-H1-verification", "seat": SEAT, "bound": args.bound,
              "episodes_per_cell": args.episodes, "total_cap": CAP, "cells": []}

    for case_id, name in CELLS:
        done = [c for c in state["cells"] if c["name"] == name]
        if done:
            print(f"[H1] === {name} already ran ({done[0]['summary']['h1']['episodes']} episodes); "
                  f"a finished cell is never re-run ===", flush=True)
            report["cells"].append(done[0])
            continue
        if state.get("stopped"):
            break
        cell = os.path.join(args.out_root, name)
        os.makedirs(cell, exist_ok=True)
        store = os.path.join(cell, "store.jsonl")
        lib = os.path.join(cell, "lib.jsonl")
        open(store, "a").close()
        open(lib, "a").close()
        print(f"[H1] === {name} ({case_id}, {args.episodes} episodes, cap {CAP}) ===", flush=True)
        run = run_cell(case_id=case_id, episodes=args.episodes, out_root=cell,
                       store=store, lib=lib)
        summary = read_cell(cell)
        spent = sum(r.get("http_requests") or 0 for r in summary.get("per_episode", []))
        state["spent_requests"] += spent
        entry = {"name": name, "case_id": case_id, "run": run, "summary": summary,
                 "spent_requests": spent}
        state["cells"].append(entry)
        report["cells"].append(entry)
        h1 = summary.get("h1", {})
        print(f"      rc={run['rc']} {run['wall_s']}s eps={summary.get('episodes')} "
              f"outcomes={summary.get('outcomes')} "
              f"quota={summary.get('quota_deaths_total')}"
              f"/{summary.get('quota_longest_consecutive')}consec "
              f"spent={state['spent_requests']}/{args.bound}")
        print(f"      H1: derivation_ran={h1.get('derivation_ran')} trigger={h1.get('trigger')} "
              f"survived={h1.get('survived_to_the_step')} "
              f"joint={h1.get('joint_successes')}/{h1.get('joint_denominator')} "
              f"rate={h1.get('joint_rate')} {h1.get('note') or ''}", flush=True)
        with open(os.path.join(args.out_root, "h1_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        # the pre-registration's rule is *consecutive*, so the run length is the number that
        # decides it -- a cell total is a bigger, easier number and would stop the batch early
        if summary.get("quota_longest_consecutive", 0) >= QUOTA_STOP:
            state["stopped"] = name
            state["stopped_because"] = (f"{summary['quota_deaths']} quota deaths in {name}; "
                                        f"the pre-registered stop rule (3)")
        elif state["spent_requests"] >= args.bound:
            state["stopped"] = name
            state["stopped_because"] = f"bound {args.bound} reached"

    print(f"[H1] spent {state['spent_requests']}/{args.bound}; stopped={state.get('stopped')} "
          f"{state.get('stopped_because') or ''}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())