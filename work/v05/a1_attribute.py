"""v0.5 A1: which ring killed each of E2''s eight dead episodes.

The one reading instrument for RQ11. The criteria it implements were written down first, in
`docs/continuous-decision-v0.5-phase-log.md` ("P2 A1 判据"), and are not restated here --
they are quoted where a judgement is made, so that a reader can check this file against the
text it was asked to implement. The shape of the argument:

* one **declared item** per goal assignment, `(color, shape) -> target`, read from the
  episode's own shared goal resolution (identical across the three channels for one
  `(case, repeat)`, which is what makes the three cells comparable);
* one **round** per `decision_context` event, and one **frame** per observation (the k-th
  look is the k-th observation in both camera cells: `summary.perception.looks` equals the
  `observation` event count, 26/26 and 15/15);
* the loop's own view of the world is the `progress` / `candidates` it was handed, not a
  `WorldState` this file rebuilds. A rebuilt world would be a second opinion about the
  question under test.

Four rings, measured separately and then ranked by a pre-registered precedence (a -> b ->
c), because the rings are a causal chain: a body the frame never saw cannot be bound, and a
body that was never bound cannot be acted on. Multi-ring answers are readings, not failures
(SPEC §10.1).

Reads the E2' archive read-only; writes `work/v05/a1_attribute.json` and prints the
per-episode evidence chain. Costs nothing: the stub channel's frame-side data comes from
`a1_stub_replay.py`, a deterministic offline replay of that channel's own reader.

Usage:  PYTHONPATH=. <py> work/v05/a1_attribute.py
"""
from __future__ import annotations

import collections
import json
import os

from embodied_agent.evaluation.tasks import COLORS, SHAPES

E2 = "/home/czx/embodied-agent-batches/v04/e2"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHANNELS = ("privileged", "stub", "vlm")
RINGS = ("a_frame_detection", "b_binding", "c_decision_availability", "d_prompt")
PRECEDENCE = RINGS[:3]           # d is scored, never ranked: see the criteria's rule 1


# ------------------------------------------------------------------ archive ----

def _run(channel: str) -> str:
    root = os.path.join(E2, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    assert len(runs) == 1, runs
    return os.path.join(root, runs[0])


def _events(ep_dir: str) -> list[dict]:
    with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _stub_replay() -> dict:
    path = os.path.join(REPO, "work", "v05", "a1_stub_replay.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {e["episode_id"]: e for e in data["episodes"]}


# ------------------------------------------------------------------- frames ----

def _detection(d: dict) -> tuple[str, str]:
    attrs = d.get("state_attributes") or {}
    eid = str(d.get("entity_id") or "")
    colour = str(attrs.get("color") or (eid.split(":", 1)[1] if eid.startswith("seen:") else ""))
    return colour, str(attrs.get("shape") or "")


def vlm_frames(events: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """observation_ref -> [(color, shape)] for every archived percept."""
    out = {}
    for e in events:
        if e["type"] != "perception":
            continue
        payload = e["payload"]
        out[payload.get("observation_id") or payload.get("observation_ref")] = [
            _detection(d) for d in payload.get("detections") or []]
    return out


def stub_frames(replay_rows: list[dict]) -> list[list[tuple[str, str]]]:
    return [[(o["color"], o["shape"]) for o in look["objects"]] for look in replay_rows]


# ---------------------------------------------------------------- the reader ----

def analyse(channel: str, ep_id: str, ep_dir: str, replay: dict) -> dict:
    with open(os.path.join(ep_dir, "episode_summary.json"), encoding="utf-8") as f:
        summary = json.load(f)
    events = _events(ep_dir)
    result = summary.get("result") or {}

    assignments = [(a[0] if isinstance(a[0], dict) else {}, a[1])
                   for a in (summary.get("goal_resolution") or {}).get("assignments") or []]

    # observation ordinals, and the frames behind them
    obs_index = {}
    for index, e in enumerate(events):
        if e["type"] == "observation":
            obs_index[(e["payload"].get("observation") or {}).get("observation_ref")] = index
    if channel == "vlm":
        by_ref = vlm_frames(events)
    elif channel == "stub":
        rows = (replay.get(ep_id) or {}).get("looks") or []
        by_index = stub_frames(rows)
        by_ref = None
    else:
        by_index, by_ref = None, None

    def frame_for(ref: str):
        if channel == "vlm":
            return by_ref.get(ref, [])
        if channel == "stub":
            return by_index[obs_index[ref]] if ref in obs_index and obs_index[ref] < len(by_index) else []
        return None

    rounds = [e["payload"] for e in events if e["type"] == "decision_context"]
    decisions = [e["payload"] for e in events if e["type"] == "decision"]
    feedbacks = [(e["payload"].get("feedback") or {}) for e in events
                 if e["type"] == "execution_feedback"]
    blocked = [e["payload"] for e in events if e["type"] == "terminated_blocked"]
    rejection_reasons = collections.Counter(
        r for fb in feedbacks for r in (fb.get("rejection_reasons") or []))
    failure_histogram = collections.Counter(fb.get("failure_code") or "none" for fb in feedbacks)
    # what actually happened to each action the loop submitted, keyed by decision id:
    # ring c's "动作无效" half is read off this, not off the ledger's counters.
    outcome_by_decision = {}
    for fb in feedbacks:
        outcome_by_decision[fb.get("decision_id")] = {
            "status": fb.get("status"), "executed": fb.get("executed"),
            "failure_code": fb.get("failure_code"),
            "rejection_reasons": fb.get("rejection_reasons") or []}

    items = []
    for i, (attrs, target) in enumerate(assignments):
        declared = {k: str(v) for k, v in attrs.items()}
        colour, shape = declared.get("color", ""), declared.get("shape", "")
        per_round = []
        for r in rounds:
            rows = r.get("progress") or []
            row = rows[i] if i < len(rows) else {}
            assert row.get("target_id") == target, (ep_id, i, row.get("target_id"), target)
            unbound = "entity_binding" in (row.get("unmeasured") or [])
            detections = frame_for(r.get("observation_ref") or "")
            both = [d for d in (detections or []) if d[0] == colour and d[1] == shape]
            colour_hits = [d for d in (detections or []) if d[0] == colour]
            if unbound:
                if detections is None or not colour_hits:
                    mode = "frame_did_not_see_the_colour"
                elif len(both) >= 2:
                    mode = "ambiguous_after_binding"
                elif len(both) == 1:
                    mode = "unbound_with_a_unique_match"
                else:
                    mode = "shape_mismatch"
            else:
                mode = "bound"
            per_round.append({
                "round": r.get("round_index"), "state_version": r.get("state_version"),
                "bound": not unbound, "entity_id": row.get("entity_id"),
                "value": row.get("value"),
                "actionable": any(c.get("entity_id") == row.get("entity_id")
                                  for c in (r.get("candidates") or [])),
                "detections_in_frame": colour_hits,
                "declared": declared, "mode": mode})

        ever_bound = any(p["bound"] for p in per_round)
        ever_actionable = any(p["actionable"] for p in per_round)
        frames_with_colour = sum(1 for p in per_round if p["detections_in_frame"])
        # the decisions that named this item, and what came back
        ids = {p["entity_id"] for p in per_round if p["bound"]}
        mine = [d for d in decisions
                if str(((d.get("execute") or {}).get("args") or {}).get("object_id") or "") in ids]
        mine_outcomes = [outcome_by_decision.get(d.get("decision_id")) for d in mine]
        mine_failed = [o for o in mine_outcomes
                       if o and (o.get("failure_code") or o.get("rejection_reasons")
                                 or not o.get("executed"))]

        # --- ring verdicts, at the level the criteria fix them ---------------------
        unbound_rounds = [p for p in per_round if not p["bound"]]
        # a: the colour was absent from *every* frame (an occasional miss is not a
        # death cause; the criteria set the whole-episode threshold on purpose).
        # Two guards, both corrections found by the v0.5 document gate:
        #   * a channel with no camera at all has no frames to miss anything in -- the
        #     criteria write `n/a` in that column for `privileged`, and "the frame did not
        #     see it" is not a statement a channel without frames can make;
        #   * an item that was bound in every round has no binding to attribute, so the
        #     detection verdict is only reached from an unbound one.
        frames_available = channel != "privileged"
        ring_a = bool(unbound_rounds) and frames_available and frames_with_colour == 0
        ring_b = bool(unbound_rounds) and not ring_a
        ring_c_item = (ever_bound and not ever_actionable) or (bool(mine) and
                                                               len(mine_failed) == len(mine))
        contributions = []
        if ring_a:
            contributions.append("a_frame_detection")
        if ring_b:
            contributions.append("b_binding")
        if ring_c_item:
            contributions.append("c_decision_availability")
        verdict = next((ring for ring in PRECEDENCE if ring in contributions), "")
        items.append({
            "index": i, "declared": declared, "target": target,
            "rounds": per_round,
            "rounds_total": len(per_round),
            "rounds_bound": sum(1 for p in per_round if p["bound"]),
            "rounds_unbound": len(unbound_rounds),
            "rounds_actionable": sum(1 for p in per_round if p["actionable"]),
            "rounds_frame_saw_colour": frames_with_colour,
            "rounds_frame_missed": len(per_round) - frames_with_colour,
            "actions_on_item": len(mine), "actions_on_item_failed": len(mine_failed),
            "ever_bound": ever_bound, "ever_actionable": ever_actionable,
            "stable_binding": ever_bound and not unbound_rounds,
            "modes": sorted(set(p["mode"] for p in per_round)),
            "ring_contributions": contributions,
            "dominant_ring": verdict,
        })

    # ring c, at episode level (criteria row c, second clause): every declared item was
    # actionable at least once, and the episode still ended on one of the three control
    # outcomes -- a legal action that cannot be executed, not a world nobody can act in.
    all_actionable = all(it["ever_actionable"] for it in items)
    control_outcome = result.get("failure_type") in ("REPEATED_INVALID", "BUDGET_EXHAUSTED") or bool(blocked)
    ring_c_episode = bool(items) and all_actionable and control_outcome

    # ring d, vlm only: what the prompt/parse layer did per request
    calls = _jsonl(os.path.join(ep_dir, "model_calls.jsonl"))
    prompt = {
        "calls": len(calls),
        "ok": collections.Counter(str(bool(c.get("ok"))) for c in calls),
        "finish_reason": collections.Counter(str(c.get("finish_reason")) for c in calls),
        "format_repairs": sum(int(c.get("format_repairs_this_call") or 0) for c in calls),
        "schema_errors": sum(1 for c in calls if c.get("schema_errors")),
        "raw_unparseable": 0,
        "colour_outside_vocab": 0,
        "shape_outside_vocab": 0,
    }
    for call in calls:
        raw = str(call.get("raw_response") or "")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = {}
            if raw:
                prompt["raw_unparseable"] += 1
        for obj in (payload.get("objects") or []):
            if str(obj.get("color")) not in COLORS:
                prompt["colour_outside_vocab"] += 1
            if obj.get("shape") and str(obj.get("shape")) not in SHAPES:
                prompt["shape_outside_vocab"] += 1

    ring_counts = {ring: sum(1 for it in items if ring in it["ring_contributions"])
                   for ring in RINGS}
    dominant = next((ring for ring in PRECEDENCE if ring_counts[ring] == max(ring_counts.values())
                     and ring_counts[ring] > 0), "")
    return {
        "channel": channel, "episode_id": ep_id, "case_id": summary.get("case_id"),
        "terminal_status": result.get("terminal_status"), "failure_type": result.get("failure_type"),
        "termination_reason": result.get("termination_reason"),
        "decision_rounds": result.get("decision_rounds"), "skill_calls": result.get("skill_calls"),
        "objects_completed": result.get("objects_completed"),
        "objects_total": result.get("objects_total"),
        "identical_invalid_attempts": result.get("identical_invalid_attempts"),
        "perception": summary.get("perception"),
        "items": items,
        "actions": [{"action": d.get("action"),
                     "execute": (d.get("execute") or {}).get("args"),
                     "rationale": d.get("rationale"),
                     "outcome": outcome_by_decision.get(d.get("decision_id"))} for d in decisions],
        "feedback": {"count": len(feedbacks),
                     "failure_codes": dict(failure_histogram),
                     "rejection_reasons": dict(rejection_reasons)},
        "blocked": blocked,
        "prompt": prompt,
        "ring_item_counts": ring_counts,
        "ring_c_episode": ring_c_episode,
        "dominant_ring": dominant,
    }


def main() -> int:
    replay = _stub_replay()
    report = {"archive": E2, "cells": []}
    for channel in CHANNELS:
        run = _run(channel)
        for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
            cell = analyse(channel, ep, os.path.join(run, "episodes", ep), replay)
            report["cells"].append(cell)

    out = os.path.join(REPO, "work", "v05", "a1_attribute.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    for cell in report["cells"]:
        print(f"\n=== {cell['channel']:<11} {cell['episode_id']}  "
              f"{cell['terminal_status']}/{cell['failure_type']}  "
              f"objects {cell['objects_completed']}/{cell['objects_total']}  "
              f"dominant={cell['dominant_ring'] or '-'}  rings={cell['ring_item_counts']}  "
              f"c_episode={cell['ring_c_episode']}")
        for it in cell["items"]:
            print(f"   item{it['index']} {it['declared']} -> {it['target']}: "
                  f"bound {it['rounds_bound']}/{it['rounds_total']}, "
                  f"actionable {it['rounds_actionable']}/{it['rounds_total']}, "
                  f"frame-saw-colour {it['rounds_frame_saw_colour']}/{it['rounds_total']} "
                  f"(missed {it['rounds_frame_missed']}), "
                  f"actions {it['actions_on_item']} failed {it['actions_on_item_failed']}, "
                  f"modes={it['modes']} -> {it['dominant_ring'] or '-'}")
        print("   actions: " + str([(a["action"], (a["execute"] or {}).get("object_id"),
                                     (a["outcome"] or {}).get("failure_code"))
                                    for a in cell["actions"]]))
        print(f"   feedback: {cell['feedback']}")
        if cell["blocked"]:
            print(f"   blocked: {cell['blocked']}")
        if cell["channel"] == "vlm":
            print(f"   prompt: {cell['prompt']}")
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())