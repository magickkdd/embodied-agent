"""v0.6 B1 supplement: is there a reader-side repair with a ceiling at all?

B1 answered the fusion-window option (SPEC §5 B1, criteria B1-1..B1-3): a past-frame window
supplies a *colour* at 10-11 of 64 missing item-rounds and the declared *shape* at **none of
them**, so it cannot repair the binding this residual is about. What B1 does not answer is the
other #26 option the ruling is named for -- repairing the reader itself -- and that one is
measurable for free on the stub channel, because `StubReader` is a deterministic algorithm and
the frames are on disk with their digests.

So: replay every archived stub frame under a grid of the reader's two public knobs
(`min_pixels`, `hue_tol_deg`) and count, per setting, how many of the colour-missing item-rounds
B1 found would have had their colour detected, and how many of those would also have carried
the declared shape. Two numbers, same corpus, no requests, and the setting that wins is a
measurement rather than an opinion.

The VLM channel is deliberately **not** in this scan: its knobs are a prompt and a model, and
re-qualifying a prompt costs requests, which is a pre-registration question (D5'''), not a
zero-cost one.

Usage:  PYTHONPATH=. <py> work/v06/b1_reader_scan.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import os

from embodied_agent.evaluation.calibration import cell_catalog
from embodied_agent.evaluation.run import build_scene
from embodied_agent.evaluation.tasks import find_case
from embodied_agent.perception.frames import SensorFrame, camera_for
from embodied_agent.perception.observe import StubReader

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
#: the shipped setting first, then the two knobs moved one at a time and together
GRID = [(120, 22.0), (80, 22.0), (200, 22.0), (120, 15.0), (120, 30.0), (80, 15.0), (60, 15.0)]


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _episodes(arc: str) -> list[str]:
    root = os.path.join(ARCS[arc], "long_horizon_stub")
    run = sorted(d for d in os.listdir(root)
                 if os.path.isdir(os.path.join(root, d, "episodes")))[-1]
    ep_root = os.path.join(root, run, "episodes")
    return [os.path.join(ep_root, ep) for ep in sorted(os.listdir(ep_root))]


def readings(ep_dir: str) -> dict[tuple[int, float], list[list[tuple[str, str]]]]:
    case = find_case(os.path.basename(ep_dir).split(".")[0], ("long_horizon",))
    scene = build_scene(case)
    try:
        catalog = cell_catalog(scene.trays.values())
    finally:
        scene.close()
    out = {}
    perception = os.path.join(ep_dir, "perception")
    names = sorted(n for n in os.listdir(perception) if n.endswith(".png"))
    for min_pixels, hue_tol in GRID:
        reader = StubReader(min_pixels=min_pixels, hue_tol_deg=hue_tol)
        frames = []
        for name in names:
            stem = name[:-4]
            view = stem.rsplit("_", 1)[1]
            frame = SensorFrame(
                frame_id=stem, camera_id=view, camera=camera_for(view), modality="rgbd",
                image_ref=os.path.join(perception, name), image_sha256=_sha(os.path.join(perception, name)),
                depth_ref=os.path.join(perception, f"{stem}.depth.npy"),
                depth_sha256=_sha(os.path.join(perception, f"{stem}.depth.npy")))
            frames.append([(o.color, o.shape) for o in reader.read(frame, catalog=catalog).objects])
        out[(min_pixels, hue_tol)] = frames
    return out


def frame_index_by_round(ep_dir: str) -> dict[int, int]:
    """Which captured frame the round with index `n` was answered from.

    A round is answered from one observation, and the observations are a superset of the
    rounds (the loop observes after every skill as well as before every round), so the two are
    **not** interchangeable: indexing frames by round number would read an unrelated frame for
    most rounds and quietly produce a number about nothing. This is B1's alignment, spelled out.
    """
    events = []
    with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    ordinals = {}
    for index, e in enumerate(events):
        if e["type"] == "observation":
            ordinals[(e["payload"].get("observation") or {}).get("observation_ref")] = index
    out = {}
    for e in events:
        if e["type"] != "decision_context":
            continue
        ref = e["payload"].get("observation_ref")
        if ref in ordinals:
            out[int(e["payload"].get("round_index"))] = ordinals[ref]
    return out


def main() -> int:
    # the item-rounds B1 says are missing a colour, with the colour and shape they needed
    with open(os.path.join(REPO, "work", "v06", "b1_ceiling.json"), encoding="utf-8") as f:
        ceiling = json.load(f)
    needed = collections.defaultdict(list)
    for episode in ceiling["episodes"]:
        for row in episode["rows"]:
            needed[f"{episode['archive']}:{episode['episode_id']}"].append(
                (str(row["declared"].get("color")), str(row["declared"].get("shape")),
                 row["round"]))

    report = {"grid": [{"min_pixels": m, "hue_tol_deg": h} for m, h in GRID],
              "settings": {}, "needed_item_rounds": {k: len(v) for k, v in needed.items()}}
    for arc in ARCS:
        for ep_dir in _episodes(arc):
            ep = os.path.basename(ep_dir)
            key = f"{arc}:{ep}"
            if key not in needed:
                continue
            per_setting = readings(ep_dir)
            round_frame = frame_index_by_round(ep_dir)
            case_id = ep.split(".")[0]
            for setting, frames in per_setting.items():
                colour_ok = shape_ok = 0
                for colour, shape, round_index in needed[key]:
                    index = round_frame.get(int(round_index))
                    frame = frames[index] if index is not None and index < len(frames) else []
                    hits = [d for d in frame if d[0] == colour]
                    if hits:
                        colour_ok += 1
                        if any(d[1] == shape for d in hits):
                            shape_ok += 1
                bucket = report["settings"].setdefault(
                    f"min_pixels={setting[0]},hue_tol_deg={setting[1]}",
                    {"colour_seen": 0, "colour_and_shape_seen": 0, "episodes": {}})
                bucket["colour_seen"] += colour_ok
                bucket["colour_and_shape_seen"] += shape_ok
                bucket["episodes"][key] = {"colour_seen": colour_ok, "colour_and_shape_seen": shape_ok}

    total = sum(len(v) for v in needed.values())
    with open(os.path.join(REPO, "work", "v06", "b1_reader_scan.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"\nitem-rounds that missed their colour: {total}")
    for name, row in sorted(report["settings"].items()):
        print(f"  {name:<34} colour_seen={row['colour_seen']:<4} "
              f"colour_and_shape_seen={row['colour_and_shape_seen']}")
    print(os.path.join(REPO, "work", "v06", "b1_reader_scan.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())