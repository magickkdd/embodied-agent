"""v0.5 A1 step 0: what the E2' archive actually contains, by key name.

Not an analysis: this exists so the criteria written next are written against the keys
that are really on disk rather than the ones someone remembers. It prints, per channel,
the event types each episode filed and the payload keys of the four candidate bottleneck
rings, and nothing else -- no counting, no verdict. Run once, read, then keep its output
next to the criteria as the "input manifest" SPEC §6 asks for.

Usage:  PYTHONPATH=. <py> work/v05/a1_keys.py
"""
from __future__ import annotations

import collections
import json
import os

E2 = "/home/czx/embodied-agent-batches/v04/e2"
CHANNELS = ("privileged", "stub", "vlm")


def _cell(channel: str) -> str:
    root = os.path.join(E2, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    assert len(runs) == 1, f"{channel}: expected one run directory, found {runs}"
    return os.path.join(root, runs[0])


def _events(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    for channel in CHANNELS:
        run = _cell(channel)
        print(f"\n===== {channel} :: {os.path.basename(run)}")
        with open(os.path.join(run, "manifest.json"), encoding="utf-8") as f:
            man = json.load(f)
        print("  manifest.perception:", json.dumps(man.get("perception"), ensure_ascii=False))
        ep_root = os.path.join(run, "episodes")
        for ep in sorted(os.listdir(ep_root)):
            ep_dir = os.path.join(ep_root, ep)
            events = _events(os.path.join(ep_dir, "events.jsonl"))
            types = collections.Counter(e["type"] for e in events)
            summary_path = os.path.join(ep_dir, "episode_summary.json")
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)
            result = summary.get("result") or summary
            print(f"\n  -- {ep}  events={len(events)}")
            print(f"     outcome={result.get('outcome') or summary.get('outcome')} "
                  f"failure_type={result.get('failure_type')} "
                  f"termination_reason={result.get('termination_reason')}")
            print("     types:", dict(types))
            for kind in ("observation", "perception", "decision", "execution_feedback",
                         "terminated_blocked", "skill_call", "finish_check", "episode_end"):
                (row,) = [e["payload"] for e in events if e["type"] == kind][:1] or [None]
                if row is not None:
                    keys = sorted(row)
                    print(f"     {kind:20s} keys={keys}")
            looks = os.path.join(ep_dir, "perception")
            if os.path.isdir(looks):
                names = sorted(os.listdir(looks))
                print(f"     perception/ files={len(names)} first={names[:2]}")


if __name__ == "__main__":
    main()