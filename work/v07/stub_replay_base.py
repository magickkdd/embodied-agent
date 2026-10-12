"""v0.7 M1's stub-channel frame base: a copy, extended to the third camera archive.

Copied from `work/v06/stub_replay.py` (SPEC-v0.7 §14: v0.6's instruments are sealed and v0.7
works from copies, never writing back). One change, because M1 asks about **three** generations
rather than two:

* `ARCS` gains `v06`, so the discrimination profile rests on E2' / E2'' / E2''' frames rather
  than on the first two. v0.6's stub cell turns out to have archived its frames after all (the
  channel writes no `perception` *events*, but the PNG/depth pairs are on disk) — which is why
  the join below reads pixels, not records.

Deterministic, offline, zero requests: `StubReader` is a camera algorithm, the frames are on disk
with their own digests, and `SensorFrame` carries its own `CameraSpec` precisely so a run
directory can be re-read with nothing connected.

Usage:  PYTHONPATH=. <py>            (imported by `m1_mismatch.py`; `main()` writes the base run)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from embodied_agent.evaluation.calibration import cell_catalog
from embodied_agent.evaluation.run import build_scene
from embodied_agent.evaluation.tasks import find_case
from embodied_agent.perception.frames import SensorFrame, camera_for
from embodied_agent.perception.observe import StubReader

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"),
        "v05": os.path.join(BATCHES, "v05", "e2"),
        "v06": os.path.join(BATCHES, "v06", "e2")}


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _run(arc: str, channel: str) -> str:
    root = os.path.join(ARCS[arc], f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
    assert len(runs) == 1, runs
    return os.path.join(root, runs[0])


def _frames(perception_dir: str) -> list[tuple[str, str]]:
    names = sorted(n for n in os.listdir(perception_dir) if n.endswith(".png"))
    return [(n[:-4], n[:-4].rsplit("_", 1)[1]) for n in names]


def replay_episode(ep_dir: str, case_id: str) -> dict:
    case = find_case(case_id, ("long_horizon",))
    scene = build_scene(case)
    try:
        catalog = cell_catalog(scene.trays.values())
    finally:
        scene.close()
    reader = StubReader()
    rows = []
    for index, (frame_id, view) in enumerate(_frames(os.path.join(ep_dir, "perception"))):
        image = os.path.join(ep_dir, "perception", f"{frame_id}.png")
        depth = os.path.join(ep_dir, "perception", f"{frame_id}.depth.npy")
        frame = SensorFrame(
            frame_id=frame_id, camera_id=view, camera=camera_for(view), modality="rgbd",
            image_ref=image, image_sha256=_sha(image), image_bytes=os.path.getsize(image),
            depth_ref=depth, depth_sha256=_sha(depth))
        reading = reader.read(frame, catalog=catalog)
        rows.append({"observation_index": index, "frame_id": frame_id, "view": view,
                     "objects": [{"color": o.color, "shape": o.shape,
                                  "confidence": o.confidence, "how_identified": "segmented"}
                                 for o in reading.objects]})
    return {"case_id": case_id, "episode_id": os.path.basename(ep_dir), "looks": rows}


def main() -> int:
    out = {"reader": "StubReader (deterministic, offline replay)",
           "arcs": ARCS, "episodes": []}
    for arc in ARCS:
        root = os.path.join(ARCS[arc], "long_horizon_stub")
        runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
        # a run directory with no `perception/` frames cannot be replayed, and saying so is
        # better than counting an absent episode as one with zero looks
        run = os.path.join(root, runs[-1])
        if not os.listdir(os.path.join(run, "episodes")) or not os.path.isdir(
                os.path.join(run, "episodes",
                             sorted(os.listdir(os.path.join(run, "episodes")))[0], "perception")):
            print(f"{arc}: no archived frames under {run}; skipped", file=sys.stderr)
            continue
        for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
            row = replay_episode(os.path.join(run, "episodes", ep), ep.split(".")[0])
            row["archive"] = arc
            out["episodes"].append(row)
            print(f"replayed {arc}/{ep}: {len(row['looks'])} looks", file=sys.stderr)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stub_replay.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())