"""v0.5 A2: the ten covariates, triggers and non-triggers side by side.

Criterion 2 of the A2 criteria: "any co-variation must be counted on both sides". This
file is that both-sides table, and it is the only place a hypothesis may come from. It
reads `a2_scan.json` (one row per model-seat episode, triggers and non-triggers in the same
table) and prints, for each of the ten covariates fixed before the scan ran, how the three
triggering episodes sit against the other 184.

Nothing here computes a rate for the corpus and nothing here claims a cause: with three
triggers every row is a reading, and the columns say how thin they are.

Usage:  PYTHONPATH=. <py> work/v05/a2_covariates.py
"""
from __future__ import annotations

import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPORA = ("v04", "v03")


def rows() -> list[dict]:
    with open(os.path.join(HERE, "a2_scan.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for tag in CORPORA:
        for row in data[tag]["rows"]:
            out.append({"corpus": tag, **row})
    return out


def value_of(row: dict, name: str):
    whole = row.get("whole_episode") or {}
    before = row.get("before_trigger") or {}
    if name == "V1_seat":
        return row.get("seat")
    if name == "V2_run":
        return f"{row['corpus']}#{row['run_index']}"
    if name == "V3_case":
        return row.get("case_id")
    if name == "V4_round":
        return (row.get("trigger_event") or {}).get("version", "no-view-version")
    if name == "V5_failures_whole":
        return whole.get("feedback_failures")
    if name == "V6_edge_violated":
        if not row.get("triggered"):
            return "n/a (no edge)"
        return all(v.endswith("!") for v in row.get("edges") or [])
    if name == "V7_recovery_whole":
        return whole.get("recovery_actions")
    if name == "V8_env_events_fired":
        return row.get("env_events_fired")
    if name == "V9_outcome":
        return f"{row.get('outcome')}/{row.get('failure_type')}"
    if name == "V10_rounds":
        return row.get("decision_rounds")
    if name == "V4b_plan_views_whole":
        return whole.get("plan_views")
    raise KeyError(name)


NAMES = ["V1_seat", "V2_run", "V3_case", "V4_round", "V4b_plan_views_whole",
         "V5_failures_whole", "V6_edge_violated", "V7_recovery_whole",
         "V8_env_events_fired", "V9_outcome", "V10_rounds"]


def main() -> int:
    data = rows()
    trig = [r for r in data if r["triggered"]]
    rest = [r for r in data if not r["triggered"]]
    print(f"corpus: {len(data)} model-seat episodes ({len(trig)} triggered, {len(rest)} not)")
    for row in trig:
        print(f"  trigger: {row['corpus']}/{row['cell']}/{row['episode_id']} "
              f"edges={row['edges']} view_version={(row.get('trigger_event') or {}).get('version')} "
              f"trigger={(row.get('trigger_event') or {}).get('trigger')!r} "
              f"before_first_edge_view={row.get('before_trigger')} "
              f"whole_episode={row.get('whole_episode')}")
    for name in NAMES:
        tv = collections.Counter(str(value_of(r, name)) for r in trig)
        rv = collections.Counter(str(value_of(r, name)) for r in rest)
        print(f"\n{name}")
        print(f"  triggers : {dict(tv)}")
        for value, n in sorted(rv.items(), key=lambda kv: -kv[1])[:8]:
            print(f"  others   : {value:<34} {n}")
    # the one question the both-sides table can actually separate at n=3: episodes that
    # filed a recovery action, and how many of those carry an edge
    rec = [r for r in rest if (r.get("whole_episode") or {}).get("recovery_actions")]
    rec_trig = [r for r in trig if (r.get("whole_episode") or {}).get("recovery_actions")]
    print(f"\nrecovery_action filed at all: triggers {len(rec_trig)}/{len(trig)}, "
          f"others {len(rec)}/{len(rest)}; of those, triggered "
          f"{sum(1 for r in rec if r['triggered'])}/{len(rec)}")

    # the confound that n=3 cannot settle: recovery_action count and episode length move
    # together, and both are on the pre-registered list (V7, V10). Printing them next to
    # each other is not a new covariate -- it is the check that keeps V7 from being read
    # as "the recovery regime" when it may only be "a long episode".
    print("\ntop episodes by recovery_action count (the whole corpus, both cells):")
    ranked = sorted(data, key=lambda r: -((r.get("whole_episode") or {}).get("recovery_actions") or 0))
    print(f"  {'rounds':>7} {'recov':>6} {'recov/round':>12}  {'ep':<10} episode")
    for r in ranked[:12]:
        whole = r.get("whole_episode") or {}
        rounds = r.get("decision_rounds") or 0
        rec_n = whole.get("recovery_actions") or 0
        print(f"  {rounds:>7} {rec_n:>6} {(rec_n / rounds if rounds else 0):>12.3f}  "
              f"{'TRIGGER' if r['triggered'] else '-':<10} "
              f"{r['corpus']}/{r['case_id']}.{r.get('repeat')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())