#!/usr/bin/env bash
# Push the two tags, verify the whole thing landed, and remove the token file.
set -uo pipefail
export GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes'
cd /tmp/robo_publish/repo
TARGET=git@github.com:magickkdd/robo-agent.git
API=https://api.github.com/repos/magickkdd/robo-agent
TOKEN_FILE=/home/czx/.robo_agent_push_token

echo "=== push the two tags ==="
git push "$TARGET" refs/tags/v0.2 refs/tags/continuous-decision-v0.2 2>&1 | tail -4
echo "  rc=${PIPESTATUS[0]}"

echo
echo "=== every ref now on the remote ==="
GIT_CONFIG_GLOBAL=/dev/null git ls-remote --heads --tags "$TARGET" 2>&1

echo
echo "=== GitHub's own view ==="
if [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(cat "$TOKEN_FILE")
  hdr=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json"
       -H "X-GitHub-Api-Version: 2022-11-28")
  curl -s "${hdr[@]}" "$API" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("  full_name    =", d.get("full_name"))
print("  private      =", d.get("private"))
print("  size         =", d.get("size"), "KB")
print("  default      =", d.get("default_branch"))'
  echo "  --- the root of the default branch ---"
  curl -s "${hdr[@]}" "$API/contents/" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("  ", d.get("message"))
else:
    print("   {} entries:".format(len(d)))
    for e in d:
        print("     {}  {}".format(e["type"][:4], e["name"]))'
  echo "  --- the newest commit ---"
  curl -s "${hdr[@]}" "$API/commits?per_page=1" | python3 -c '
import json, sys
d = json.load(sys.stdin)
c = d[0]
print("  ", c["sha"][:10], c["commit"]["author"]["name"], "<" + c["commit"]["author"]["email"] + ">")
print("  ", c["commit"]["message"].splitlines()[0][:90])'
  unset TOKEN
fi

echo
echo "=== the token file goes away now ==="
rm -f "$TOKEN_FILE"
echo "  token file: $([ -f "$TOKEN_FILE" ] && echo STILL PRESENT || echo removed)"

echo
echo "=== the local repository is untouched by any of this ==="
cd /home/czx/embodied-agent-robot-agent-embodied-agent-4
echo "  local HEAD  : $(git rev-parse --short HEAD)  (the un-rewritten history)"
echo "  local origin: $(git remote get-url origin)"
echo "  local remotes: $(git remote | tr '\n' ' ')"
echo "  local uncommitted: $(git status --porcelain | wc -l)"
echo "  note: the pushed copy has different SHAs on purpose — the artefacts had to come out of the"
echo "  history, and the 27 commit messages, authors and dates were carried across unchanged."
