"""v0.5 A1 step 0b: the *content* of the records the four candidate rings live in.

Same status as `a1_keys.py` -- an input manifest, not an analysis. It exists because the
criteria must be written against the fields that are really there (v0.4's #19 was an
instrument that blinded itself to a key that existed all along, and this stage refuses to
repeat that). It prints representative records verbatim and stops.

Usage:  PYTHONPATH=. <py> work/v05/a1_keys2.py
"""
from __future__ import annotations

import json
import os

E2 = "/home/czx/embodied-agent-batches/v04/e2"


def _run(channel: str) -> str:
    root = os.path.join(E2, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    return os.path.join(root, runs[0])


def _events(ep_dir: str) -> list[dict]:
    with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _pick(events, kind, n=1):
    return [e["payload"] for e in events if e["type"] == kind][:n]


def _dump(label, obj):
    print(f"\n--- {label}")
    print(json.dumps(obj, ensure_ascii=False, indent=1)[:2600])


def main() -> None:
    for channel in ("stub", "vlm"):
        run = _run(channel)
        with open(os.path.join(run, "manifest.json"), encoding="utf-8") as f:
            man = json.load(f)
        print(f"\n\n########## {channel} manifest keys: {sorted(man)}")
        for key in ("planner", "model", "decision_source", "perceive", "offline", "commit",
                    "task_set", "subset", "modes", "arms"):
            if key in man:
                _dump(f"{channel}.manifest.{key}", man[key])
        for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
            ep_dir = os.path.join(run, "episodes", ep)
            events = _events(ep_dir)
            with open(os.path.join(ep_dir, "episode_summary.json"), encoding="utf-8") as f:
                summary = json.load(f)
            print(f"\n\n===== {channel} / {ep} summary keys: {sorted(summary)}")
            _dump(f"{ep}.summary.top", {k: v for k, v in summary.items()
                                        if k not in ("events", "result")})
            _dump(f"{ep}.summary.result", summary.get("result"))
            for payload in _pick(events, "observation", 1):
                _dump(f"{ep}.observation", payload)
            for payload in _pick(events, "decision_context", 1):
                _dump(f"{ep}.decision_context", payload)
            for payload in _pick(events, "decision", 2):
                _dump(f"{ep}.decision", payload)
            for payload in _pick(events, "execution_feedback", 2):
                _dump(f"{ep}.execution_feedback", payload)
            for payload in _pick(events, "skill_call", 1):
                _dump(f"{ep}.skill_call", payload)
            for payload in _pick(events, "terminated_blocked", 1):
                _dump(f"{ep}.terminated_blocked", payload)
            for payload in _pick(events, "skill_gap", 1):
                _dump(f"{ep}.skill_gap", payload)
            for payload in _pick(events, "perception", 1):
                _dump(f"{ep}.perception", payload)
            calls = os.path.join(ep_dir, "model_calls.jsonl")
            if os.path.exists(calls):
                with open(calls, encoding="utf-8") as f:
                    first = json.loads(f.readline())
                _dump(f"{ep}.model_call.first", first)


if __name__ == "__main__":
    main()