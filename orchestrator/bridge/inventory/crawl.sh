#!/usr/bin/env bash
# Read-only site-inventory crawler for the Gemini bridge seed.
# Fetches each property's sitemap(s) -> URL list; caches pages for coverage parse.
set -uo pipefail
UA="Mozilla/5.0 (Macintosh) Chrome/128 Safari/537.36"
OUT="$(cd "$(dirname "$0")" && pwd)"
DOMAINS=(boutimar.com boutimar.ir cruise24.ir cruise24.me cruisebaz.com exploreorient.com ambientetravel.com albaloostudio.com)

fetch(){ curl -sSL --max-time 25 -A "$UA" "$1" 2>/dev/null; }

for d in "${DOMAINS[@]}"; do
  mkdir -p "$OUT/$d"
  # collect candidate sitemap locations (index + robots-declared)
  { echo "https://$d/sitemap.xml"; echo "https://$d/sitemap_index.xml"; echo "https://$d/sitemap-index.xml";
    fetch "https://$d/robots.txt" | grep -iE '^sitemap:' | sed -E 's/^[Ss]itemap:[[:space:]]*//' ; } \
    | tr -d '\r' | sort -u > "$OUT/$d/_sm_seeds.txt"

  : > "$OUT/$d/_urls.txt"
  # expand: each seed may be an index (contains <sitemap>) or a urlset (<url>)
  while read -r sm; do
    [ -z "$sm" ] && continue
    body="$(fetch "$sm")"
    [ -z "$body" ] && continue
    # child sitemaps from an index
    childs=$(printf '%s' "$body" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g' | grep -iE 'sitemap.*\.xml' )
    if [ -n "$childs" ]; then
      while read -r c; do
        [ -z "$c" ] && continue
        fetch "$c" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g' >> "$OUT/$d/_urls.txt"
      done <<< "$childs"
    fi
    # direct page locs (non-sitemap)
    printf '%s' "$body" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g' | grep -viE 'sitemap.*\.xml' >> "$OUT/$d/_urls.txt"
  done < "$OUT/$d/_sm_seeds.txt"

  sort -u "$OUT/$d/_urls.txt" -o "$OUT/$d/_urls.txt"
  n=$(wc -l < "$OUT/$d/_urls.txt" | tr -d ' ')
  echo "$d: $n sitemap URLs"
done
