"""v0.6 B2: when does `bind_attributes` refuse, and what would each of the three candidates
then be buying.

The criteria are in `docs/continuous-decision-v0.6-phase-log.md` ("P2 判据", B2-1..B2-3).
Three things shape this file:

* the branch has never fired in any real batch (v0.5 negative result #7), so B2-1 re-derives
  that from the archives rather than citing it, and B2-2/3 have to *build* the situation --
  the construction is the instrument here, not an extra archive to find;
* the branch's condition is exactly "`bind_attributes` found **two or more** entities matching
  every declared attribute", so the three reachable paths are the three ways a frame can
  produce that: two bodies with identical attributes, two bodies whose *measured* attributes
  collapsed onto the declared pair, and a grounding refusal that leaves two frame-named
  entities matching it;
* candidate i ("bind by per-frame uniqueness") is only as good as the frame's uniqueness, so
  the instrument **measures** it: for every ambiguous-colour item in the archives, how many
  frames see exactly one body of that colour, and how many see two. A candidate whose premise
  is measured at 0% is not a candidate, and the number belongs in front of D4''' rather than
  behind it.

Reads archives read-only; writes `work/v06/b2_ambiguity.json`; spends nothing.

Usage:  PYTHONPATH=. <py> work/v06/b2_ambiguity.py
"""
from __future__ import annotations

import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "work", "v05"))
sys.path.insert(0, os.path.join(REPO, "work", "v06"))

from embodied_agent.core.contracts import EntityRef, EntityState, GoalAssignment, GoalSpec, WorldState  # noqa: E402
from embodied_agent.core.verify import RuntimeVerifier, bind_attributes  # noqa: E402

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
CHANNELS = ("stub", "vlm")


def _run(arc: str, channel: str) -> str:
    root = os.path.join(ARCS[arc], f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
    return os.path.join(root, runs[-1])


def _events(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def frame_detections(arc: str, channel: str, ep_dir: str, replay: dict):
    """`(colour, shape)` per observation, same alignment A1/B1 used."""
    if channel == "vlm":
        by_ref = {}
        for e in _events(os.path.join(ep_dir, "events.jsonl")):
            if e["type"] != "perception":
                continue
            payload = e["payload"]
            rows = []
            for det in payload.get("detections") or []:
                attrs = det.get("state_attributes") or {}
                eid = str(det.get("entity_id") or "")
                colour = str(attrs.get("color") or (eid.split(":", 1)[1] if eid.startswith("seen:") else ""))
                rows.append((colour, str(attrs.get("shape") or "")))
            by_ref[payload.get("observation_id") or payload.get("observation_ref")] = rows
        ordinals = {}
        for index, e in enumerate(_events(os.path.join(ep_dir, "events.jsonl"))):
            if e["type"] == "observation":
                ordinals[(e["payload"].get("observation") or {}).get("observation_ref")] = index
        series = [None] * (len(ordinals) + 1)
        for ref, index in ordinals.items():
            if index < len(series):
                series[index] = by_ref.get(ref, [])
        return [s or [] for s in series]
    rows = replay.get(f"{arc}:{os.path.basename(ep_dir)}") or {}
    return [[(o["color"], o["shape"]) for o in look["objects"]] for look in rows.get("looks", [])]


def scan_archives(replay: dict) -> dict:
    """B2-1 + candidate i's premise, over every camera episode of both archives."""
    ambiguous_modes = collections.Counter()
    per_colour_frames = collections.Counter()
    for arc in ARCS:
        for channel in CHANNELS:
            run = _run(arc, channel)
            for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
                ep_dir = os.path.join(run, "episodes", ep)
                if not os.path.exists(os.path.join(ep_dir, "episode_summary.json")):
                    continue
                series = frame_detections(arc, channel, ep_dir, replay)
                # B2-1: a frame in which two or more detections carry the *same* attribute pair
                # is the only way the refusal can be reached from a frame; count them, and
                # count the same-colour frames so candidate i's premise is a measurement
                for frame in series:
                    pairs = collections.Counter(frame)
                    ambiguous_modes[f"{arc}|{channel}|ambiguous_pairs"] += sum(
                        1 for n in pairs.values() if n > 1)
                    for colour in {c for c, _ in frame}:
                        per_colour_frames[f"{arc}|{channel}|{colour}"] += 1
    return {"identical_attribute_pairs_in_frames": dict(ambiguous_modes),
            "frames_by_colour": dict(per_colour_frames)}


def candidate_i_premise(replay: dict) -> dict:
    """How often a frame sees exactly one body of a colour that the declaration gives twice.

    Candidate i ("bind by per-frame uniqueness") is only sound when the frame *is* unique.
    This counts it, per archive/channel/colour, and separates it from the frames that see two or
    more -- c3's two yellows are the whole question.
    """
    out = collections.defaultdict(lambda: collections.Counter())
    for arc in ARCS:
        for channel in CHANNELS:
            run = _run(arc, channel)
            for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
                ep_dir = os.path.join(run, "episodes", ep)
                if not os.path.exists(os.path.join(ep_dir, "episode_summary.json")):
                    continue
                for frame in frame_detections(arc, channel, ep_dir, replay):
                    counts = collections.Counter(c for c, _ in frame)
                    for colour, n in counts.items():
                        key = f"{arc}|{channel}|{colour}"
                        out[key]["frames"] += 1
                        out[key]["unique" if n == 1 else ("two" if n == 2 else "three+")] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


def synthetic_paths() -> dict:
    """B2-2: the three reachable paths, built, with what each does to the binding."""
    def world(*entities):
        return WorldState(state_version=1, sim_time=0.0, wall_time=0.0,
                          entities=list(entities), targets=[])

    def entity(eid, colour, shape):
        return EntityState(entity_id=eid, attributes={"color": colour, "shape": shape})

    attrs = {"color": "yellow", "shape": "cube"}
    goal = GoalSpec(assignments=[GoalAssignment(entity=EntityRef(attributes=attrs),
                                                 target_id="tray_middle")])
    paths = {
        "two bodies with identical measured attributes": world(
            entity("obj_yellow_1", "yellow", "cube"), entity("obj_yellow_6", "yellow", "cube")),
        "two bodies whose measured attributes collapsed onto the declared pair": world(
            entity("obj_yellow_1", "yellow", "cuboid"), entity("obj_yellow_6", "yellow", "cuboid")),
        "a grounding refusal leaving two frame-named entities matching": world(
            entity("seen:yellow", "yellow", "cube"), entity("seen:yellow_2", "yellow", "cube")),
    }
    out = {}
    for name, w in paths.items():
        verifier = RuntimeVerifier(w)
        bound = verifier.bind(goal.assignments[0])
        (item,) = verifier.progress(goal)
        out[name] = {
            "entities": [e.entity_id for e in w.entities],
            "bind_attributes": bind_attributes(attrs, w),
            "verifier_bind": bound,
            "unmeasured": list(item.unmeasured or []),
            "value": item.value.value,
        }
    # and the shape that must not be confused with the refusal: one entity, wrong shape
    alone = world(entity("obj_yellow_1", "yellow", "cuboid"))
    verifier = RuntimeVerifier(alone)
    out["one entity, wrong shape (NOT the ambiguity branch)"] = {
        "entities": ["obj_yellow_1"],
        "bind_attributes": bind_attributes(attrs, alone),
        "verifier_bind": verifier.bind(goal.assignments[0]),
        "unmeasured": list(verifier.progress(goal)[0].unmeasured or []),
        "value": verifier.progress(goal)[0].value.value,
    }
    return out


def main() -> int:
    replay = {}
    with open(os.path.join(REPO, "work", "v06", "stub_replay.json"), encoding="utf-8") as f:
        for episode in json.load(f)["episodes"]:
            replay[f"{episode['archive']}:{episode['episode_id']}"] = episode

    report = {
        "criteria": "docs/continuous-decision-v0.6-phase-log.md, P2 判据 B2",
        "b2_1_archive_scan": scan_archives(replay),
        "candidate_i_premise": candidate_i_premise(replay),
        "b2_2_paths": synthetic_paths(),
    }
    path = os.path.join(REPO, "work", "v06", "b2_ambiguity.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print("\n== B2-1 frames carrying an identical (colour, shape) pair")
    for key, n in sorted(report["b2_1_archive_scan"]["identical_attribute_pairs_in_frames"].items()):
        print(f"   {key:<44} {n}")
    print("\n== candidate i's premise: frames per colour, by uniqueness")
    for key, counts in sorted(report["candidate_i_premise"].items()):
        if key.endswith("|yellow"):
            print(f"   {key:<44} {counts}")
    print("\n== B2-2 the three reachable paths (built)")
    for name, row in report["b2_2_paths"].items():
        print(f"   {name:<62} bind_attributes={row['bind_attributes']!r} "
              f"verifier_bind={row['verifier_bind']!r} unmeasured={row['unmeasured']}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())