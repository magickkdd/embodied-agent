"""Preflight over the v2 table: does every v2 case still speak the truth it declares?

`preflight` is the table's own gate -- it builds the real scene, checks the utterance binds to
exactly the hidden truth's (object, region) pairs, and probes the placement instrument. v0.7's
declaration changes touch the utterance, so this is the first thing that can catch a v2 mention
that means something other than v1's did.

Usage:  PYTHONPATH=. <py>
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from embodied_agent.evaluation.long_horizon_tasks import build_long_horizon_set, preflight  # noqa: E402


def main() -> int:
    versions = sys.argv[1:] or ["v2"]
    bad = 0
    for version in versions:
        print(f"=== {version}")
        for case in build_long_horizon_set(version):
            reading = preflight(case)
            ok = reading.get("ok")
            bad += 0 if ok else 1
            detail = {k: v for k, v in reading.items() if k != "ok" and v not in (None, [], {})}
            print(f"  {case.task_id:<32} ok={ok}  {json.dumps(detail, ensure_ascii=False)[:200]}")
    print(f"preflight failures: {bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())