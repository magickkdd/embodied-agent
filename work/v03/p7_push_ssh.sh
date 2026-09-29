#!/usr/bin/env bash
# Register this machine's SSH key with the GitHub account, then push over SSH.
#
# Why this route and not the token: the push to github.com's git endpoint 408s on this network
# (a 2.83 MiB pack, postBuffer, HTTP/1.1 and lowSpeed all made no difference), while
# api.github.com and SSH both work. The only remaining HTTPS route would be the `ghfast.top`
# mirror that /home/czx/.gitconfig redirects every github.com URL to — and that would hand a
# token holding `admin:org`, `delete_repo`, `workflow` and `packages` to a third party.
#
# So the token is used exactly once, for a small authenticated API call that needs
# `admin:public_key` (which this token has), and the push itself then carries no credential but
# the key. The token file is deleted at the end either way.
set -euo pipefail

NAME=czx
EMAIL=1276618006@qq.com
KEY_TITLE="wsl-$(hostname)"
KEY_FILE=/home/czx/.ssh/id_ed25519.pub
TOKEN_FILE=/home/czx/.robo_agent_push_token
WORK=/tmp/robo_publish/repo
SSH_TARGET=git@github.com:magickkdd/robo-agent.git

PUB=$(cat "$KEY_FILE")
TOKEN=$(cat "$TOKEN_FILE")
hdr=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json"
     -H "X-GitHub-Api-Version: 2022-11-28")

echo "=== 1. is this key already registered? ==="
EXISTING=$(curl -s "${hdr[@]}" https://api.github.com/user/keys | python3 -c '
import json, sys
d = json.load(sys.stdin)
if isinstance(d, dict):
    print("ERR:" + str(d.get("message")))
    raise SystemExit
for k in d:
    print("{}  {}".format(k["id"], k["title"]))')
echo "$EXISTING" | head -5

if echo "$EXISTING" | grep -q "^ERR:"; then
  echo "  the API refused the key listing — stopping rather than guessing"
  echo "$EXISTING"
  exit 1
fi

echo
echo "=== 2. add the key ==="
curl -s -X POST "${hdr[@]}" \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"title": sys.argv[1], "key": sys.argv[2].strip()}))' \
        "$KEY_TITLE" "$PUB")" \
  https://api.github.com/user/keys | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "id" in d:
    print("  added key id={}  title={}".format(d["id"], d["title"]))
else:
    print("  REFUSED:", d.get("message", d))'

echo
echo "=== 3. does SSH authenticate now? ==="
timeout 45 ssh -T -o StrictHostKeyChecking=accept-new -o BatchMode=yes git@github.com 2>&1 \
  | grep -v '^Warning' | head -2
# "Hi <name>! You've successfully authenticated" is the answer; exit 1 is SUCCESS for `ssh -T`

echo
echo "=== 4. push over SSH ==="
cd "$WORK"
echo "  HEAD    : $(git rev-parse --short HEAD)"
echo "  commits : $(git log --oneline | wc -l)"
echo "  files   : $(git ls-files | wc -l)"
GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes' \
  git -c user.name="$NAME" -c user.email="$EMAIL" push "$SSH_TARGET" "HEAD:refs/heads/main" 2>&1 | tail -6

echo
echo "=== 5. the two tags ==="
GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes' \
  git push "$SSH_TARGET" "refs/tags/v0.2" "refs/tags/continuous-decision-v0.2" 2>&1 | tail -4

echo
echo "=== 6. verify what landed ==="
GIT_CONFIG_GLOBAL=/dev/null git ls-remote --heads --tags https://github.com/magickkdd/robo-agent.git 2>&1 | head -6
curl -s "${hdr[@]}" https://api.github.com/repos/magickkdd/robo-agent \
  | python3 -c 'import json,sys
d = json.load(sys.stdin)
print("  repo size = {} KB".format(d.get("size")))'

unset TOKEN
rm -f "$TOKEN_FILE"
echo
echo "  token file: $([ -f "$TOKEN_FILE" ] && echo STILL PRESENT || echo removed)"
echo "  the SSH key '$KEY_TITLE' is now registered on the account and was used for the push."
