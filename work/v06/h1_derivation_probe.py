"""Why H1's trigger never fired: the derivation's own branch conditions, read offline.

H1's corrected reading says `trigger = 0` across 21 model-seat episodes on c2 and c3: the
derivation authored 5-6 subgoal rows per episode and **zero** dependencies. That is consistent with
v0.5 A2's H2 (187 initial views, `dependencies` always empty, 0 counterexamples), but "the
observations agree" is not "the mechanism is known". This file states the mechanism, for free, by
running the same `subgoals.derive` offline on each long-horizon case's initial snapshot with the
channel's own placement instrument, and reporting the two conditions the edge branches test:

* **the blocker branch** needs all three of: the row's placement verdict is not `true`, no
  candidate passes the instrument's re-check for that row (`feasible()` false), and some *other*
  body occupies the region. Any one of them false and no edge is authored;
* **the capacity branch** needs two rows competing for one region whose own feasible slot count is
  below the demand.

So this prints, per case: rows, edges by kind, the derivation's own notes, and for each row
whether feasibility held -- because "no edge" and "no edge *because every row was feasible*" are
different facts, and only the second one says the corpus cannot exercise this code path.

Zero requests, zero episodes: this reads the frozen cases and builds a scene.

Usage:  PYTHONPATH=. <py>
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

CASES = ["lh_c1_shared_pair_restore", "lh_c2_displaced_completion",
         "lh_c3_capacity_and_shift", "lh_c4_failed_grasp_recovery",
         "lh_c5_release_deviation", "lh_c6_two_disruptions"]


def main() -> int:
    import tempfile

    from embodied_agent.core.contracts import TaskInput
    from embodied_agent.core.events import EpisodeStore
    from embodied_agent.core.interpreter import interpret
    from embodied_agent.core.placement_planner import PlacementPlanner
    from embodied_agent.core.skills import SkillExecutor
    from embodied_agent.core.verify import RuntimeVerifier
    from embodied_agent.evaluation.calibration import cell_catalog
    from embodied_agent.evaluation.run import build_scene
    from embodied_agent.evaluation.tasks import find_case
    from embodied_agent.perception.arm import build_arm
    from embodied_agent.perception.grounding import GroundingMap
    from embodied_agent.planning import subgoals as SG

    out = {"cases": {}, "note": ("edges come from `subgoals.derive`, the deterministic derivation "
                                 "(P1's correction); the model seat supplies the world, not the "
                                 "graph")}
    for case_id in CASES:
        case = find_case(case_id, ("long_horizon",))
        scene = build_scene(case)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                catalog = cell_catalog(scene.trays.values())
                planner = PlacementPlanner(scene, case.verify)
                executor = SkillExecutor(scene, world_provider=lambda: None, config=case.verify)
                store = EpisodeStore(tmp, f"{case_id}.probe")
                # the channel's own privileged runtime, so the snapshot is the one an episode
                # would have started from rather than one this file assembled
                runtime = build_arm(case=case, scene=scene, executor=executor, store=store,
                                    run_dir=tmp, episode_id=f"{case_id}.probe",
                                    perceive="privileged", catalog=catalog,
                                    gmap=GroundingMap.from_objects(case.objects),
                                    budgets=case.budgets)
                executor.placement_planner = planner
                runtime.placement_planner = planner
                world = runtime.observe()
                task = TaskInput(task_id=case.task_id, utterance=case.utterance)
                goal = interpret(task, world)
                progress = RuntimeVerifier(world).progress(goal)
                derivation = SG.derive(goal, world, task, planner=planner, progress=progress)

                rows = []
                for sub in derivation.subgoals:
                    eid = sub.target_entity_ids[0] if sub.target_entity_ids else ""
                    tid = sub.target_region_id or ""
                    verdict = next(
                        (i.value for i in progress
                         if str(i.predicate_id) == SG.placement_predicate(eid, tid)), None)
                    feasible = None
                    reason = None
                    if tid and eid:
                        f = SG.feasibility(planner, eid, tid, world)
                        feasible, reason = bool(f.feasible), f.first_reason
                    rows.append({"subgoal_id": sub.subgoal_id, "entity_id": eid, "target_id": tid,
                                 "placement_verdict": str(verdict),
                                 "feasible": feasible, "feasibility_reason": reason,
                                 "region_occupants_other": [o for o in SG.occupants(world, tid)
                                                             if o != eid],
                                 "satisfied": str(sub.satisfied.value)})
                out["cases"][case_id] = {
                    "rows": len(derivation.subgoals),
                    "dependencies": len(derivation.dependencies),
                    "dependency_kinds": sorted({str(d.kind.value) for d in derivation.dependencies}),
                    "notes": list(derivation.notes),
                    "have_placement_instrument": True,
                    "rows_detail": rows,
                    "edge_conditions": {
                        "verdict_true_rows": sum(1 for r in rows
                                                  if r["placement_verdict"] == "true"),
                        "infeasible_rows": sum(1 for r in rows if r["feasible"] is False),
                        "rows_with_another_occupant": sum(1 for r in rows
                                                          if r["region_occupants_other"]),
                    },
                }
            finally:
                scene.close()

    path = os.path.join(REPO, "work", "v06", "h1_derivation_probe.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"{'case':<32}{'rows':>5}{'edges':>6}  {'infeasible':>11}{'verdict_true':>13}"
          f"{'occupant_rows':>14}  notes")
    for case_id, reading in out["cases"].items():
        c = reading["edge_conditions"]
        print(f"{case_id:<32}{reading['rows']:>5}{reading['dependencies']:>6}  "
              f"{c['infeasible_rows']:>11}{c['verdict_true_rows']:>13}"
              f"{c['rows_with_another_occupant']:>14}  {len(reading['notes'])}")
    for case_id, reading in out["cases"].items():
        for note in reading["notes"]:
            print(f"  note [{case_id}] {note}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())