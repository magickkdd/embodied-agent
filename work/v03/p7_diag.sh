#!/usr/bin/env bash
# Diagnose the 408: is the token valid, does the repo exist, and can the link carry a POST?
#
# The 408 survived dropping the pack from 141 MB to 3.1 MB, so it is not a size problem. Three
# candidates remain, and they need different fixes:
#
#   * the token is bad or lacks scope      -> 401/403 on an authenticated GET, not a 408 on POST
#   * the repo does not exist / is private  -> 404 on the API
#   * the link cannot carry git-receive-pack-> small GETs succeed, large POSTs time out
#
# The token is never printed or logged. Only status codes and a few non-secret fields are.
set -uo pipefail

TOKEN_FILE=/home/czx/.robo_agent_push_token
[ -f "$TOKEN_FILE" ] || { echo "no token file"; exit 1; }
TOKEN=$(cat "$TOKEN_FILE")

hdr=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json"
     -H "X-GitHub-Api-Version: 2022-11-28")

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "=== 1. is the token valid? (GET /user) ==="
echo "  HTTP $(code "${hdr[@]}" https://api.github.com/user)   200 = valid"
LOGIN=$(curl -s "${hdr[@]}" https://api.github.com/user | sed -n 's/.*"login":"\([^"]*\)".*/\1/p' | head -1)
echo "  authenticated as: ${LOGIN:-<unreadable>}"

echo
echo "=== 2. does magickkdd/robo-agent exist, and is it empty? ==="
echo "  HTTP $(code "${hdr[@]}" https://api.github.com/repos/magickkdd/robo-agent)"
curl -s "${hdr[@]}" https://api.github.com/repos/magickkdd/robo-agent \
  | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
except Exception as e:
    print("  (unreadable response)"); raise SystemExit
for k in ("full_name","private","size","default_branch","pushed_at"):
    if k in d: print(f"  {k} = {d[k]}")' 2>/dev/null

echo
echo "=== 3. can this link carry a POST at all? ==="
echo "  POST /user/issues is not allowed, so this is a token-permission probe instead:"
echo "  HTTP $(code -X POST -d '{}' "${hdr[@]}" https://api.github.com/user/issues)  (404/401 = the POST reached GitHub)"

echo
echo "=== 4. a plain-POST reachability test with a sizeable body ==="
head -c 200000 /dev/urandom > /tmp/p7_probe.bin
echo "  POST 200 KB to a harmless endpoint: HTTP $(code -X POST --data-binary @/tmp/p7_probe.bin \
  -H 'Content-Type: application/octet-stream' "${hdr[@]}" https://api.github.com/user/keys)"
rm -f /tmp/p7_probe.bin

unset TOKEN
echo
echo "=== 5. token scope, as GitHub reports it ==="
curl -s -D - -o /dev/null "${hdr[@]}" https://api.github.com/user 2>/dev/null \
  | grep -i 'x-oauth-scopes\|x-accepted' | head -3
echo "  (an empty scope header means a fine-grained token; the API will still refuse what it lacks)"
