#!/usr/bin/env bash
# What is actually on the remote right now? The push prints "Everything up-to-date" and then
# exits 1, which is self-contradictory: either nothing needed pushing, or something did and the
# connection died afterwards. Both are consistent with a ref having landed and the sideband
# channel dying on the way back — so the remote is asked directly rather than inferred.
set -uo pipefail
TARGET=https://github.com/magickkdd/robo-agent.git
TOKEN_FILE=/home/czx/.robo_agent_push_token
TOKEN=$(cat "$TOKEN_FILE")
hdr=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json"
     -H "X-GitHub-Api-Version: 2022-11-28")

echo "=== git ls-remote (git protocol) ==="
GIT_CONFIG_GLOBAL=/dev/null git ls-remote --heads --tags "$TARGET" 2>&1 | head -8
echo "  (no output above = no refs)"

echo
echo "=== GitHub API: the repo's own view ==="
curl -s "${hdr[@]}" https://api.github.com/repos/magickkdd/robo-agent | python3 -c '
import json, sys
d = json.load(sys.stdin)
for k in ("size", "default_branch", "pushed_at", "empty"):
    if k in d:
        print(f"  {k} = {d[k]}")
print("  size is in KB, so >0 means something landed")'

echo
echo "=== GitHub API: the branches it lists ==="
curl -s "${hdr[@]}" https://api.github.com/repos/magickkdd/robo-agent/branches | python3 -c '
import json, sys
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("  ", d.get("message", d))
elif not d:
    print("   (no branches)")
for b in d:
    print(f"   {b[\"name\"]}  {b[\"commit\"][\"sha\"][:10]}")' 2>/dev/null || echo "  (unreadable)"

echo
echo "=== GitHub API: the default branch's tree, if any ==="
curl -s "${hdr[@]}" \
  "https://api.github.com/repos/magickkdd/robo-agent/contents/" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("  ", d.get("message", "(no contents)"))
else:
    print(f"   {len(d)} entries at the root:")
    for e in d[:25]:
        print(f"     {e[\"type\"][:4]}  {e[\"name\"]}")' 2>/dev/null || echo "  (unreadable)"

unset TOKEN
