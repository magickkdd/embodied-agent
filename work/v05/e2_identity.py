"""v0.5 P4: the identity items the pre-registration names, read off both archives.

Three facts and nothing else: each cell's manifest (channel, model, offline, code commit and
dirty flag), each episode's `grounding_map_sha256`, and the two-ledger spend per cell (requests
made from `model_calls.jsonl` against requests attributed to results). The acceptance item
about identity is a comparison, and a comparison needs both sides read by the same code.

Usage:  PYTHONPATH=. <py> work/v05/e2_identity.py
"""
from __future__ import annotations

import glob
import json
import os

BATCHES = "/home/czx/embodied-agent-batches"
ARCS = {"v04": os.path.join(BATCHES, "v04", "e2"), "v05": os.path.join(BATCHES, "v05", "e2")}
CHANNELS = ("privileged", "stub", "vlm")


def _run_dir(root: str, channel: str) -> str:
    cell = os.path.join(root, f"long_horizon_{channel}")
    runs = [d for d in os.listdir(cell) if os.path.isdir(os.path.join(cell, d, "episodes"))]
    return os.path.join(cell, runs[-1])


def _json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    for arc, root in ARCS.items():
        print(f"\n================ {arc}")
        for channel in CHANNELS:
            run_dir = _run_dir(root, channel)
            manifest = _json(os.path.join(run_dir, "manifest.json")) or {}
            perception = manifest.get("perception") or {}
            made = attributed = 0
            digests = {}
            for ep in sorted(os.listdir(os.path.join(run_dir, "episodes"))):
                ep_dir = os.path.join(run_dir, "episodes", ep)
                mc = os.path.join(ep_dir, "model_calls.jsonl")
                if os.path.exists(mc):
                    with open(mc, encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                made += int(json.loads(line).get("http_requests_this_call") or 0)
                summary = _json(os.path.join(ep_dir, "episode_summary.json")) or {}
                result = summary.get("result") or {}
                attributed += int(result.get("http_requests") or 0)
                digest = (summary.get("perception") or {}).get("grounding_map_sha256")
                if digest:
                    digests[ep.split(".")[0]] = digest[:12]
            print(f"  {channel:<11} channel={perception.get('channel')} "
                  f"arm={perception.get('arm')} offline={manifest.get('offline')} "
                  f"model={(manifest.get('model') or {}).get('model')} "
                  f"commit={(manifest.get('code') or {}).get('commit')} "
                  f"dirty={(manifest.get('code') or {}).get('dirty')}")
            print(f"              requests_made={made} requests_attributed={attributed} "
                  f"map_sha256={digests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())