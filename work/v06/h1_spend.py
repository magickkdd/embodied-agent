"""H1's spend, counted from the two ledgers, the way v0.4 had to learn to count it.

v0.4's driver understated its own spend by 356 goal-parse requests when it read only the
per-episode ledger, so the number that guards a bound has to come from `batch_spend` (the
P6-a instrument) over every run root under the batch. The driver sums `episode_summary`'s
`http_requests`, which is one ledger; this is the check on that number rather than a second
estimate.

Usage:  PYTHONPATH=. <py> [archive]
"""
from __future__ import annotations

import glob
import os
import sys

REPO = "/home/czx/embodied-agent-robot-agent-embodied-agent-4"
sys.path.insert(0, REPO)

from embodied_agent.evaluation.run import batch_spend  # noqa: E402


def main() -> int:
    archive = sys.argv[1] if len(sys.argv) > 1 else "/home/czx/embodied-agent-batches/v06/h1"
    per_run, total = [], {"http_requests": 0, "prompt_tokens": 0, "completion_tokens": 0}
    for run in sorted(glob.glob(os.path.join(archive, "*", "*"))):
        if not os.path.isdir(os.path.join(run, "episodes")):
            continue
        spend = batch_spend(run)
        per_run.append({"run": run, **{k: spend[k] for k in total}})
        for key in total:
            total[key] += spend[key]
    for row in per_run:
        print(f"  {row['run']:<70} http={row['http_requests']:<6} "
              f"prompt={row['prompt_tokens']} completion={row['completion_tokens']}")
    print(f"  TOTAL http_requests={total['http_requests']} / bound 930")
    print(f"  remaining {930 - total['http_requests']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())