#!/usr/bin/env bash
# Is the local SSH key registered with GitHub, and can this network reach GitHub over SSH?
#
# SSH is the clean way out of the 408: it is a different protocol on a different port (22, or 443
# via ssh.github.com), and it authenticates with the key rather than the token — so the very
# powerful personal access token that is currently sitting on disk would not be sent anywhere at
# all, not even to a mirror.
#
# `accept-new` is used for the host key so the test does not block on a prompt. The fingerprint is
# printed either way, because "trusted on first use" is a real trust decision and the reader should
# see what they accepted.
set -uo pipefail

echo "=== the key we would use ==="
ls -l ~/.ssh/id_ed25519.pub
echo "  type/size: $(ssh-keygen -lf ~/.ssh/id_ed25519.pub 2>/dev/null | awk '{print $2, $3}')"
echo "  (only the type and size — a public key is public, but the point is to show which key)"

echo
echo "=== port 22: ssh -T git@github.com ==="
timeout 45 ssh -T -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 \
  -o BatchMode=yes git@github.com 2>&1 | head -4
echo "  (exit ${PIPESTATUS[0]}; 'successfully authenticated' means the key IS registered)"

echo
echo "=== port 443: ssh.github.com ==="
timeout 45 ssh -T -p 443 -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 \
  -o BatchMode=yes git@ssh.github.com 2>&1 | head -4
echo "  (exit ${PIPESTATUS[0]})"

echo
echo "=== the host keys we accepted ==="
ssh-keygen -F github.com 2>/dev/null | grep -v '^#' | cut -c1-80 || echo "  none recorded"
ssh-keygen -F ssh.github.com 2>/dev/null | grep -v '^#' | cut -c1-80 || echo "  none recorded"

echo
echo "=== what ~/.ssh/config already says ==="
cat ~/.ssh/config
