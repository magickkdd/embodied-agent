"""RQ23's per-episode reading: does the v0.8 repair close the dead end, and where it does not.

RQ23 asks whether the held-orphan class disappears once the bookkeeping keeps an unbound row
pending and matches it by declared attributes. The new-blood batch's summary says **no** -- three
episodes still end `holding X but no pending goal names it` -- so this instrument reads each of them
the way RQ21 read the five historical ones, and adds the one question the fix's design turns on:

    the fallback matches the *declaration* against `world.entities[held].attributes`, so the
    question is what the snapshot says about the **held** body -- a body in the gripper is a body
    the frame may report (`seen:red`) while the world entry for the held object carries no
    attributable pair at all.

Each episode therefore reports: the round the object was picked, whether the pending row named it
by id then, whether it still does after the pick, what the reader reported for that colour/shape,
and what the snapshot's own faces (`visibility`, the perception block's hold flags) say about the
held body. A repair that does not cover this shape of drift is a finding, not a failed test.

Usage: PYTHONPATH=. <py>
"""
from __future__ import annotations

import ast
import json
import os
import sys

ROOT = "/home/czx/embodied-agent-batches/v08/newblood"
CELLS = ["c2_vlm", "c4_vlm", "c5_vlm"]
ORPHAN = "no pending goal names it"


def _run(cell: str) -> str:
    base = os.path.join(ROOT, cell)
    runs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d, "episodes"))]
    return os.path.join(base, runs[-1]) if runs else ""


def _events(ep_dir: str) -> list[dict]:
    return [json.loads(line) for line in open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8")
            if line.strip()]


def _declared(entity_id: str):
    text = str(entity_id or "").strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, dict) else None


def read_episode(cell: str, ep_dir: str) -> dict | None:
    events = _events(ep_dir)
    summary_path = os.path.join(ep_dir, "episode_summary.json")
    if not os.path.exists(summary_path):
        return None
    summary = json.load(open(summary_path, encoding="utf-8"))
    result = summary.get("result") or {}
    reason = str(result.get("termination_reason") or "")
    if ORPHAN not in reason:
        return None
    held = reason.split("holding ", 1)[1].split(" ")[0]

    rounds = [(e.get("payload") or {}).get("round_index") or i
              for i, e in enumerate(events) if e.get("type") == "decision_context"]
    contexts = [e.get("payload") or {} for e in events if e.get("type") == "decision_context"]
    picks = []
    for index, event in enumerate(events):
        if event.get("type") != "execution_feedback":
            continue
        fb = (event.get("payload") or {}).get("feedback") or {}
        if fb.get("skill") == "pick" and fb.get("entity_id") == held \
                and str(fb.get("status")) == "completed":
            picks.append((event.get("sequence"), index))
    # which decision_context the pick belonged to: the most recent one before the feedback
    pick_seq = picks[-1][0] if picks else None
    pick_context = None
    if pick_seq is not None:
        before = [e for e in events if e.get("sequence", 0) < pick_seq
                  and e.get("type") == "decision_context"]
        pick_context = (before[-1].get("payload") or {}) if before else None

    def names_id(payload) -> bool:
        return any(r.get("entity_id") == held for r in ((payload or {}).get("progress") or []))

    reader_for_held = None
    visibility = None
    for event in events:
        if event.get("type") != "perception":
            continue
        payload = event.get("payload") or {}
        visibility = payload.get("visibility")
        for det in payload.get("detections") or []:
            attrs = det.get("state_attributes") or {}
            if attrs.get("color") == held.split("_")[1]:
                reader_for_held = {"entity_id": det.get("entity_id"), "color": attrs.get("color"),
                                   "shape": attrs.get("shape"),
                                   "claimed_on_or_in": attrs.get("claimed_on_or_in")}
    last = contexts[-1] if contexts else {}
    unbound = [{"declared": _declared(r.get("entity_id")), "target_id": r.get("target_id")}
               for r in (last.get("progress") or []) if _declared(r.get("entity_id"))]
    return {"cell": cell, "episode_id": os.path.basename(ep_dir), "held": held,
            "rounds": len(contexts), "http_requests": result.get("http_requests"),
            "objects": f"{result.get('objects_completed')}/{result.get('objects_total')}",
            "pick_seq": pick_seq,
            "named_by_id_at_the_pick": names_id(pick_context),
            "named_by_id_at_the_end": names_id(last),
            "unbound_rows_at_the_end": unbound,
            "reader_reported_for_the_held_colour": reader_for_held,
            "last_visibility_block": json.dumps(visibility, ensure_ascii=False)[:200],
            "last_round": last.get("round_index")}


def main() -> int:
    episodes = []
    for cell in CELLS:
        run = _run(cell)
        if not run:
            continue
        for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
            reading = read_episode(cell, os.path.join(run, "episodes", ep))
            if reading:
                episodes.append(reading)
    out = {"criteria": "docs/continuous-decision-v0.8-phase-log.md P1 判据 + D2''''' 修复设计",
           "repair_scope_question": ("the fallback matches the declaration against the held body's "
                                     "snapshot attributes; this is what the snapshot says about a "
                                     "body that is in the gripper"),
           "episodes": episodes}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "r23_orphan_check.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for episode in episodes:
        print(f"=== {episode['cell']}/{episode['episode_id']}  held={episode['held']} "
              f"rounds={episode['rounds']} http={episode['http_requests']} "
              f"objects={episode['objects']}")
        print(f"    抓取轮按 id 指名={episode['named_by_id_at_the_pick']} "
              f"终态轮按 id 指名={episode['named_by_id_at_the_end']}")
        print(f"    终态未绑定行的声明: {episode['unbound_rows_at_the_end']}")
        print(f"    读侧给握持物颜色的读数: {episode['reader_reported_for_the_held_colour']}")
        print(f"    最后一帧的 visibility 块: {episode['last_visibility_block']}")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())