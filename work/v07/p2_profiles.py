"""v0.7 P2's two profiles, written as a file the v2 table can read (P-C and P-D).

The v2 table carries two per-case blocks that v0.7 ruled must enter the table rather than live
in a report: the **t0 trigger premise** (does this case's world contain the displacement that
makes the dependency derivation author an edge at all -- v0.6 H1 measured "no" on all six, which
is why the trigger batch had no denominator) and the **perception demand profile** (how many
looks a camera episode on this case actually costs, per channel -- the number E2'''' 's bound is
built from instead of a guess, the way #27 should have been bounded all along).

Both are measured artefacts, so this file only assembles them from instruments that measured:

* trigger premise: `h1_derivation_probe.py` (v0.6's probe, copied) run over all six cases;
* demand: `m1_mismatch.json`'s confirmed look counts per case and channel, plus the **final
  request** totals from v0.6's E2'''' archive (the two-ledger reading, because the per-episode
  context snapshot understates the spend by the round in flight).

Zero cost, zero requests: it reads the archives and re-runs one offline derivation.

Usage:  PYTHONPATH=. <py>       -> work/v07/task_profiles.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

V06_E2 = "/home/czx/embodied-agent-batches/v06/e2"


def _v06_requests_per_case() -> dict:
    """Final requests per episode, per case, on the channel that spends (vlm), from the archive."""
    out: dict[str, list[int]] = {}
    runs = [p for p in sorted(glob.glob(os.path.join(V06_E2, "long_horizon_vlm", "*")))
            if os.path.isdir(os.path.join(p, "episodes"))]
    if not runs:
        return out
    for ep in sorted(glob.glob(os.path.join(runs[-1], "episodes", "*"))):
        path = os.path.join(ep, "episode_summary.json")
        if not os.path.exists(path):
            continue
        result = json.load(open(path, encoding="utf-8")).get("result") or {}
        case_id = os.path.basename(ep).split(".")[0]
        out.setdefault(case_id, []).append(int(result.get("http_requests") or 0))
    return out


def main() -> int:
    with open(os.path.join(HERE, "h1_derivation_probe.json"), encoding="utf-8") as f:
        probe = json.load(f)
    with open(os.path.join(HERE, "m1_mismatch.json"), encoding="utf-8") as f:
        m1 = json.load(f)
    requests = _v06_requests_per_case()

    profiles = {"source": {"trigger": "work/v07/h1_derivation_probe.json (v0.6 H1 probe, copy)",
                           "demand": "work/v07/m1_mismatch.json confirmed look counts + "
                                     "v0.6 E2''' episode_summary final request counts",
                           "cost": "zero"},
                "cases": {}}
    for case_id, reading in probe["cases"].items():
        looks = {channel: m1["cases"][case_id]["confirmed_discrimination"][channel]
                 for channel in ("stub", "vlm")}
        per_episode = {}
        for channel, profile in looks.items():
            looks_total = profile["looks"]
            episodes = sum(profile["looks_by_archive"].values()) and None
            per_episode[channel] = {
                "confirmed_looks_total": looks_total,
                "first_look_objects": profile["first_look_objects"],
                "objects_per_frame": profile["objects_per_frame"],
                "same_name_cooccurrence_frames": profile["same_name_cooccurrence_frames"],
            }
        spends = requests.get(case_id, [])
        profiles["cases"][case_id] = {
            "trigger_premise": {
                "subgoal_rows": reading["rows"],
                "dependencies": reading["dependencies"],
                "infeasible_rows": reading["edge_conditions"]["infeasible_rows"],
                "rows_with_another_occupant": reading["edge_conditions"]["rows_with_another_occupant"],
                "has_denominator_at_t0": reading["dependencies"] > 0,
                "note": ("the blocker edge needs an infeasible placement in an occupied region; "
                         "both counts are the t0 readings, and an episode can still create the "
                         "condition later -- which is what a trigger batch would measure, and v0.6 "
                         "measured that it never did"),
            },
            "demand": {
                **per_episode,
                "v06_final_requests_per_episode": spends,
                "v06_max_final_request": max(spends) if spends else None,
                "note": ("the bound is built from these numbers, not from a historical guess: "
                         "E2'''' reads max(final requests per episode) x episodes x 1.25, and the "
                         "final number is the one that includes the round the preflight admits"),
            },
        }

    path = os.path.join(HERE, "task_profiles.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=1)

    print(f"{'case':<30}{'rows':>5}{'edges':>6}{'denominator':>13}"
          f"{'stub looks':>11}{'vlm looks':>10}{'v06 max req/ep':>16}")
    for case_id, reading in profiles["cases"].items():
        trigger = reading["trigger_premise"]
        demand = reading["demand"]
        print(f"{case_id:<30}{trigger['subgoal_rows']:>5}{trigger['dependencies']:>6}"
              f"{str(trigger['has_denominator_at_t0']):>13}"
              f"{demand['stub']['confirmed_looks_total']:>11}"
              f"{demand['vlm']['confirmed_looks_total']:>10}"
              f"{str(demand['v06_max_final_request']):>16}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())