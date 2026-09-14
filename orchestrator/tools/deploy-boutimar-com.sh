#!/usr/bin/env bash
# Deploy boutimar.com from THIS Mac, whose IP is on the FTP allowlist.
#
# Why this exists: the host firewalls FTP by IP, and GitHub's runners have
# ever-changing IPs that cannot be allowlisted — so the GitHub deploy is blocked
# at the door (531). This Mac's IP can be allowlisted, so the upload runs from
# here instead. It NEVER stores the password: it prompts for it, hidden, each run.
#
# Usage:
#   bash orchestrator/tools/deploy-boutimar-com.sh          # articles + sitemap (fast)
#   bash orchestrator/tools/deploy-boutimar-com.sh --full   # entire site incl. images
#
# It pulls the latest main, builds, then uploads over FTPS. Reads the password
# from a hidden prompt or the FTP_PASSWORD env var if you exported one.
set -euo pipefail

HOST="server22gr.axspace.com"
USER="deploy@boutimar.com"
REPO_DIR="$(cd "$(dirname "$0")/../../boutimar-com" && pwd)"
FULL=0; [ "${1:-}" = "--full" ] && FULL=1

echo "▸ boutimar.com deploy — from $(curl -fsS --max-time 10 https://api.ipify.org || echo '?') (must be on the FTP allowlist)"

# ── 1. latest source ────────────────────────────────────────────────────────
cd "$REPO_DIR"
echo "▸ pulling latest main…"
git pull --ff-only origin main

# ── 2. build ────────────────────────────────────────────────────────────────
echo "▸ building (npm ci && npm run build)…"
npm ci --silent
npm run build
test -f dist/index.html || { echo "✗ build produced no dist/index.html"; exit 1; }
LOCAL=$(grep -c "<loc>" dist/sitemap.xml || echo 0)
echo "  built OK — sitemap has $LOCAL URLs"

# ── 3. the password, never stored ───────────────────────────────────────────
if [ -z "${FTP_PASSWORD:-}" ]; then
  read -rsp "▸ FTP password for $USER: " FTP_PASSWORD; echo
fi
[ -n "$FTP_PASSWORD" ] || { echo "✗ no password given"; exit 1; }

# ── 4. the file set to upload ───────────────────────────────────────────────
cd dist
if [ "$FULL" = "1" ]; then
  mapfile -t FILES < <(find . -type f ! -name '.DS_Store')
  echo "▸ FULL upload: ${#FILES[@]} files (this includes images and is slow)"
else
  mapfile -t FILES < <(find journal sitemap.xml llms.txt index.html -type f ! -name '.DS_Store' 2>/dev/null)
  echo "▸ content upload: ${#FILES[@]} files (articles, journal index, sitemap, home)"
fi

# ── 5. upload over FTPS, creating remote dirs as needed, never deleting ──────
# curl uses one connection per file; --ftp-create-dirs mirrors the tree.
ok=0; fail=0
for f in "${FILES[@]}"; do
  rel="${f#./}"
  if curl -fsS --ssl-reqd --ftp-create-dirs --max-time 120 \
       --user "$USER:$FTP_PASSWORD" -T "$rel" "ftp://$HOST/$rel"; then
    ok=$((ok+1)); printf '.'
  else
    fail=$((fail+1)); printf '\n  ✗ failed: %s\n' "$rel"
  fi
done
echo; echo "▸ uploaded $ok file(s), $fail failed"
unset FTP_PASSWORD
[ "$fail" = "0" ] || { echo "✗ some files failed — see above"; exit 1; }

# ── 6. verify against the live site ─────────────────────────────────────────
echo "▸ verifying live…"
for u in journal/iran-dmc/ journal/discover-iran-iran-travel-advisory/ journal/destinations-kish-island-travel-guide/; do
  code=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 20 "https://boutimar.com/$u" || echo ERR)
  echo "  $code  https://boutimar.com/$u"
done
LIVE=$(curl -fsS --max-time 20 https://boutimar.com/sitemap.xml | grep -c "<loc>" || echo 0)
echo "  live sitemap: $LIVE URLs (built: $LOCAL)"
echo "✓ done"
