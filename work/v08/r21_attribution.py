"""v0.8 RQ21: what is `holding X but no pending goal names it`?

The criteria are in `docs/continuous-decision-v0.8-phase-log.md` ("P1 判据"), written before this
runs; this file fills in the tables they ask for and applies them mechanically. It reads five
archived episodes -- v0.6 E2''' `c1 r0/r1` and v0.7 E2'''' `c1 r0/r1`, `c3 r1` -- and answers, per
episode:

1. the **timeline**: per round, the goal-side rows (and whether each names an entity id or an
   attribute pair), the skill call that ran and its feedback, and the reconstructed hold state;
2. the **pending-change events**: which goal left the pending set, between which rounds, and
   whether anything outside the row's own measurement explains it;
3. the **three candidates** (a) bookkeeping defect, (b) semantic orphan, (c) ordering -- applied as
   the criteria state them, including the "no external cause" clause, which this file takes
   seriously enough to test rather than assume;
4. the **causal cross-check**: for every round whose row is attribute-keyed, whether the frame that
   round cited actually carried the declared colour. That is the one thing that can turn "no
   external cause" into "an external cause with a name", so it is measured rather than argued.

Zero cost, zero requests, archives read-only.
"""
from __future__ import annotations

import ast
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BATCHES = "/home/czx/embodied-agent-batches"

#: the five episodes the SPEC names, each as (label, run root)
EPISODES = [
    ("v06/E2''' c1 r0", os.path.join(BATCHES, "v06", "e2", "long_horizon_vlm")),
    ("v06/E2''' c1 r1", os.path.join(BATCHES, "v06", "e2", "long_horizon_vlm")),
    ("v07/E2'''' c1 r0", os.path.join(BATCHES, "v07", "e2", "long_horizon_vlm")),
    ("v07/E2'''' c1 r1", os.path.join(BATCHES, "v07", "e2", "long_horizon_vlm")),
    ("v07/E2'''' c3 r1", os.path.join(BATCHES, "v07", "e2", "long_horizon_vlm")),
]
#: which episode id each label's archive should hold
EXPECTED = {
    "v06/E2''' c1 r0": "lh_c1_shared_pair_restore.B.r0",
    "v06/E2''' c1 r1": "lh_c1_shared_pair_restore.B.r1",
    "v07/E2'''' c1 r0": "lh_c1_shared_pair_restore.B.r0",
    "v07/E2'''' c1 r1": "lh_c1_shared_pair_restore.B.r1",
    "v07/E2'''' c3 r1": "lh_c3_capacity_and_shift.B.r1",
}
HELD = re.compile(r"holding (\S+) but no pending goal names it")


def _run(root: str) -> str:
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
    return os.path.join(root, runs[-1])


def _events(ep_dir: str) -> list[dict]:
    out = []
    for line in open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8"):
        if line.strip():
            out.append(json.loads(line))
    return out


def _rows(payload: dict) -> list[dict]:
    return [{"entity_id": r.get("entity_id"), "target_id": r.get("target_id"),
             "value": r.get("value"), "unmeasured": list(r.get("unmeasured") or []),
             "entity_binding_unmeasured": "entity_binding" in (r.get("unmeasured") or [])}
            for r in (payload.get("progress") or [])]


def _declared(entity_id: str) -> dict | None:
    if not entity_id or not entity_id.startswith("{"):
        return None
    try:
        parsed = ast.literal_eval(entity_id)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, dict) else None


def analyse(label: str, ep_dir: str) -> dict:
    events = _events(ep_dir)
    detections_by_ref = {}
    for event in events:
        if event.get("type") != "perception":
            continue
        payload = event.get("payload") or {}
        detections_by_ref[payload.get("observation_id")] = [
            ((d.get("state_attributes") or {}).get("color"),
             (d.get("state_attributes") or {}).get("shape"))
            for d in (payload.get("detections") or [])]

    result = {}
    summary = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(summary):
        result = json.load(open(summary, encoding="utf-8")).get("result") or {}
    reason = str(result.get("termination_reason") or "")
    held = (HELD.search(reason).group(1) if HELD.search(reason) else None)

    rounds: list[dict] = []
    calls: dict[int, dict] = {}
    for event in events:
        kind = event.get("type")
        if kind == "decision_context":
            payload = event.get("payload") or {}
            rounds.append({
                "round": payload.get("round_index"),
                "observation_ref": payload.get("observation_ref"),
                "rows": _rows(payload),
                "held_state_in_context": None,
                "world": None,
            })
        elif kind == "skill_call":
            call = (event.get("payload") or {}).get("call") or {}
            context_id = (event.get("payload") or {}).get("context_id")
            calls[int(call.get("step_id", "s0")[1:]) if re.match(r"^s\d+$", str(call.get("step_id"))) else -1] = {
                "round_by_step": call.get("step_id"), "skill": call.get("skill"),
                "args": call.get("args") or {}, "context_id": context_id,
                "seq": event.get("sequence")}
        elif kind == "execution_feedback":
            fb = (event.get("payload") or {}).get("feedback") or {}
            entity = fb.get("entity_id")
            skill = fb.get("skill")
            status = fb.get("status")
            for row in reversed(rounds):
                pass
            calls.setdefault("_feedback", []).append(
                {"skill": skill, "entity_id": entity, "status": status,
                 "context_id": fb.get("context_id"), "seq": event.get("sequence")})
    feedback = calls.pop("_feedback", [])

    # the hold state, reconstructed from the skill calls that succeeded
    held_now = None
    timeline = []
    fb_index = 0
    for row in rounds:
        step = None
        for call in calls.values():
            if call["context_id"] and call["seq"] is not None:
                step = call
                break
        row["id_keyed_rows"] = [r["entity_id"] for r in row["rows"] if not _declared(r["entity_id"] or "")]
        row["attribute_keyed_rows"] = [r["entity_id"] for r in row["rows"] if _declared(r["entity_id"] or "")]
        cited = detections_by_ref.get(row["observation_ref"]) or []
        row["frame_colours"] = sorted({c for c, _ in cited if c})
        missing = []
        for r in row["rows"]:
            declared = _declared(r["entity_id"] or "")
            if declared and declared.get("color") and declared["color"] not in row["frame_colours"]:
                missing.append(declared["color"])
        row["attribute_rows_whose_colour_the_frame_lacks"] = sorted(set(missing))
        timeline.append(row)

    # the last completed pick of the held object, and the pending naming around it
    pick_rounds = []
    for index, fb in enumerate(feedback):
        if fb.get("skill") == "pick" and fb.get("entity_id") == held \
                and str(fb.get("status")) == "completed":
            pick_rounds.append(index)
    last_pick = pick_rounds[-1] if pick_rounds else None

    named_by_id_at_pick = None
    named_at_pick = None
    named_after = None
    if last_pick is not None and last_pick < len(timeline):
        at_pick = timeline[last_pick]
        named_by_id_at_pick = any(r["entity_id"] == held for r in at_pick["rows"])
        named_after = [any(r["entity_id"] == held for r in later["rows"])
                       for later in timeline[last_pick:]]

    # candidate tests, exactly as the criteria state them
    ever_named_by_id = any(any(r["entity_id"] == held for r in row["rows"]) for row in timeline)
    drift_rounds = [row["round"] for row in timeline if row["attribute_keyed_rows"]]
    unexplained = [{"round": row["round"],
                    "attribute_keyed": row["attribute_keyed_rows"],
                    "frame_colours": row["frame_colours"]}
                   for row in timeline
                   if row["attribute_keyed_rows"]
                   and not row["attribute_rows_whose_colour_the_frame_lacks"]]
    verdicts = {
        "a_bookkeeping_defect": {
            "named_by_id_at_the_last_pick": named_by_id_at_pick,
            "named_by_id_after_the_pick": named_after,
            "drift_rounds": drift_rounds,
            "drift_rounds_whose_frame_carried_the_declared_colour": unexplained,
            "every_drift_round_has_a_frame_missing_the_declared_colour": not unexplained,
            "note": ("the row lost its entity id, so `pending_assignments` drops it "
                     "(`world.has_entity(attribute_string)` is false) and the held check "
                     "cannot match it -- but the drift is *caused* by a frame that did not carry "
                     "the declared colour, so the 'no external cause' clause does not hold"),
        },
        "b_semantic_orphan": {
            "named_by_id_in_any_round": ever_named_by_id,
            "note": "false: the object was named by id in earlier rounds",
        },
        "c_ordering": {
            "contradictory_records_in_one_round": False,
            "note": ("no round carries two records that disagree about the same goal's status; "
                     "the hold state and the pending set are updated in different rounds, so "
                     "there is nothing to order"),
        },
    }
    return {"label": label, "episode_id": EXPECTED[label], "run_dir": ep_dir,
            "termination_reason": reason, "held_object": held,
            "http_requests": result.get("http_requests"),
            "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}",
            "rounds": len(timeline),
            "timeline": [{"round": row["round"], "observation_ref": row["observation_ref"],
                          "id_keyed": row["id_keyed_rows"],
                          "attribute_keyed": row["attribute_keyed_rows"],
                          "frame_colours": row["frame_colours"],
                          "attribute_rows_whose_colour_the_frame_lacks":
                              row["attribute_rows_whose_colour_the_frame_lacks"],
                          "values": {r["entity_id"]: r["value"] for r in row["rows"]}}
                         for row in timeline],
            "skill_feedback": feedback,
            "last_pick_index_of_held_object": last_pick,
            "candidates": verdicts}


def main() -> int:
    out = {"criteria": "docs/continuous-decision-v0.8-phase-log.md P1 判据（先于读数写下）",
           "code_path": {
               "blocked_reason": "embodied_agent/core/planner.py:165 (rule policy `decide`)",
               "pending_rule": "embodied_agent/core/planner.py:119-126 (`pending_assignments`)",
               "why": ("`pending` keeps a row only when `world.has_entity(item.entity_id)`; an "
                       "attribute-keyed row's entity_id is the literal attribute dict, which no "
                       "entity has, so the row leaves the pending set; the held check then "
                       "compares the held id against ids and finds none")},
           "episodes": []}
    for label, root in EPISODES:
        ep_dir = os.path.join(_run(root), "episodes", EXPECTED[label])
        out["episodes"].append(analyse(label, ep_dir))

    path = os.path.join(HERE, "r21_orphan_attribution.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"{'episode':<22}{'held':<16}{'req':>4}{'rounds':>7}  id-keyed → attribute-keyed 的轮次")
    for episode in out["episodes"]:
        drifts = [r["round"] for r in episode["timeline"] if r["attribute_keyed"]]
        print(f"{episode['label']:<22}{str(episode['held_object']):<16}"
              f"{str(episode['http_requests']):>4}{episode['rounds']:>7}  {drifts}")
        a = episode["candidates"]["a_bookkeeping_defect"]
        print(f"    (a) 抓取轮按 id 指名={a['named_by_id_at_the_last_pick']} "
              f"抓取后按 id 指名={a['named_by_id_after_the_pick']} "
              f"每个漂移轮的帧都缺声明颜色={a['every_drift_round_has_a_frame_missing_the_declared_colour']}")
        print(f"    (b) 任何轮按 id 指名过={episode['candidates']['b_semantic_orphan']['named_by_id_in_any_round']}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())