#!/usr/bin/env bash
# Retry the push with the three transport settings that fix HTTP 408 on git push.
#
# The diagnosis was already narrow: the token authenticates (GET /user -> 200), the target repo
# exists and is public, a 200 KB POST to api.github.com succeeds, and the pack is only 3.1 MB. So
# the failure is specific to how `git push` frames its request, not to size, auth or reachability.
#
# git streams the pack with `Transfer-Encoding: chunked` unless `http.postBuffer` is large enough
# to hold it, and a chunked POST is exactly what some middleboxes drop — the server sees a request
# that never completes its body and answers 408. Setting postBuffer above the pack size makes git
# send Content-Length instead. `lowSpeedLimit=0` stops git aborting on a slow-but-progressing
# link, and HTTP/1.1 is requested because some proxies mishandle HTTP/2 on this endpoint.
set -uo pipefail

WORK=/tmp/robo_publish/repo
TARGET=https://github.com/magickkdd/robo-agent.git
NAME=czx
EMAIL=1276618006@qq.com
TOKEN_FILE=/home/czx/.robo_agent_push_token

[ -d "$WORK/.git" ] || { echo "no prepared copy at $WORK — run p7_publish.sh first"; exit 1; }
[ -f "$TOKEN_FILE" ] || { echo "no token file"; exit 1; }

cd "$WORK"
echo "=== what is about to be sent ==="
echo "  HEAD          : $(git rev-parse --short HEAD)"
echo "  commits       : $(git log --oneline | wc -l)"
echo "  tracked files : $(git ls-files | wc -l)"
echo "  .git size     : $(du -sh .git | cut -f1)"
echo "  pack size     : $(git count-objects -vH | sed -n 's/^size-pack: *//p')"

TOKEN=$(cat "$TOKEN_FILE")
AUTH=$(printf 'x-access-token:%s' "$TOKEN" | base64 -w0)
unset TOKEN

echo
echo "=== push with postBuffer / lowSpeed / HTTP/1.1 ==="
set +e
GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
GIT_HTTP_LOW_SPEED_LIMIT=0 GIT_HTTP_LOW_SPEED_TIME=999999 \
git -c user.name="$NAME" -c user.email="$EMAIL" \
    -c "http.extraHeader=Authorization: Basic $AUTH" \
    -c http.postBuffer=524288000 \
    -c http.lowSpeedLimit=0 \
    -c http.lowSpeedTime=999999 \
    -c http.version=HTTP/1.1 \
    push "$TARGET" "HEAD:refs/heads/main" 2>&1 | tail -10
rc=${PIPESTATUS[0]}
set -e
echo "  rc=$rc"

if [ "$rc" = "0" ]; then
  echo
  echo "=== the two tags ==="
  GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
  git -c "http.extraHeader=Authorization: Basic $AUTH" \
      -c http.postBuffer=524288000 -c http.version=HTTP/1.1 \
      push "$TARGET" "refs/tags/v0.2" "refs/tags/continuous-decision-v0.2" 2>&1 | tail -4
  unset AUTH
  rm -f "$TOKEN_FILE"
  echo
  echo "=== what landed ==="
  GIT_CONFIG_GLOBAL=/dev/null git ls-remote --heads --tags "$TARGET" 2>&1 | head -6
  echo "  token file: $([ -f "$TOKEN_FILE" ] && echo STILL PRESENT || echo removed)"
  exit 0
fi

echo
echo "  still failing. Falling back to the GitHub API (git database), which is a different"
echo "  endpoint and a different request shape from git-receive-pack:"
unset AUTH
exit 1
