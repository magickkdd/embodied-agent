"""Why the held orphan still appears in three new-blood episodes, and what the stub cells'
zero-request "budget stops" actually hit.

Two questions the batch's summary answers only coarsely:

1. c2_vlm r0 and c5_vlm r0/r1 still end `holding X but no pending goal names it` **after** the
   v0.8 repair. The repair matches a pending row to the held object by the *declared attributes*,
   exactly; so the reading to check is whether the held body's own attributes differ from the
   declaration -- a shape the reader misread, with the colour right. If that is what happens, the
   fix's scope is colour-level drift and a shape-level drift still dead-ends, and that is a
   finding rather than a bug in the fix.
2. The stub cells report `BUDGET_EXHAUSTED` with **zero** HTTP requests. `BUDGET_EXHAUSTED` is one
   FailureCode for every budget, so which budget ran out has to be read off the episode rather
   than guessed from the code.

Usage: PYTHONPATH=. <py>
"""
from __future__ import annotations

import ast
import json
import os
import sys

ROOT = "/home/czx/embodied-agent-batches/v08/newblood"
ORPHAN_CELLS = ["c2_vlm", "c5_vlm"]
BUDGET_CELLS = ["c2_stub", "c5_stub"]


def _run(cell: str) -> str:
    base = os.path.join(ROOT, cell)
    runs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d, "episodes"))]
    return os.path.join(base, runs[-1]) if runs else ""


def _events(ep_dir: str) -> list[dict]:
    out = []
    for line in open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8"):
        if line.strip():
            out.append(json.loads(line))
    return out


def _declared(entity_id: str):
    text = str(entity_id or "").strip()
    if not text.startswith("{"):
        return None
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def orphan_detail(ep_dir: str) -> dict:
    events = _events(ep_dir)
    entities = {}
    for event in events:
        if event.get("type") == "perception":
            for det in ((event.get("payload") or {}).get("detections") or []):
                attrs = det.get("state_attributes") or {}
                entities[attrs.get("color")] = attrs.get("shape")
    last = None
    for event in events:
        if event.get("type") == "decision_context":
            last = event.get("payload") or {}
    rows = last.get("progress") or []
    held = None
    reason = ""
    sp = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(sp):
        result = (json.load(open(sp, encoding="utf-8")).get("result") or {})
        reason = str(result.get("termination_reason") or "")
        if "holding " in reason:
            held = reason.split("holding ", 1)[1].split(" ")[0]
    colour = held.split("_")[1] if held else ""
    declared_pairs = []
    for row in rows:
        declared = _declared(row.get("entity_id"))
        if declared:
            declared_pairs.append(declared)
    return {"held": held, "last_round": last.get("round_index"),
            "attribute_rows": declared_pairs,
            "reader_shape_for_held_colour": entities.get(colour),
            "declared_colour_for_held": colour}


print("=== 1. 修复后仍出现握持孤儿的三个集：漂移是颜色层还是形状层")
for cell in ORPHAN_CELLS:
    run = _run(cell)
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        ep_dir = os.path.join(run, "episodes", ep)
        sp = os.path.join(ep_dir, "episode_summary.json")
        if not os.path.exists(sp):
            continue
        result = (json.load(open(sp, encoding="utf-8")).get("result") or {})
        if "no pending goal names it" not in str(result.get("termination_reason") or ""):
            continue
        detail = orphan_detail(ep_dir)
        print(f"  {cell:<8}{ep:<34}held={detail['held']} last_round={detail['last_round']}")
        print(f"      未绑定行声明的属性对: {detail['attribute_rows']}")
        print(f"      读侧给该握持物颜色的形状: {detail['reader_shape_for_held_colour']} "
              f"(声明颜色 {detail['declared_colour_for_held']})")

print("\n=== 2. stub 格零请求的 BUDGET_EXHAUSTED：哪一种预算")
for cell in BUDGET_CELLS:
    run = _run(cell)
    for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
        sp = os.path.join(run, "episodes", ep, "episode_summary.json")
        if not os.path.exists(sp):
            continue
        result = (json.load(open(sp, encoding="utf-8")).get("result") or {})
        if result.get("failure_type") != "BUDGET_EXHAUSTED":
            continue
        budgets = {}
        bs = os.path.join(run, "episodes", ep, "budget.json")
        if os.path.exists(bs):
            budgets = json.load(open(bs, encoding="utf-8"))
        print(f"  {cell:<8}{ep:<34}"
              f"rounds={result.get('decision_rounds')} skills={result.get('skill_calls')} "
              f"http={result.get('http_requests')} obj={result.get('objects_completed')}/"
              f"{result.get('objects_total')} note={str((result.get('artifacts') or {}).get('note'))[:90]}")
        if budgets:
            print(f"      budget.json: {json.dumps(budgets, ensure_ascii=False)[:300]}")