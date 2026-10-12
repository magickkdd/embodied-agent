"""v0.7 M1: which of v1's 30 declarations asks the sensor for something it has never shown.

The criteria are written down **before** this runs, in `docs/continuous-decision-v0.7-phase-log.md`
("P1 判据", M1-1..M1-4), and they are the whole of the judgement: this file measures and applies
them, and it does not propose a re-adjudication (that is D4'''', the user's call).

What it reads, all of it zero-cost and read-only:

* three generations of camera archives (`v04/e2`, `v05/e2`, `v06/e2`) -- the `vlm` channel's
  archived `perception` records, and the `stub` channel's archived frames replayed through
  `stub_replay_base.py` (a copy of v0.6's base, extended to v06);
* the v1 task table (`configs/experiment/frozen_long_horizon_v1.json`) for the declaration side.

Three readings come out, and they are deliberately kept apart:

1. **per declaration x per attribute**, the three-way verdict (groundable / beyond-grain /
   conditionally groundable), with the evidence chain the criteria demand: which generation,
   how many frames, what the reader reported;
2. **per case**, the "已证实判别力" profile -- the colours, the shape vocabulary, the objects seen
   per frame, same-name co-occurrence (v0.6's B2 zero, promoted to a profile field rather than a
   conclusion), and the looks per episode that P3's demand profile is built from;
3. **M1-4**, the degeneracy warning: for every beyond-grain attribute, what would be left to
   tell the case's targets apart if P-A dropped it. That is a warning input for 原则 21's gate
   (c), not a re-adjudication.

The wording discipline (M1-3) is enforced in the output's own keys: everything here is named
`confirmed_*`, because finite frames give a lower bound and v2 may only declare inside it.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"),
        "v05": os.path.join(BATCHES, "v05", "e2"),
        "v06": os.path.join(BATCHES, "v06", "e2")}
V1 = os.path.join(REPO, "configs", "experiment", "frozen_long_horizon_v1.json")


# ----------------------------------------------------------------- readers ----


def _run(arc: str, channel: str) -> str:
    root = os.path.join(ARCS[arc], f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
    return os.path.join(root, runs[-1])


def _vlm_series(arc: str, channel: str) -> list[dict]:
    """One entry per episode: the `(colour, shape)` pairs each archived look reported.

    Read from the `perception` records, which carry `state_attributes` per detection. Frames
    that a run did not archive (`--no-frames`) contribute no detections and are counted as such
    rather than as empty frames -- an absent frame is not a frame that saw nothing.
    """
    run = _run(arc, channel)
    episodes = []
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        looks = []
        path = os.path.join(run, "episodes", ep, "events.jsonl")
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "perception":
                continue
            payload = event.get("payload") or {}
            detections = []
            for det in (payload.get("detections") or []):
                attrs = det.get("state_attributes") or {}
                detections.append({"color": attrs.get("color"), "shape": attrs.get("shape"),
                                   "claimed_on_or_in": attrs.get("claimed_on_or_in")})
            if detections:
                looks.append({"observation_index": len(looks), "detections": detections})
        episodes.append({"archive": arc, "channel": channel,
                         "episode_id": ep, "case_id": ep.split(".")[0], "looks": looks})
    return episodes


def _stub_series() -> list[dict]:
    with open(os.path.join(HERE, "stub_replay.json"), encoding="utf-8") as f:
        replay = json.load(f)
    episodes = []
    for row in replay["episodes"]:
        episodes.append({
            "archive": row["archive"], "channel": "stub",
            "episode_id": row["episode_id"], "case_id": row["case_id"],
            "looks": [{"observation_index": look["observation_index"],
                       "detections": [{"color": o["color"], "shape": o["shape"],
                                       "claimed_on_or_in": None} for o in look["objects"]]}
                      for look in row["looks"]]})
    return episodes


# ------------------------------------------------------------- the criteria ----


def _verdict_for_value(frames: list[dict], pick) -> dict:
    """The M1-1 three-way verdict for one attribute value, with its evidence chain.

    `frames` is the whole corpus for one channel, each entry `{ordinal, detections, first_look}`.
    The first branch is the amendment logged in the phase log ("判据修正 1"): **no frames at
    all is `no_confirmed_evidence`, not `beyond_grain`**. Absence of evidence is not evidence of
    absence, and a verdict that said otherwise would let v2 delete declarations the sensor was
    never asked about.
    """
    if not frames:
        return {"verdict": "no_confirmed_evidence", "frames_seen": 0, "generations": [],
                "evidence": "this case has no archived camera frame on this channel at all"}
    hits = [f for f in frames if any(pick(d) for d in f["detections"])]
    if not hits:
        return {"verdict": "beyond_grain", "frames_seen": 0, "generations": [],
                "evidence": "no frame in the confirmed corpus reported this value"}
    lone = [f for f in hits
            if sum(1 for d in f["detections"] if pick(d)) == 1]
    generations = sorted({f["archive"] for f in hits})
    first_look_hits = sum(1 for f in hits if f["first_look"])
    evidence = (f"reported in {len(hits)} frames across generations {generations}; "
                f"earliest ordinal {min(f['ordinal'] for f in hits)}; "
                f"{len(lone)} of those frames carried no namesake; "
                f"first-look hits {first_look_hits} of "
                f"{sum(1 for f in frames if f['first_look'])} episodes")
    if lone:
        # M1-1 as written: reported in at least one frame with no same-named object beside it.
        # First-look coverage is reported in `first_look_hits` but is **not** part of the
        # verdict -- it is the #26 signature and it belongs to the profile, not to the verdict.
        return {"verdict": "groundable", "frames_seen": len(hits), "generations": generations,
                "evidence": evidence, "first_look_hits": first_look_hits}
    # The only way to reach here is a value that was reported but never separable -- i.e. it
    # always came beside a namesake. That is a stateable condition, so it is conditional
    # groundability rather than a beyond-grain verdict.
    return {"verdict": "conditionally_groundable", "frames_seen": len(hits),
            "generations": generations, "evidence": evidence, "first_look_hits": first_look_hits,
            "condition": "every frame that reported it also reported at least one namesake "
                         "with the same value, so the sensor never separated it"}


def _pair_verdict(frames: list[dict], colour: str, shape: str) -> dict:
    """The pair-level reading, which is what a declaration actually binds by.

    A declaration says "the yellow cube", so what matters is whether the sensor can produce the
    pair **and** whether the pair is unique in the frame. A colour that is separable while the
    pair never appears is a declaration that binds by a thing the sensor never showed together.
    """
    hits = [f for f in frames
            if any(d["color"] == colour and d["shape"] == shape for d in f["detections"])]
    lone = [f for f in hits
            if sum(1 for d in f["detections"]
                   if d["color"] == colour and d["shape"] == shape) == 1]
    if not frames:
        return {"pair_frames": 0, "pair_frames_without_namesake": 0,
                "verdict": "no_confirmed_evidence",
                "evidence": "this case has no archived camera frame on this channel at all"}
    return {"pair_frames": len(hits), "pair_frames_without_namesake": len(lone),
            "verdict": ("groundable" if lone else
                        "conditionally_groundable" if hits else "beyond_grain"),
            "evidence": (f"the pair ({colour}, {shape}) appeared in {len(hits)} frames, "
                         f"{len(lone)} of them without a namesake")}


def main() -> int:  # noqa: C901 - one function, in the order of the criteria
    with open(V1, encoding="utf-8") as f:
        table = json.load(f)

    corpus = _stub_series() + [ep for arc in ARCS for ch in ("vlm",)
                               for ep in _vlm_series(arc, ch)]
    # flatten every look of every episode, keeping which look of its episode it is
    frames = collections.defaultdict(list)
    for episode in corpus:
        for look in episode["looks"]:
            frames[(episode["channel"], episode["case_id"])].append({
                "archive": episode["archive"], "ordinal": look["observation_index"],
                "detections": look["detections"],
                "first_look": look["observation_index"] == 0})
    channels = sorted({ep["channel"] for ep in corpus})

    out = {"criteria": "docs/continuous-decision-v0.7-phase-log.md P1 判据 M1-1..M1-4",
           "wording": "已证实 (confirmed): finite frames give a lower bound; v2 may only declare "
                      "inside it, and no reading here may say the sensor 其实能 anything",
           "corpus": {"archives": sorted(ARCS), "channels": channels,
                      "episodes": collections.Counter((ep["channel"], ep["archive"])
                                                      for ep in corpus).most_common(),
                      "frames": collections.Counter(
                          (ep["channel"], ep["archive"]) for ep in corpus).most_common()},
           "cases": {}, "declarations": []}

    # ---- M1-2: the per-case confirmed discrimination profile
    for case in table["cases"]:
        case_id = case["task_id"]
        per_channel = {}
        for channel in channels:
            looks = frames.get((channel, case_id), [])
            colours = collections.Counter()
            shapes = collections.Counter()
            counts = []
            cooccurrence = 0
            for look in looks:
                counts.append(len(look["detections"]))
                seen = collections.Counter((d["color"], d["shape"]) for d in look["detections"])
                cooccurrence += sum(1 for n in seen.values() if n > 1)
                for d in look["detections"]:
                    colours[d["color"]] += 1
                    shapes[d["shape"]] += 1
            by_archive = collections.Counter(look["archive"] for look in looks)
            first_looks = [look for look in looks if look["first_look"]]
            first_look_objects = [len(look["detections"]) for look in first_looks]
            per_channel[channel] = {
                "looks": len(looks),
                "looks_by_archive": dict(by_archive),
                "confirmed_colours": sorted(c for c in colours if c),
                "confirmed_shapes": sorted(s for s in shapes if s),
                "colour_frames": dict(colours),
                "shape_frames": dict(shapes),
                "objects_per_frame": {"min": min(counts) if counts else None,
                                      "median": sorted(counts)[len(counts) // 2] if counts else None,
                                      "max": max(counts) if counts else None},
                "same_name_cooccurrence_frames": cooccurrence,
                # the #26 signature as a *profile* number: how many objects the very first look
                # of each episode carried. A first look that sees nothing is the intermittency
                # v0.6 measured, and it belongs here rather than in a verdict.
                "first_look_objects": {
                    "looks": len(first_looks),
                    "min": min(first_look_objects) if first_look_objects else None,
                    "median": sorted(first_look_objects)[len(first_look_objects) // 2]
                              if first_look_objects else None,
                    "max": max(first_look_objects) if first_look_objects else None,
                },
            }
        out["cases"][case_id] = {
            "targets": case["targets"],
            "confirmed_discrimination": per_channel,
            "utterance": case["utterance"],
        }

    # ---- M1-1 + M1-4: per declaration x per attribute, plus the pair and the warning
    for case in table["cases"]:
        case_id = case["task_id"]
        by_id = {o["entity_id"]: o for o in case["objects"]}
        for target_id in case["targets"]:
            attributes = (by_id.get(target_id) or {}).get("attributes") or {}
            colour, shape = attributes.get("color"), attributes.get("shape")
            row = {"case_id": case_id, "target_id": target_id,
                   "declared": {"color": colour, "shape": shape},
                   "per_channel": {}, "beyond_grain_attributes": [], "warning": None}
            for channel in channels:
                case_frames = frames.get((channel, case_id), [])
                row["per_channel"][channel] = {
                    "color": _verdict_for_value(case_frames, lambda d, c=colour: d["color"] == c),
                    "shape": _verdict_for_value(case_frames, lambda d, s=shape: d["shape"] == s),
                    "pair": _pair_verdict(case_frames, colour, shape),
                }
            beyond = sorted({name for channel in channels
                             for name, key in (("color", "color"), ("shape", "shape"))
                             if row["per_channel"][channel][key]["verdict"] == "beyond_grain"})
            row["beyond_grain_attributes"] = beyond
            # M1-4: if P-A dropped the beyond-grain attributes, what would still tell this case's
            # targets apart? Counted on the case's declared attributes, not on sensor readings.
            survivors = []
            for other in case["targets"]:
                other_attributes = (by_id.get(other) or {}).get("attributes") or {}
                keep = tuple(f"{k}={v}" for k, v in sorted(other_attributes.items())
                          if k not in beyond)
                survivors.append(keep)
            distinct = len(set(survivors))
            row["warning"] = {
                "beyond_grain_attributes": beyond,
                "targets_after_dropping_them": len(survivors),
                "distinct_signatures_left": distinct,
                "degenerate": distinct < len(survivors),
                "note": ("if P-A drops these attributes the targets of this case stop being "
                         "distinguishable from the declaration alone -- 原则 21(c) gate input"
                         if distinct < len(survivors) else None),
            }
            out["declarations"].append(row)

    path = os.path.join(HERE, "m1_mismatch.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------------ print
    tally = collections.Counter()
    for row in out["declarations"]:
        for channel in channels:
            for key in ("color", "shape", "pair"):
                tally[f"{key}:{row['per_channel'][channel][key]['verdict']}"] += 1
    print("M1 三分判定（30 条声明 × 2 通道 × 颜色/形状/属性对）")
    for key in sorted(tally):
        print(f"  {key:<46}{tally[key]}")
    print("\n逐 case 的已证实判别力（每帧物体数 / 同名共现帧 / 形状词表）")
    for case_id, reading in out["cases"].items():
        for channel in channels:
            c = reading["confirmed_discrimination"][channel]
            print(f"  {case_id:<30}{channel:<6}looks={c['looks']:<5}"
                  f"objs/frame={c['objects_per_frame']['min']}/"
                  f"{c['objects_per_frame']['median']}/{c['objects_per_frame']['max']}  "
                  f"cooccur={c['same_name_cooccurrence_frames']:<3} "
                  f"shapes={','.join(c['confirmed_shapes'])}")
    print("\n超粒度属性清单（M1-1 的证据链在 JSON 里）")
    for row in out["declarations"]:
        if row["beyond_grain_attributes"]:
            chains = []
            for channel in channels:
                for name in row["beyond_grain_attributes"]:
                    chains.append(f"{channel}/{name}: "
                                  f"{row['per_channel'][channel][name]['verdict']} "
                                  f"({row['per_channel'][channel][name]['evidence']})")
            print(f"  {row['case_id']:<30}{row['target_id']:<12}"
                  f"{row['declared']['color']}/{row['declared']['shape']}  "
                  f"beyond={row['beyond_grain_attributes']}")
            for chain in chains:
                print(f"      {chain}")
    print("\n原则 21(c) 预警（删掉超粒度属性后签名不再互异）")
    for case_id, reading in out["cases"].items():
        rows = [r for r in out["declarations"] if r["case_id"] == case_id]
        degenerate = any(r["warning"]["degenerate"] for r in rows)
        print(f"  {case_id:<30}{'DEGENERATE' if degenerate else 'ok'}  "
              f"targets={len(rows)}  "
              f"distinct_left={min(r['warning']['distinct_signatures_left'] for r in rows)}/"
              f"{len(rows)}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())