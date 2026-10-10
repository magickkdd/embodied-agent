"""v0.5 A1, the stub channel's frame-side reading: `StubReader` replayed offline.

Why this exists. The `stub` cell wrote **no** `perception` events (`perception_events: 0`
in every episode summary), so the archive of that channel contains the loop's view of the
world but not the frame-side answer that produced it. Ring (a) of RQ11 -- "did the frame see
the body at all" -- is therefore unanswerable from the stub events alone, and answering it
from the loop's view would assume the very thing under test (a bound entity implies a seen
body; an unbound one might be unseen *or* unbound).

So the frame is replayed. `StubReader` is deterministic and offline by construction ("it
cannot name a shape without measuring the surface under it"), the frames are on disk with
their own digests, and `SensorFrame` carries its own `CameraSpec` precisely so a run
directory can be re-read with nothing connected. The replay therefore re-derives what that
channel saw, byte for byte, at zero request cost -- and writes nothing into the archive
(SPEC §14: instruments do not write to archives).

The per-round join: one archived look per `observation` event in both stub cells (26/26 and
15/15, `summary.perception.looks` against the event count), both sequences are append-only
and written by the same loop iteration, so the k-th look is the k-th observation. The join
is ordinal and this is the reason; it is not a guess about content.

Usage:  PYTHONPATH=. <py> work/v05/a1_stub_replay.py [out.json]
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

E2 = "/home/czx/embodied-agent-batches/v04/e2"


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _run(channel: str) -> str:
    root = os.path.join(E2, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    assert len(runs) == 1, runs
    return os.path.join(root, runs[0])


def _frames(perception_dir: str) -> list[tuple[str, str]]:
    """`(frame_id, view)` for every archived look, in capture order."""
    names = sorted(n for n in os.listdir(perception_dir) if n.endswith(".png"))
    out = []
    for name in names:
        stem = name[:-4]
        view = stem.rsplit("_", 1)[1]
        out.append((stem, view))
    return out


def replay_episode(ep_dir: str, case_id: str) -> dict:
    case = find_case(case_id, ("long_horizon",))
    scene = build_scene(case)
    try:
        catalog = cell_catalog(scene.trays.values())
    finally:
        scene.close()
    reader = StubReader()
    perception_dir = os.path.join(ep_dir, "perception")
    rows = []
    for index, (frame_id, view) in enumerate(_frames(perception_dir)):
        image = os.path.join(perception_dir, f"{frame_id}.png")
        depth = os.path.join(perception_dir, f"{frame_id}.depth.npy")
        frame = SensorFrame(
            frame_id=frame_id, camera_id=view, camera=camera_for(view), modality="rgbd",
            image_ref=image, image_sha256=_sha(image), image_bytes=os.path.getsize(image),
            depth_ref=depth, depth_sha256=_sha(depth))
        reading = reader.read(frame, catalog=catalog)
        rows.append({
            "observation_index": index,
            "frame_id": frame_id,
            "view": view,
            "objects": [{"color": o.color, "shape": o.shape,
                         "confidence": o.confidence, "ref": o.ref,
                         "how_identified": "segmented"}
                        for o in reading.objects],
        })
    return {"case_id": case_id, "episode_id": os.path.basename(ep_dir), "looks": rows}


def main() -> int:
    run = _run("stub")
    out = {"channel": "stub", "reader": "StubReader (deterministic, offline replay)",
           "episodes": []}
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        ep_dir = os.path.join(run, "episodes", ep)
        case_id = ep.split(".")[0]
        out["episodes"].append(replay_episode(ep_dir, case_id))
        print(f"replayed {ep}: {len(out['episodes'][-1]['looks'])} looks", file=sys.stderr)
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "a1_stub_replay.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())