"""v0.5 A1 step 0c: the per-episode `perception`, `goal_resolution` and `candidates` rows.

Third and last input-manifest script. It exists for one specific question the previous two
could not answer: `decision_context.progress` showed a task item whose `entity_id` is a
stringified attribute dict with `unmeasured: ["entity_binding"]`, which is
`RuntimeVerifier.progress` reporting an assignment it could not bind. Whether that is a
detection miss (the frame never saw the body) or a binding failure (the frame saw it and the
bridge would not bind it) is the whole of RQ11's ring question, and the archive has to say
which. These three keys are where it can say it.

Usage:  PYTHONPATH=. <py> work/v05/a1_keys3.py
"""
from __future__ import annotations

import json
import os

E2 = "/home/czx/embodied-agent-batches/v04/e2"
CHANNELS = ("privileged", "stub", "vlm")


def _run(channel: str) -> str:
    root = os.path.join(E2, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    return os.path.join(root, runs[0])


def main() -> None:
    for channel in CHANNELS:
        run = _run(channel)
        for ep in sorted(os.listdir(os.path.join(run, "episodes"))):
            ep_dir = os.path.join(run, "episodes", ep)
            with open(os.path.join(ep_dir, "episode_summary.json"), encoding="utf-8") as f:
                summary = json.load(f)
            print(f"\n\n===== {channel} / {ep}")
            print("  summary.perception:", json.dumps(summary.get("perception"),
                                                     ensure_ascii=False)[:1800])
            print("  summary.goal_resolution:", json.dumps(summary.get("goal_resolution"),
                                                           ensure_ascii=False)[:1800])
            print("  summary.decision_source:", json.dumps(summary.get("decision_source"),
                                                           ensure_ascii=False)[:600])
            print("  summary.environment_events:",
                  json.dumps(summary.get("environment_events"), ensure_ascii=False)[:600])
            with open(os.path.join(ep_dir, "events.jsonl"), encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
            for payload in [e["payload"] for e in events if e["type"] == "decision_context"]:
                prog = [(p["entity_id"], p["value"], p.get("unmeasured"))
                        for p in payload.get("progress", [])]
                cands = [(c.get("candidate_id"), c.get("entity_id"), c.get("target_id"))
                         for c in payload.get("candidates", [])]
                print(f"  r{payload['round_index']:>2} v{payload['state_version']:<3} "
                      f"progress={json.dumps(prog, ensure_ascii=False)}")
                print(f"       candidates={json.dumps(cands, ensure_ascii=False)}")


if __name__ == "__main__":
    main()