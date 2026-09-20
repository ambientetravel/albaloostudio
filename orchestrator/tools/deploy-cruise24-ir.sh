#!/usr/bin/env bash
# Deploy cruise24.ir from THIS Mac, whose IP is on the FTP allowlist.
#
# Why this exists: cruise24.ir is on the same Netafraz/DirectAdmin host as
# boutimar.com, which firewalls FTP by IP. GitHub's runners have ever-changing
# IPs that cannot be allowlisted, and cruise24.ir has NO git repo, so there is no
# CI to push from anyway. This Mac's IP can be allowlisted, so the build+upload
# runs from here — the exact model of deploy-boutimar-com.sh. It NEVER stores the
# password: it prompts, hidden, each run.
#
# Usage:
#   bash orchestrator/tools/deploy-cruise24-ir.sh          # blog + storefront + sitemap
#   bash orchestrator/tools/deploy-cruise24-ir.sh --full   # every file in public/
#
# PREREQUISITE (cruise24.ir session owns this): _build.py must render pipeline
# articles into public/blog/<slug>.html and list them in blog.html. Until that
# render step exists, this ships the storefront it already builds — it does not
# invent article pages.
#
# FTP host/user are read from env so no cruise24.ir credential is hard-coded here.
# Set them once (cruise24.ir is the same host as boutimar.com, so HOST is very
# likely the same; USER is cruise24.ir's own FTP account):
#   export C24_FTP_HOST="server22gr.axspace.com"   # confirm in DirectAdmin
#   export C24_FTP_USER="deploy@cruise24.ir"       # confirm in DirectAdmin
set -euo pipefail

HOST="${C24_FTP_HOST:-}"
USER="${C24_FTP_USER:-}"
BUILD_DIR="$(cd "$(dirname "$0")/../../cruise24-ir" && pwd)"
FULL=0; [ "${1:-}" = "--full" ] && FULL=1

if [ -z "$HOST" ] || [ -z "$USER" ]; then
  echo "✗ set C24_FTP_HOST and C24_FTP_USER first (see the header of this script)."
  echo "  cruise24.ir shares boutimar.com's host, so HOST is likely server22gr.axspace.com;"
  echo "  USER is cruise24.ir's own DirectAdmin FTP account."
  exit 2
fi

echo "▸ cruise24.ir deploy — from $(curl -fsS --max-time 10 https://api.ipify.org || echo '?') (must be on the FTP allowlist)"

# ── 1. build (Python, not npm — cruise24.ir is a _build.py static site) ───────
cd "$BUILD_DIR"
echo "▸ building (python3 _build.py → public/)…"
python3 _build.py
test -f public/sitemap.xml || { echo "✗ build produced no public/sitemap.xml"; exit 1; }
LOCAL=$(grep -c "<loc>" public/sitemap.xml || echo 0)
echo "  built OK — sitemap has $LOCAL URLs"

# ── 2. the password, never stored ─────────────────────────────────────────────
if [ -z "${FTP_PASSWORD:-}" ]; then
  read -rsp "▸ FTP password for $USER: " FTP_PASSWORD; echo
fi
[ -n "$FTP_PASSWORD" ] || { echo "✗ no password given"; exit 1; }

# ── 3. the file set to upload (content, or everything with --full) ────────────
cd public
if [ "$FULL" = "1" ]; then
  mapfile -t FILES < <(find . -type f ! -name '.DS_Store')
  echo "▸ FULL upload: ${#FILES[@]} files"
else
  # blog/ (the pipeline articles once _build.py renders them), the blog index,
  # the storefront HTML, sitemap and offer.json — never images or api/.
  mapfile -t FILES < <(find blog blog.html *.html sitemap.xml offer.json \
                            -type f ! -name '.DS_Store' 2>/dev/null | sort -u)
  echo "▸ content upload: ${#FILES[@]} files (blog, storefront, sitemap, offer.json)"
fi
[ "${#FILES[@]}" -gt 0 ] || { echo "✗ nothing to upload — did the build run?"; exit 1; }

# ── 4. upload over FTPS, creating remote dirs as needed, never deleting ───────
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

# ── 5. verify against the live site ───────────────────────────────────────────
echo "▸ verifying live…"
LIVE=$(curl -fsS --max-time 20 https://cruise24.ir/sitemap.xml | grep -c "<loc>" || echo 0)
echo "  live sitemap: $LIVE URLs (built: $LOCAL)"
OFFER=$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 20 https://cruise24.ir/offer.json || echo ERR)
echo "  offer.json: $OFFER"
echo "✓ done"
