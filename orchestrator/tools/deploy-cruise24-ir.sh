#!/usr/bin/env bash
# Deploy cruise24.ir from THIS Mac, whose IP is on the FTP allowlist.
#
# Why this exists: cruise24.ir is on the same Netafraz/DirectAdmin host as
# boutimar.com, which firewalls FTP by IP. GitHub's runners have ever-changing
# IPs that cannot be allowlisted, and cruise24.ir has no git repo, so there is no
# CI to push from anyway. This Mac's IP can be allowlisted, so the build+upload
# runs from here. It NEVER stores the password: it prompts, hidden, each run.
#
# ⚠️ LIVE TREE: /Users/alimozzy/cruise24.ir  (tools/build.py, public_html/).
# There is a SECOND, DEAD tree at claude websitebuilder/cruise24-ir (_build.py,
# Aug 27) — do NOT point this at it: its pages are ~3 weeks stale and 20-40%
# smaller, and deploying them would revert canonical tags, OpenGraph, long-form
# content, FAQ schema and the corrected visa verdicts. The refuse-if-shrinking
# pre-flight below is the backstop for exactly that mistake.
#
# Usage:
#   bash orchestrator/tools/deploy-cruise24-ir.sh          # blog + storefront + sitemap + offer
#   bash orchestrator/tools/deploy-cruise24-ir.sh --full   # every file in public_html/
#
# FTP host/user come from env — no cruise24.ir credential is hard-coded, and the
# script REFUSES to run until Alireza supplies them:
#   export C24_FTP_HOST="server22gr.axspace.com"   # confirm in DirectAdmin
#   export C24_FTP_USER="deploy@cruise24.ir"       # confirm in DirectAdmin
set -euo pipefail

HOST="${C24_FTP_HOST:-}"
USER="${C24_FTP_USER:-}"
BUILD_DIR="/Users/alimozzy/cruise24.ir"           # the LIVE tree, not the dead one
OUT="public_html"                                  # tree A builds here, not public/
BASE_URL="https://cruise24.ir"
SHRINK_PCT=20                                      # abort if a file is >20% smaller than live
FULL=0; [ "${1:-}" = "--full" ] && FULL=1

if [ -z "$HOST" ] || [ -z "$USER" ]; then
  echo "✗ set C24_FTP_HOST and C24_FTP_USER first (see the header). No credential is guessed."
  exit 2
fi
[ -d "$BUILD_DIR" ] || { echo "✗ live tree not found at $BUILD_DIR"; exit 2; }

echo "▸ cruise24.ir deploy — from $(curl -fsS --max-time 10 https://api.ipify.org || echo '?') (must be on the FTP allowlist)"

# ── 1. build (tree A: python3 tools/build.py, idempotent, refreshes its feed) ─
cd "$BUILD_DIR"
echo "▸ building (python3 tools/build.py → $OUT/)…"
python3 tools/build.py
test -f "$OUT/sitemap.xml" || { echo "✗ build produced no $OUT/sitemap.xml"; exit 1; }
LOCAL=$(grep -c "<loc>" "$OUT/sitemap.xml" || echo 0)
echo "  built OK — sitemap has $LOCAL URLs"

# ── 2. the file set to upload ─────────────────────────────────────────────────
cd "$OUT"
if [ "$FULL" = "1" ]; then
  mapfile -t FILES < <(find . -type f ! -name '.DS_Store')
  echo "▸ FULL upload: ${#FILES[@]} files"
else
  mapfile -t FILES < <(find blog blog.html *.html sitemap.xml offer.json llms.txt \
                            -type f ! -name '.DS_Store' 2>/dev/null | sort -u)
  echo "▸ content upload: ${#FILES[@]} files (blog, storefront, sitemap, offer.json, llms.txt)"
fi
[ "${#FILES[@]}" -gt 0 ] || { echo "✗ nothing to upload — did the build run?"; exit 1; }

# ── 3. REFUSE-IF-SHRINKING pre-flight — the stale-tree backstop ────────────────
# Before uploading anything, compare each file to what is live. A file that is
# more than SHRINK_PCT% smaller than the live one is almost certainly a stale
# build about to overwrite good content — abort the WHOLE run and show the sizes.
# A live size of 0 means the page is new (nothing to shrink), so it is allowed.
echo "▸ pre-flight: checking no file shrinks more than ${SHRINK_PCT}% vs live…"
shrunk=0
for f in "${FILES[@]}"; do
  rel="${f#./}"
  local_sz=$(wc -c < "$rel" | tr -d ' ')
  live_sz=$(curl -fsS -o /dev/null -w '%{size_download}' --max-time 20 "$BASE_URL/$rel" 2>/dev/null || echo 0)
  if [ "$live_sz" -gt 0 ] && [ "$local_sz" -lt $(( live_sz * (100 - SHRINK_PCT) / 100 )) ]; then
    printf '  ✗ %s would shrink: %sb local vs %sb live\n' "$rel" "$local_sz" "$live_sz"
    shrunk=$((shrunk+1))
  fi
done
if [ "$shrunk" -gt 0 ]; then
  echo "✗ ABORT: $shrunk file(s) would shrink >${SHRINK_PCT}% — this looks like the STALE tree."
  echo "  Confirm BUILD_DIR is the live tree ($BUILD_DIR) and the build ran, then retry."
  exit 1
fi
echo "  pre-flight OK — no file shrinks beyond the threshold"

# ── 4. the password, never stored ─────────────────────────────────────────────
if [ -z "${FTP_PASSWORD:-}" ]; then
  read -rsp "▸ FTP password for $USER: " FTP_PASSWORD; echo
fi
[ -n "$FTP_PASSWORD" ] || { echo "✗ no password given"; exit 1; }

# ── 5. upload over FTPS, creating remote dirs as needed, never deleting ───────
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

# ── 6. verify against the live site ───────────────────────────────────────────
echo "▸ verifying live…"
LIVE=$(curl -fsS --max-time 20 "$BASE_URL/sitemap.xml" | grep -c "<loc>" || echo 0)
echo "  live sitemap: $LIVE URLs (built: $LOCAL)"
OFFER=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 20 "$BASE_URL/offer.json" || echo ERR)
echo "  offer.json: $OFFER"
echo "✓ done"
