"""Name the stub cell's unbound rows by replaying the archived frames, at zero cost.

The pre-registration's acceptance item -- every failed episode names its cause as #25 / #26 /
#27 -- fails on the stub cell for two reasons (`work/v06/e2_stub_names.py` states both):

* stub c1 dies of `REPEATED_INVALID`, a cause outside the three residuals, with zero unbound rows
  -- nothing to name, and the same reading E2'' already had;
* stub c3 has eight unbound rows, and **neither** archive holds a `perception` event for the stub
  channel: the offline stub path writes the raw `perception/*.png` + `.depth.npy` pair and the
  reader's own answers live only in the run's live objects.

So the frames are there and the reader is deterministic: replaying E2'' stub c3's archived PNGs
through `StubReader` reproduces exactly what that episode saw, with no request and no re-run. The
equivalence E2''' stub == E2'' stub is checked first (trajectory fields plus the full sequence of
unbound rows), because borrowing the older frames is only legitimate if the trajectory did not
move.

Usage:  PYTHONPATH=. <py>
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import stub_replay_base as stub_replay  # noqa: E402  (v0.7's copy of v0.6's replay base,
# extended to the v06 archive; the v0.6 original stays sealed)
from e2_readings import _declared_colours, _declared_of, _episode  # noqa: E402

NEW = "/home/czx/embodied-agent-batches/v07/e2"
OLD = "/home/czx/embodied-agent-batches/v06/e2"
CHANNEL = "long_horizon_stub"
TRAJECTORY = ("terminal_status", "failure_type", "decision_rounds", "skill_calls",
              "http_requests", "identical_invalid_attempts", "objects_completed", "objects_total")


def _run_dir(root: str) -> str:
    for path in sorted(os.listdir(os.path.join(root, CHANNEL))):
        if os.path.isdir(os.path.join(root, CHANNEL, path, "episodes")):
            return os.path.join(root, CHANNEL, path)
    raise SystemExit(f"no run directory under {os.path.join(root, CHANNEL)}")


def _ordinals(ep_dir: str) -> dict[str, int]:
    """observation_ref -> observation ordinal, which is what a replayed look list is indexed by."""
    out, index = {}, 0
    for line in open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8"):
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "observation":
            out[(event.get("payload") or {}).get("observation") and
                ((event["payload"].get("observation") or {}).get("observation_ref"))] = index
            index += 1
    return out


def main() -> int:
    new_run, old_run = _run_dir(NEW), _run_dir(OLD)
    episodes = []
    for ep_dir in sorted(os.listdir(os.path.join(new_run, "episodes"))):
        new_ep_dir = os.path.join(new_run, "episodes", ep_dir)
        old_ep_dir = os.path.join(old_run, "episodes", ep_dir)
        new_ep, old_ep = _episode(new_ep_dir), _episode(old_ep_dir)
        case_id = ep_dir.split(".")[0]
        mismatched = [k for k in TRAJECTORY
                      if new_ep["result"].get(k) != old_ep["result"].get(k)]
        rows_same = ([(r["round"], r["entity_id"], r["target_id"]) for r in new_ep["unbound"]]
                     == [(r["round"], r["entity_id"], r["target_id"]) for r in old_ep["unbound"]])
        # v0.6's method correction, applied here: the stub channel **does** archive its frames
        # (v0.6 concluded it did not, because the channel writes no `perception` events -- only
        # pixels). So this batch's own frames are the first choice and the older archive is a
        # fallback, used only when the batch archived none and only after the trajectory
        # equivalence has been checked episode by episode.
        own_frames = os.path.isdir(os.path.join(new_ep_dir, "perception"))
        reading = {"episode_id": ep_dir, "case_id": case_id,
                   "frames_from": new_ep_dir if own_frames else old_ep_dir,
                   "frames_source": "this batch" if own_frames else "borrowed (equivalence checked)",
                   "trajectory_fields_mismatched": mismatched,
                   "unbound_rows_identical": rows_same,
                   "terminal_status": new_ep["result"].get("terminal_status"),
                   "failure_type": new_ep["result"].get("failure_type"),
                   "unbound_rows": new_ep["unbound_rows"]}
        equivalent = not mismatched and rows_same
        if not new_ep["unbound_rows"]:
            reading["cause"] = (f"{reading['failure_type']} (outside #25/#26/#27)"
                                if reading["failure_type"] else "no unbound rows to name")
            episodes.append(reading)
            continue
        if not own_frames and not equivalent:
            reading["cause"] = "unattributed"
            reading["why"] = ("this batch archived no frames and the older archive's trajectory "
                              "disagrees, so no frames may stand in for it")
            episodes.append(reading)
            continue

        replay = stub_replay.replay_episode(reading["frames_from"], case_id)
        looks = [[(o["color"], o["shape"]) for o in look["objects"]] for look in replay["looks"]]
        ordinals = _ordinals(new_ep_dir)
        multiplicity = _declared_colours(case_id)
        named, tally = [], collections.Counter()
        for row in new_ep["unbound"]:
            declared = _declared_of(row.get("entity_id") or "")
            index = ordinals.get(row.get("observation_ref"))
            seen = looks[index] if index is not None and index < len(looks) else []
            if declared is None or index is None:
                cause, why = "unattributed", "the row names no declared pair, or its frame is missing"
            else:
                colour = declared.get("color") or declared.get("colour")
                shape = declared.get("shape")
                colours = [c for c, _ in seen]
                shapes = [s for c, s in seen if c == colour]
                if colour not in colours:
                    cause, why = "#26", f"frame {index} carried {sorted(set(colours))}"
                elif shape not in shapes:
                    n = multiplicity.get(colour, 1)
                    cause = "#25" if n > 1 else "regression_of_v05"
                    why = (f"colour {colour} seen as {shapes}, declared {shape}, "
                           f"declared multiplicity {n}")
                else:
                    cause, why = "unattributed", "the declared pair was in the frame and the row failed"
            tally[cause] += 1
            named.append({**row, "frame_ordinal": index, "cause": cause, "why": why})
        reading.update({"declared_multiplicity": multiplicity, "cause_tally": dict(tally),
                        "rows": named,
                        "cause": "/".join(sorted(tally)) if tally else "unattributed"})
        episodes.append(reading)

    out = {"new_archive": new_run, "frames_replayed_from": old_run,
           "argument": ("the stub reader is deterministic and offline, the stub cell spends zero "
                        "requests, and its ceiling never bound, so E2''' stub ran E2''s "
                        "trajectory -- checked per episode on the trajectory fields and the whole "
                        "unbound-row sequence before the older frames are used"),
           "episodes": episodes}
    with open(os.path.join(NEW, "e2_stub_names_v2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for r in episodes:
        print(f"{r['episode_id']:<36}{str(r['terminal_status']):<8}"
              f"{str(r['failure_type'] or '-'):<20}unbound={r['unbound_rows']:<3}"
              f"equiv={not r['trajectory_fields_mismatched'] and r['unbound_rows_identical']}  "
              f"cause={r['cause']}")
        if r.get("cause_tally"):
            print(f"    multiplicity={r['declared_multiplicity']} tally={r['cause_tally']}")
            for row in (r.get("rows") or [])[:4]:
                print(f"      r{row.get('round')} f{row.get('frame_ordinal')} "
                      f"{row.get('cause'):<18} {row.get('why')}")
    print(os.path.join(NEW, "e2_stub_names_v2.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())