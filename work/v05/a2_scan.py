"""v0.5 A2: every model-seat episode of the merged corpus, with its ten covariates.

The criteria this implements are in `docs/continuous-decision-v0.5-phase-log.md`
("P2 A2 判据"); they are quoted where a judgement is made. Three of them shape the file:

* one table for triggers and non-triggers alike, because a covariate read off the three
  triggering episodes alone is a story, not a co-variation (criterion 2);
* "trigger" means what the shipped scorer means by it -- an episode in which at least one
  dependency edge was authored -- so the denominator cannot drift from
  `evaluation/long_horizon.py`'s L2 (criterion: the two must agree edge for edge, which
  `a2_check_scorer.py` checks);
* the ten covariates were fixed before this file was run, so none of them is a covariate
  discovered by looking at what the three triggering episodes happened to contain.

Reads both archives read-only; writes `work/v05/a2_scan.json` plus a printed table.
Costs nothing.

Usage:  PYTHONPATH=. <py> work/v05/a2_scan.py [v04|v03]
"""
from __future__ import annotations

import collections
import json
import os
import sys

BATCHES = "/home/czx/embodied-agent-batches"
#: the model-seat cells of each root. `v03` is not one directory: the "153 model-seat
#: episodes" of the merged corpus is the twelve `planner=deepseek` cells of v0.3's E1
#: (six `long_horizon_*` = 63 and six `em_*` = 90), which `a2_cells.py` counts cell by
#: cell. The `rule` cells (`vlm_contrast`, `long_horizon_full_rule`) are not model seat
#: and stay out: a structural zero from a decision source that never authors a plan is a
#: definition, not an observation.
ROOTS = {"v04": os.path.join(BATCHES, "v04", "e1"),
         "v03": os.path.join(BATCHES, "v03", "e1")}
PLAN_EVENTS = ("plan", "plan_revision")


def _truthy(value) -> bool:
    """A `violated` field that arrives as the string `"False"`.

    The plan view publishes its booleans as strings (`satisfied: "True"`,
    `violated: "False"`), so `bool(value)` would call every edge violated -- including the
    three in this corpus, none of which is. The scorer reads the same field the same way
    (`bool(dep.get("violated"))` inside a pydantic-coerced model), which is why
    `a2_check_scorer.py` compares edge *names* and not their violation marks.
    """
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _runs(root: str) -> list[tuple[str, str]]:
    """`(cell, run_dir)` for every model-seat run under one E1 root."""
    out = []
    for cell in sorted(os.listdir(root)):
        cell_dir = os.path.join(root, cell)
        if not os.path.isdir(cell_dir):
            continue
        for run in sorted(os.listdir(cell_dir)):
            run_dir = os.path.join(cell_dir, run)
            manifest_path = os.path.join(run_dir, "manifest.json")
            if not os.path.exists(manifest_path) or not os.path.isdir(os.path.join(run_dir, "episodes")):
                continue
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            if manifest.get("planner") == "rule":
                continue                      # not the model seat
            out.append((cell, run_dir))
    return out


def _events(ep_dir: str) -> list[dict]:
    with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _summary(ep_dir: str) -> dict:
    path = os.path.join(ep_dir, "episode_summary.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_episode(ep_dir: str) -> dict:
    events = _events(ep_dir)
    summary = _summary(ep_dir)
    result = summary.get("result") or {}
    fired = ((summary.get("environment_events") or {}).get("fired")) or []

    edges: dict[tuple[str, str, str], bool] = {}
    trigger_event = None
    trigger_index = None
    # Two ledgers, and the reason there are two: the "before the trigger" counters can only
    # be accumulated up to the first edge-bearing view, which a non-triggering episode
    # never reaches -- so on those the same counter would silently become a whole-episode
    # count and the two sides of the covariate table would stop being the same quantity.
    # `whole` is accumulated identically for all 187 episodes (that is the column the
    # both-sides table uses); `before_edge` is the trigger's own neighbourhood.
    whole = {"feedback_failures": 0, "feedback_rejections": 0,
             "recovery_actions": 0, "plan_views": 0}
    before_edge = None
    for index, e in enumerate(events):
        kind = e["type"]
        payload = e.get("payload") or {}
        if kind in PLAN_EVENTS:
            # the scorer reads the plan view out of `payload["view"]` and nowhere else
            # (`evaluation/long_horizon.py`, the `kind in ("plan", "plan_revision")` arm);
            # reading the payload's top level is the same mistake as looking for `perceive`
            # where the manifest writes `perception`.
            view = payload.get("view") or {}
            whole["plan_views"] += 1
            new_edges = []
            for dep in view.get("dependencies") or []:
                key = (str(dep.get("from_subgoal_id") or dep.get("from") or ""),
                       str(dep.get("on_subgoal_id") or dep.get("on") or ""),
                       str(dep.get("kind") or ""))
                edges[key] = edges.get(key, False) or _truthy(dep.get("violated"))
                new_edges.append(key)
            if new_edges and trigger_event is None:
                trigger_event = {"event_index": index, "type": kind,
                                 "trigger": payload.get("trigger"),
                                 "version": view.get("version"),
                                 "changed": view.get("changed"),
                                 "rows": len(view.get("rows") or []),
                                 "dependencies": view.get("dependencies"),
                                 "violated": view.get("violated")}
                trigger_index = index
                before_edge = dict(whole)
        elif kind == "execution_feedback":
            fb = payload.get("feedback") or {}
            if fb.get("failure_code"):
                whole["feedback_failures"] += 1
            whole["feedback_rejections"] += len(fb.get("rejection_reasons") or [])
        elif kind == "recovery_action":
            whole["recovery_actions"] += 1

    return {
        "episode_id": os.path.basename(ep_dir),
        "case_id": summary.get("case_id"),
        "repeat": summary.get("repeat"),
        "triggered": bool(edges),
        "edges": [f"{f}->{o}:{k}{'!' if v else ''}" for (f, o, k), v in sorted(edges.items())],
        "edge_count": len(edges),
        "violated_edges": sum(1 for v in edges.values() if v),
        "trigger_event": trigger_event,
        "plan_view_count": whole["plan_views"],
        "whole_episode": whole,
        "before_trigger": before_edge,
        "outcome": result.get("terminal_status"),
        "failure_type": result.get("failure_type"),
        "decision_rounds": result.get("decision_rounds"),
        "env_events_fired": len(fired),
    }


def scan(root: str) -> list[dict]:
    rows = []
    for run_index, (cell, run) in enumerate(_runs(root)):
        manifest_path = os.path.join(run, "manifest.json")
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        model = manifest.get("model") or {}
        ep_root = os.path.join(run, "episodes")
        for ep in sorted(os.listdir(ep_root)):
            row = scan_episode(os.path.join(ep_root, ep))
            row.update({
                "cell": cell, "run": os.path.basename(run), "run_index": run_index,
                "seat": f"{model.get('provider')}/{model.get('model')}",
                "planner": manifest.get("planner"),
            })
            rows.append(row)
    return rows


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else None
    out = {}
    for tag, root in ROOTS.items():
        if which and tag != which:
            continue
        rows = scan(root)
        out[tag] = {"root": root, "rows": rows,
                    "episodes": len(rows),
                    "triggered": sum(1 for r in rows if r["triggered"])}
        print(f"\n== {tag} :: {root}")
        print(f"   model-seat episodes={len(rows)}  triggered={out[tag]['triggered']}")
        per_cell = collections.Counter((r["cell"], r["seat"], r["triggered"])
                                       for r in rows)
        cells = sorted({(r["cell"], r["seat"]) for r in rows})
        for cell, seat in cells:
            n = sum(1 for r in rows if r["cell"] == cell and r["seat"] == seat)
            t = sum(1 for r in rows if r["cell"] == cell and r["seat"] == seat and r["triggered"])
            print(f"   cell={cell:<34} seat={seat:<34} episodes={n:<4} triggered={t}")
        for r in rows:
            if r["triggered"]:
                print(f"   TRIGGER {r['cell']}/{r['episode_id']} "
                      f"edges={r['edges']} view={r['trigger_event'].get('version')} "
                      f"trigger={r['trigger_event'].get('trigger')!r} "
                      f"outcome={r['outcome']}/{r['failure_type']} "
                      f"before={r['before_trigger']}")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"a2_scan{'_' + which if which else ''}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())