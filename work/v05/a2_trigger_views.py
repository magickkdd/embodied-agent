"""v0.5 A2: the three plan views that carry a dependency edge, verbatim.

The covariate table says which episodes triggered; this says what was actually written in
the view that triggered, so the hypothesis section can quote the record instead of
paraphrasing it. Selection is the scan's own (any view with a non-empty `dependencies`), and
nothing is filtered further.

Usage:  PYTHONPATH=. <py> work/v05/a2_trigger_views.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    with open(os.path.join(HERE, "a2_scan.json"), encoding="utf-8") as f:
        scan = json.load(f)
    for tag in ("v04", "v03"):
        for row in scan[tag]["rows"]:
            if not row["triggered"]:
                continue
            view = row.get("trigger_event") or {}
            print(f"\n===== {tag} / {row['cell']} / {row['episode_id']}  "
                  f"(seat {row['seat']}, outcome {row['outcome']}/{row['failure_type']})")
            print(json.dumps({k: v for k, v in view.items() if k != "rows"},
                             ensure_ascii=False, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())