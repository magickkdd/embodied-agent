"""The new-blood batch's per-episode rows, as the P-D demand profile for c2/c4/c5.

v0.7's table carries `no_confirmed_evidence` for these three cases: they had no archived camera
frame at all. This is the first measurement of their demand, so it is printed as the profile the
table's P-D channel wants: per case and channel, the per-episode final requests, the
perception/decision split at the last round, the unbound-row count, and the episode-level terminal
reason kept apart from the row-level shape (v0.7's lesson, now a criterion).

It also prints any `infrastructure_error` with its named cause, because the pre-registration counts
one as a miss rather than dropping it.

Usage: PYTHONPATH=. <py>
"""
from __future__ import annotations

import collections
import json
import os

ROOT = "/home/czx/embodied-agent-batches/v08/newblood"
with open(os.path.join(ROOT, "newblood_report.json"), encoding="utf-8") as f:
    REPORT = json.load(f)

profiles: dict[tuple[str, str], dict] = collections.defaultdict(
    lambda: {"requests": [], "perception": [], "decision": [], "unbound": [], "outcomes": {},
             "terminal": [], "rows": []})
ledger = []
for run in (os.path.join(ROOT, d) for d in sorted(os.listdir(ROOT))):
    errors = os.path.join(run, "errors.jsonl")
    if os.path.exists(errors):
        with open(errors, encoding="utf-8") as f:
            ledger += [json.loads(line) for line in f if line.strip()]

print(f"{'cell':<16}{'eps':>4}{'ok':>4}{'req/ep':>9}{'P':>5}{'D':>4}{'unbound':>9}  terminal reasons")
for cell in REPORT["cells"]:
    key = cell["key"]
    case_id = cell["case_id"].split("_")[1]
    bucket = profiles[(case_id, cell["channel"])]
    for row in cell["summary"].get("per_episode", []):
        bucket["requests"].append(row.get("http_requests"))
        bucket["perception"].append(row.get("perception_requests"))
        bucket["decision"].append(row.get("decision_requests"))
        bucket["unbound"].append(row.get("unbound_progress_rows"))
        status = str(row.get("episode_terminal_status"))
        bucket["outcomes"][status] = bucket["outcomes"].get(status, 0) + 1
        bucket["terminal"].append(row.get("episode_termination_reason")
                                  or row.get("episode_failure_type") or status)
        bucket["rows"].append(row["episode_id"])
    spent = [r for r in bucket["requests"] if r is not None]
    print(f"{key:<16}{cell['summary'].get('episodes'):>4}{cell['summary'].get('successes'):>4}"
          f"{str(spent):>9}{str(bucket['perception']):>5}{str(bucket['decision']):>4}"
          f"{str(bucket['unbound']):>9}  {bucket['terminal']}")

print("\n=== P-D 需求画像（c2/c4/c5 的第一次相机实测）")
out = {"basis": "v0.8 new-blood batch, rule planner, camera channels, 2 repeats",
       "cases": {}}
for (case_id, channel), bucket in sorted(profiles.items()):
    spent = [r for r in bucket["requests"] if r is not None]
    out["cases"].setdefault(case_id, {})[channel] = {
        "episodes": len(bucket["rows"]),
        "requests_per_episode": spent,
        "max_final_request": max(spent) if spent else None,
        "perception_at_last_round": bucket["perception"],
        "decision_at_last_round": bucket["decision"],
        "unbound_rows": bucket["unbound"],
        "outcomes": bucket["outcomes"],
    }
    print(f"  c{case_id} {channel:<11}requests/ep={spent} max={max(spent) if spent else None} "
          f"P={bucket['perception']} D={bucket['decision']} unbound={bucket['unbound']}")

out["ledger_rows"] = [r.get("outcome") for r in ledger]
print("\ninfrastructure ledger rows:", out["ledger_rows"])
for row in ledger:
    print("   ", json.dumps(row, ensure_ascii=False)[:200])

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p8_demand_profiles.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(path)