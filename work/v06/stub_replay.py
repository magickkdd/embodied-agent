"""v0.6 B1 step 0: the stub channel's frame-side reading, for both archives.

A copy of v0.5's `work/v05/a1_stub_replay.py` (SPEC §14: v0.5's instruments are sealed;
v0.6 works from a copy and never writes back to the original) with two changes:

* it replays **both** camera archives the study reads (`v04/e2` and `v05/e2`) rather than
  v0.5's one, because #26's ceiling is a statement about how often the frame misses a colour
  and one batch's worth of misses is not a rate;
* it keeps the same join justification (one archived look per `observation` event, so the k-th
  look is the k-th observation) and the same refusal to write into an archive.

Deterministic, offline, zero requests. `StubReader` is a camera algorithm, the frames are on
disk with their own digests, and `SensorFrame` carries its own `CameraSpec` precisely so a run
directory can be re-read with nothing connected.

Usage:  PYTHONPATH=. <py> work/v06/stub_replay.py
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
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}


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
        run = _run(arc, "stub")
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