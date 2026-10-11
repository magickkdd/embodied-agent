"""E2''' readings: what the batch owes its pre-registration, in one table.

`configs/experiment/v06_e2_preregistration.json` asks for five things, and this file answers them
from the archive rather than from the run log:

1. **the matched denominator per cell**, with an `infrastructure_error` counted as a miss;
2. **the Q1 split per episode** -- both books and the unattributed remainder. The numbers come
   from two places in the archive and the row says which is which, because they disagree and the
   disagreement is the finding: `episode_end.result.http_requests` is the final total (54 on one
   c3 episode), while the split is only visible as the last `decision_context`'s ledger snapshot
   (42) plus the refusal note's own count ("35 looks billed to 49 requests"). Reporting the
   smaller one as *the* spend would understate the wall by a round, which is exactly the kind of
   flattering error this stage's rules exist to catch. The cap is a boundary rather than a
   promise -- the preflight admits the round already in flight -- so a total of 54 against a cap
   of 48 is the documented behaviour, and it is printed as such instead of being reconciled away;
3. **every failed episode's residual cause named as #25, #26 or #27**, decided mechanically from
   the archive so the naming can be argued with:
   - `#27` the episode ended `BUDGET_EXHAUSTED`;
   - `#26` at a failing round the frame's own record (`provenance.reader.absent` /
     `provenance.geometry`) shows the declared **colour** was not carried -- the named form
     `frame_did_not_see_the_colour`;
   - `#25` the frame carried the colour but not the declared shape, **and** the declaration gives
     that colour more than once -- which is the c3 two-yellow case the SPEC names as #25's
     residual. A shape miss on a colour the declaration gives *once* would instead be flagged
     `regression_of_v05`, because that is the form v0.5 already fixed;
   - anything else is `unattributed`, which the pre-registration treats as a failed acceptance
     item rather than as a fourth cause;
4. **side by side** with E2'' (4/4, 0/4, 0/4 + 1 infrastructure_error, 148 requests) and E2'
   (4/4, 0/4, 0/4, 132), never merged;
5. the archived `budget_caps` and `grounding_map_sha256`, so a repriced cell is recognisable
   from the archive rather than from a report.

Usage:  PYTHONPATH=. <py> [report.json]
"""
from __future__ import annotations

import ast
import collections
import json
import os
import re
import sys

ARCHIVE = "/home/czx/embodied-agent-batches/v06/e2"
EARLIER = {"E2' (v0.4)": {"privileged": "4/4", "stub": "0/4", "vlm": "0/4", "requests": 132},
           "E2'' (v0.5)": {"privileged": "4/4", "stub": "0/4",
                           "vlm": "0/4 (+1 infrastructure_error)", "requests": 148}}
#: "35 looks billed to 49 requests" -- the refusal note's own split, the only place the final
#: perception count is written down rather than snapshotted mid-episode
BILLED = re.compile(r"(\d+) looks billed to (\d+) requests")


def _episode(ep_dir: str) -> dict:
    """One episode as the archive states it: the frames' own record of what they carried, the
    unbound rows that named them, and the final ledger numbers with their provenance."""
    detections = {}       # observation_ref -> [(colour, shape), ...]
    ordinal_of_ref = {}
    last_context_budget = {}
    unbound = []          # (round_index, observation_ref, declared dict)
    ordinal = 0
    ev = os.path.join(ep_dir, "events.jsonl")
    if os.path.exists(ev):
        for line in open(ev, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            payload = event.get("payload") or {}
            if kind == "observation":
                ordinal_of_ref[payload.get("observation_ref")] = ordinal
                ordinal += 1
            elif kind == "perception":
                # the frame is keyed by its own `observation_id` (`per_...`), which is the same
                # name a progress row cites in `evidence_refs`; `based_on_observation_ref` is the
                # *look* (`look_0001_main`) and pairing rows against that would match nothing
                ref = payload.get("observation_id")
                detections[ref] = [((d.get("state_attributes") or {}).get("color"),
                                     (d.get("state_attributes") or {}).get("shape"))
                                   for d in (payload.get("detections") or [])]
            elif kind == "decision_context":
                budget = payload.get("budget") or {}
                last_context_budget = {
                    "perception_requests_used": budget.get("perception_requests_used"),
                    "decision_requests_used": budget.get("decision_requests_used"),
                    "http_requests_used": budget.get("http_requests_used"),
                    "at_round": payload.get("round_index"),
                }
                for row in (payload.get("progress") or []):
                    if "entity_binding" not in (row.get("unmeasured") or []):
                        continue
                    refs = row.get("evidence_refs") or []
                    unbound.append({"round": payload.get("round_index"),
                                    "observation_ref": refs[0] if refs else None,
                                    "entity_id": row.get("entity_id"),
                                    "target_id": row.get("target_id")})

    result = {}
    sp = os.path.join(ep_dir, "episode_summary.json")
    if os.path.exists(sp):
        result = json.load(open(sp, encoding="utf-8")).get("result") or {}
    note = str((result.get("artifacts") or {}).get("note") or "")
    billed = BILLED.search(note)
    total_final = result.get("http_requests")
    perception_final = int(billed.group(2)) if billed else None
    return {"detections": detections, "ordinal_of_ref": ordinal_of_ref,
            "unbound": unbound, "last_context_budget": last_context_budget,
            "unbound_rows": len(unbound), "result": result, "note": note,
            "final": {"http_requests": total_final,
                      "http_requests_source": "episode_end.result.http_requests",
                      "perception_requests": perception_final,
                      "perception_requests_source": ("artifacts.note 'N looks billed to M requests'"
                                                     if billed else "not stated by the archive"),
                      "decision_requests": 0 if billed else
                      last_context_budget.get("decision_requests_used"),
                      "unattributed": (total_final - perception_final
                                       if (total_final is not None and perception_final is not None)
                                       else None)},
            "split_at_last_context": last_context_budget}


def _declared_colours(case_id: str) -> dict:
    """How many entities the declaration gives each colour, read off the frozen case.

    This is what separates #25 from a regression: the ambiguity residual exists only where the
    declaration names the colour twice, which is c3's two yellow bodies.
    """
    sys.path.insert(0, "/home/czx/embodied-agent-robot-agent-embodied-agent-4")
    from embodied_agent.evaluation.tasks import find_case

    case = find_case(case_id, ("long_horizon",))
    counts = collections.Counter()
    for obj in case.objects:
        # a declared object carries its attributes under `attributes`; `color` is the RGB
        # palette triple and `attributes.color` is the name the frame record also uses
        colour = ((obj or {}).get("attributes") or {}).get("color")
        if isinstance(colour, str):
            counts[colour] += 1
    return dict(counts)


def _declared_of(entity_id: str) -> dict | None:
    """`entity_id` is the declared attribute dict as a string while a row is unbound."""
    if not entity_id or not entity_id.startswith("{"):
        return None
    try:
        parsed = ast.literal_eval(entity_id)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _row_causes(ep: dict, multiplicity: dict) -> dict:
    """Name each unbound row from the frame it cited.

    * colour not among that frame's detections -> **#26**, the named `frame_did_not_see_the_colour`;
    * colour present, declared shape absent, and the declaration gives that colour more than once
      -> **#25** (c3's two yellows, the residual the SPEC keeps at that number);
    * colour present, declared shape absent, the colour given once -> **`regression_of_v05`**:
      that is the form v0.5 fixed, so a row landing here is a regression, not a known residual;
    * the declared pair *was* in the frame and the row still failed -> **`unattributed`**.
    """
    rows = []
    for row in ep["unbound"]:
        declared = _declared_of(row.get("entity_id") or "")
        if declared is None:
            rows.append({**row, "cause": "unattributed", "why": "the row names no declared pair"})
            continue
        colour = declared.get("color") or declared.get("colour")
        shape = declared.get("shape")
        seen = ep["detections"].get(row.get("observation_ref")) or []
        colours = [c for c, _ in seen]
        shapes = [s for c, s in seen if c == colour]
        if colour not in colours:
            cause, why = "#26", f"frame {row.get('observation_ref')} carried {sorted(set(colours))}"
        elif shape not in shapes:
            n = multiplicity.get(colour, 1)
            cause = "#25" if n > 1 else "regression_of_v05"
            why = (f"colour {colour} seen with shape(s) {shapes}, declared {shape}; "
                   f"the declaration gives {colour} x{n}")
        else:
            cause, why = "unattributed", "the declared pair was in the frame and the row still failed"
        rows.append({**row, "cause": cause, "why": why})
    tally = collections.Counter(r["cause"] for r in rows)
    return {"rows": rows, "tally": dict(tally),
            "named_cause": (tally.most_common(1)[0][0] if tally else None)}


def main() -> int:
    report_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ARCHIVE, "e2_triple_prime_report.json")
    report = json.load(open(report_path, encoding="utf-8"))

    out = {"report": report_path, "bound": report.get("bound"), "cells": [],
           "side_by_side_earlier": EARLIER, "reading_rules": {
               "#27": "BUDGET_EXHAUSTED",
               "#26": "the frame's own record shows the declared colour absent at a failing round",
               "#25": "colour seen, declared shape not, and the declaration gives that colour "
                       "more than once",
               "unattributed": "anything else -- a failed acceptance item, not a fourth cause"}}
    total = 0
    for cell in report["cells"]:
        s = cell["summary"]
        per_ep = []
        for row in s.get("per_episode", []):
            ep_dir = os.path.join(s["run_dir"], "episodes", row["episode_id"])
            ep = _episode(ep_dir)
            case_id = row["episode_id"].split(".")[0]
            multiplicity = _declared_colours(case_id)
            rows = _row_causes(ep, multiplicity)
            result = ep["result"]
            status = result.get("terminal_status")
            reading = {"episode_id": row["episode_id"], "channel": cell["channel"],
                       "terminal_status": status,
                       "failure_type": result.get("failure_type"),
                       "http_requests": result.get("http_requests"),
                       "objects_completed": result.get("objects_completed"),
                       "objects_total": result.get("objects_total"),
                       "note": ep["note"], "unbound_rows": ep["unbound_rows"],
                       "final": ep["final"], "split_at_last_context": ep["split_at_last_context"],
                       "declared_multiplicity": multiplicity,
                       "unbound_rows_detail": rows["rows"], "cause_tally": rows["tally"],
                       "grounding_sha": row.get("perception")}
            if status != "failed":
                reading["cause"] = None
            elif result.get("failure_type") == "BUDGET_EXHAUSTED":
                reading["cause"] = "#27"
            else:
                # the episode ended for a binding reason: name it by what its own rows say, and
                # when they disagree the tally is printed rather than a winner picked for it
                tally = rows["tally"]
                reading["cause"] = ("/".join(sorted(tally)) if tally else "unattributed")
                reading["cause_rows"] = rows["rows"]
            per_ep.append(reading)
        outcomes = s.get("outcomes") or {}
        total += s.get("http_requests", 0)
        out["cells"].append({
            "key": cell["key"], "channel": cell["channel"], "cap": cell.get("cap"),
            "budget_caps_in_archive": s.get("manifest", {}).get("budget_caps"),
            "budget_profile_max_http": s.get("manifest", {}).get("budget_profile_max_http"),
            "grounding_sha": sorted({r.get("perception") for r in per_ep if r.get("grounding_sha")}),
            "episodes": len(per_ep), "success": outcomes.get("success", 0), "outcomes": outcomes,
            "http_requests": s.get("http_requests"),
            "perception_records": s.get("perception_records"),
            "budget_stops": s.get("budget_stops"),
            "unbound_rows": sum(r.get("unbound_rows", 0) for r in per_ep),
            "per_episode": per_ep,
        })
    out["total_requests"] = total

    with open(os.path.join(ARCHIVE, "e2_triple_prime_readings.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("E2'''  " + report_path)
    print(f"{'cell':<24}{'ok':>7} {'req':>5} {'percept':>8} {'unbound':>8} {'budget_stops':>13}  caps")
    for c in out["cells"]:
        print(f"{c['key']:<24}{c['success']:>3}/{c['episodes']:<3} {c['http_requests']:>5} "
              f"{c['perception_records']:>8} {c['unbound_rows']:>8} "
              f"{str(c['budget_stops']['episodes']):>13}  {c['budget_caps_in_archive']}")
    print(f"total requests {total} / bound {report.get('bound')}")
    print("\nper episode")
    for c in out["cells"]:
        for r in c["per_episode"]:
            f = r["final"]
            print(f"  {c['channel']:<11}{r['episode_id']:<36}{str(r['terminal_status']):<8}"
                  f"total={f['http_requests']} P={f['perception_requests']} "
                  f"unattr={f['unattributed']} ctxP={(r['split_at_last_context'] or {}).get('perception_requests_used')} "
                  f"cause={r['cause']}")
    print("\nunbound rows, named by the frame each one cited")
    for c in out["cells"]:
        for r in c["per_episode"]:
            if r["terminal_status"] != "failed":
                continue
            print(f"  {r['episode_id']:<36} multiplicity={r['declared_multiplicity']} "
                  f"tally={r['cause_tally']} cause={r['cause']}")
            for row in (r.get("cause_rows") or [])[:4]:
                print(f"      r{row.get('round')} {row.get('cause'):<18} {row.get('why')}")
    print(os.path.join(ARCHIVE, "e2_triple_prime_readings.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())