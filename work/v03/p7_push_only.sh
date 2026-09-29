#!/usr/bin/env bash
# The push itself, on its own, so its output and exit code are visible rather than inferred from
# a pipeline that `set -e` may have cut short in the previous run.
set -uo pipefail
cd /tmp/robo_publish/repo
export GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes'
TARGET=git@github.com:magickkdd/robo-agent.git

echo "=== local side ==="
echo "  HEAD     : $(git rev-parse HEAD)"
echo "  commits  : $(git log --oneline | wc -l)"
echo "  files    : $(git ls-files | wc -l)"
echo "  user     : $(git -c user.name=czx -c user.email=1276618006@qq.com config user.name) <$(git -c user.name=czx -c user.email=1276618006@qq.com config user.email)>"

echo
echo "=== push HEAD -> main ==="
timeout 1200 git -c user.name=czx -c user.email=1276618006@qq.com \
    push --verbose "$TARGET" HEAD:refs/heads/main
rc=$?
echo "  rc=$rc"

echo
echo "=== remote state after ==="
GIT_CONFIG_GLOBAL=/dev/null git ls-remote --heads "$TARGET" 2>&1 | head -3
echo "  (an sha here means the branch landed)"
