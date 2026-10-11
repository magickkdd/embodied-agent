"""v0.6 B1: how much of the intermittent detection loss a past-frame fusion window could win,
and what it would cost in mis-binding risk.

The criteria are in `docs/continuous-decision-v0.6-phase-log.md` ("P2 判据", B1-1..B1-4);
they are quoted where a judgement is made. The three that shape this file:

* **the window looks backwards only** (k = the k rounds before this one). An online fix can
  only remember what it has already seen; a reading that counted "the next frame would have
  seen it" would be a measurement of hindsight dressed as a design.
* **a rescue is not a success.** A rescue counts a round the window could have supplied a
  detection for; whether the binding then holds is reported separately, and the two can
  disagree (a colour seen in the window whose shape never matched is a rescue that binds
  nothing). The criteria call the first number a ceiling and forbid reporting a rate.
* **the mis-binding reading is a veto, not a footnote** (SPEC §9 risk 1): within the window,
  a colour claimed by more than one body is the case where "bind by last known" invents an
  identity, and frame ids are `seen:<colour>`, so cross-frame continuity has to come from
  attributes and geometry -- it is not there for free.

Inputs: the per-round detection series (vlm: the archived `perception` records; stub: the
deterministic replay in `stub_replay.py`) and the per-round binding rows from v0.5's
attribution instrument, aligned on the observation ordinal exactly as A1 aligned them.

Reads archives read-only; writes `work/v06/b1_ceiling.json`; spends nothing.

Usage:  PYTHONPATH=. <py> work/v06/b1_ceiling.py
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

import a1_attribute  # noqa: E402  (v0.5's instrument, imported not modified -- SPEC §14)

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
CHANNELS = ("stub", "vlm")
WINDOWS = (1, 2)


def _run(arc: str, channel: str) -> str:
    root = os.path.join(ARCS[arc], f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d, "episodes"))]
    assert len(runs) == 1, runs
    return os.path.join(root, runs[-1])


def _events(run_dir: str) -> list[dict]:
    with open(os.path.join(run_dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def observation_ordinals(events: list[dict]) -> dict[str, int]:
    out = {}
    for index, e in enumerate(events):
        if e["type"] == "observation":
            out[(e["payload"].get("observation") or {}).get("observation_ref")] = index
    return out


def detection_series(arc: str, channel: str, ep_dir: str, replay: dict) -> list[list[tuple[str, str]]]:
    """One entry per observation: the `(colour, shape)` detections that observation used."""
    if channel == "vlm":
        by_ref = {}
        for e in _events(ep_dir):
            if e["type"] != "perception":
                continue
            payload = e["payload"]
            ref = payload.get("observation_id") or payload.get("observation_ref")
            rows = []
            for det in payload.get("detections") or []:
                attrs = det.get("state_attributes") or {}
                eid = str(det.get("entity_id") or "")
                colour = str(attrs.get("color") or (eid.split(":", 1)[1] if eid.startswith("seen:") else ""))
                rows.append((colour, str(attrs.get("shape") or "")))
            by_ref[ref] = rows
        ordinals = observation_ordinals(_events(ep_dir))
        series = [None] * (len(ordinals) + 1)
        for ref, index in ordinals.items():
            if index < len(series):
                series[index] = by_ref.get(ref, [])
        return [s or [] for s in series]
    rows = (replay.get(f"{arc}:{os.path.basename(ep_dir)}") or {})
    return [[(o["color"], o["shape"]) for o in look["objects"]] for look in rows.get("looks", [])]


def analyse_episode(arc: str, channel: str, ep_dir: str, episode_id: str,
                    replay: dict, cell: dict) -> dict:
    """The B1 rows for one episode: which missing-colour rounds a past window could supply,
    and what binding risk that supply would carry."""
    series = detection_series(arc, channel, ep_dir, replay)
    ordinals = observation_ordinals(_events(ep_dir))
    # the attribution instrument's per-round rows carry the round index but not the ref, so the
    # pairing is by position: its rounds are the `decision_context` events in file order, which
    # is the same order A1 aligned on
    refs_by_round = [e["payload"].get("observation_ref") for e in _events(ep_dir)
                     if e["type"] == "decision_context"]
    rows = []
    for item in cell["items"]:
        colour = str(item["declared"].get("color") or "")
        shape = str(item["declared"].get("shape") or "")
        for position, r in enumerate(item["rounds"]):
            if r["mode"] != "frame_did_not_see_the_colour":
                continue
            ref = refs_by_round[position] if position < len(refs_by_round) else None
            index = ordinals.get(ref)
            if index is None:
                continue
            window_hits = {}
            for k in WINDOWS:
                past = series[max(0, index - k):index]
                hits = [d for frame in past for d in frame if d[0] == colour]
                shapes = sorted({d[1] for d in hits})
                window_hits[k] = {"frames_with_colour": sum(1 for frame in past
                                                           if any(d[0] == colour for d in frame)),
                                  "detections": hits, "shapes": shapes}
            # mis-binding risk: the window's colours that more than one body claims
            risky = {}
            for k in WINDOWS:
                counts = collections.Counter(
                    d for frame in series[max(0, index - k):index] for d in frame)
                risky[k] = sum(1 for det, n in counts.items() if n > 1)
            bound_nearby = [p["bound"] for p in item["rounds"]
                            if abs((p["round"] or 0) - (r["round"] or 0)) <= max(WINDOWS)]
            rows.append({
                "item": item["index"], "declared": item["declared"], "round": r["round"],
                "state_version": r["state_version"],
                "window": {k: window_hits[k] for k in WINDOWS},
                "ambiguous_detections_in_window": risky,
                "bound_in_neighbouring_rounds": sorted(bound_nearby),
                "shape_matches_declaration": {k: shape in window_hits[k]["shapes"]
                                              for k in WINDOWS},
            })
    return {"archive": arc, "channel": channel, "episode_id": episode_id,
            "case_id": cell["case_id"], "missing_item_rounds": len(rows), "rows": rows}


def main() -> int:
    replay = {}
    with open(os.path.join(REPO, "work", "v06", "stub_replay.json"), encoding="utf-8") as f:
        for episode in json.load(f)["episodes"]:
            replay[f"{episode['archive']}:{episode['episode_id']}"] = episode
    stub_replay = {ep["episode_id"]: ep for ep in replay.values() if ep["archive"] == "v04"}

    report = {"criteria": "docs/continuous-decision-v0.6-phase-log.md, P2 判据 B1",
              "windows": list(WINDOWS), "episodes": []}
    for arc in ARCS:
        for channel in CHANNELS:
            run = _run(arc, channel)
            for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
                ep_dir = os.path.join(run, "episodes", ep)
                if not os.path.exists(os.path.join(ep_dir, "episode_summary.json")):
                    # an episode that died before it could write a summary (E2''s 429 row)
                    # has no binding rows to ask about a fusion window
                    report["episodes"].append(
                        {"archive": arc, "channel": channel, "episode_id": ep,
                         "case_id": ep.split(".")[0], "missing_item_rounds": 0, "rows": [],
                         "skipped": "no episode_summary.json (died before a result)"})
                    continue
                # A1's instrument is asked for the same archive/channel; for the stub channel
                # of v05 its offline replay has to be the v0.6 one, so the rows it returns are
                # the ones the *current* code would derive from those frames.
                cell = a1_attribute.analyse(
                    channel, ep, ep_dir,
                    {**stub_replay} if channel == "stub" else {})
                report["episodes"].append(
                    analyse_episode(arc, channel, ep_dir, ep,
                                    {f"{arc}:{ep}": (replay.get(f"{arc}:{ep}") or {})}
                                    if channel == "stub" else {}, cell))

    # ---- the four readings
    total_missing = sum(e["missing_item_rounds"] for e in report["episodes"])
    by_cell = collections.Counter()
    gain = {k: collections.Counter() for k in WINDOWS}
    binding = {k: collections.Counter() for k in WINDOWS}
    risk = {k: collections.Counter() for k in WINDOWS}
    for e in report["episodes"]:
        key = (e["archive"], e["channel"], e["case_id"])
        by_cell[key] += e["missing_item_rounds"]
        for row in e["rows"]:
            for k in WINDOWS:
                w = row["window"][k]
                if w["detections"]:
                    gain[k][key] += 1
                    if row["shape_matches_declaration"][k]:
                        binding[k][key] += 1
                if row["ambiguous_detections_in_window"][k]:
                    risk[k][key] += 1
    report["readings"] = {
        "missing_item_rounds_total": total_missing,
        "by_cell": {"|".join(k): v for k, v in sorted(by_cell.items())},
        "rescued": {k: {"|".join(kk): v for kk, v in sorted(gain[k].items())} for k in WINDOWS},
        "rescued_with_matching_shape": {k: {"|".join(kk): v for kk, v in sorted(binding[k].items())}
                                         for k in WINDOWS},
        "ambiguous_detections_in_window": {k: {"|".join(kk): v for kk, v in sorted(risk[k].items())}
                                           for k in WINDOWS},
    }
    path = os.path.join(REPO, "work", "v06", "b1_ceiling.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"\nmissing-colour item-rounds across both archives: {total_missing}")
    for key, n in sorted(by_cell.items()):
        print(f"  {'|'.join(key):<52} missing={n:<4} "
              + "  ".join(f"k={k}: rescued={gain[k][key]} shape_ok={binding[k][key]} "
                          f"ambiguous={risk[k][key]}" for k in WINDOWS))
    rescued = "  ".join(f"k={k}: {sum(gain[k].values())}" for k in WINDOWS)
    shape_ok = "  ".join(f"k={k}: {sum(binding[k].values())}" for k in WINDOWS)
    ambiguous = "  ".join(f"k={k}: {sum(risk[k].values())}" for k in WINDOWS)
    print(f"\nrescue totals: {rescued}  of {total_missing}")
    print(f"shape-matching rescues: {shape_ok}")
    print(f"windows carrying an ambiguous (colour, shape) detection: {ambiguous}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())