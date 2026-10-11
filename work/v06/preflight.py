"""v0.6 pre-batch gate: the frozen schema and the three gates, in one reading.

Written as a file rather than an inline command because a one-liner long enough to be worth
reading loses its quotes inside `bash -lc` more often than it runs. Nothing here is v0.6 logic:
it is the SPEC's "immediately before the first request" check, and it prints what it compared
so a failure says which field moved.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable

GATES = ["freeze", "prereg", "em-pairs"]


def main() -> int:
    sys.path.insert(0, REPO)
    from embodied_agent.core.v02 import schema_fingerprint

    with open(os.path.join(REPO, "configs", "experiment", "v02_schema_freeze.json"),
              encoding="utf-8") as f:
        doc = json.load(f)
    # the file wraps the fingerprint under its own key; compare the payload the code returns
    # against that payload, not against the wrapper's other bookkeeping fields.
    frozen = doc.get("schema_fingerprint", doc)
    live = schema_fingerprint()
    moved = sorted(k for k in set(live) | set(frozen) if live.get(k) != frozen.get(k))
    print(f"schema_fingerprint: {'MATCH' if not moved else 'DRIFT ' + str(moved)}")

    rc_all = 0 if not moved else 1
    for gate in GATES:
        r = subprocess.run([PY, "-m", "embodied_agent.cli", gate, "--check"],
                           capture_output=True, text=True, cwd=REPO,
                           env={**os.environ, "PYTHONPATH": "."})
        said = [ln for ln in (r.stdout + r.stderr).splitlines()
                if ln.strip() and "pybullet" not in ln]
        print(f"{gate:<14} rc={r.returncode}  {said[-1][:110] if said else ''}")
        rc_all |= r.returncode
    print("ALL GREEN" if rc_all == 0 else "NOT GREEN")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())