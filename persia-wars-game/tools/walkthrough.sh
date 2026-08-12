#!/bin/bash
# walkthrough — make a screen recording readable.
#
# Claude cannot watch a video or hear it. This turns one into the two things it
# CAN read: the distinct screens as PNGs, and the spoken commentary as a
# timestamped transcript. Both are stamped in seconds, so a line of narration
# lines up with the frame that was on screen when it was said.
#
#   tools/walkthrough.sh <recording.mov> [outdir] [everySec] [locale]
#
# Then point Claude at the output folder.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
video="${1:?usage: walkthrough.sh <recording.mov> [outdir] [everySec=1.5] [locale=en-US]}"
outdir="${2:-$(dirname "$video")/$(basename "${video%.*}")-walkthrough}"
every="${3:-1.5}"
locale="${4:-en-US}"

# Build the two helpers once; they are ~1s per run after that, vs ~35s
# re-interpreting the source every time.
for tool in framegrab narrate; do
  if [ ! -x "$here/$tool" ] || [ "$here/$tool.swift" -nt "$here/$tool" ]; then
    echo "building $tool…" >&2
    swiftc -O "$here/$tool.swift" -o "$here/$tool"
  fi
done

mkdir -p "$outdir"

echo "── frames ──"
"$here/framegrab" "$video" "$outdir/frames" "$every" 900 6

echo
echo "── narration ──"
if "$here/narrate" "$video" "$locale" > "$outdir/narration.txt" 2>"$outdir/.narrate.log"; then
  if [ -s "$outdir/narration.txt" ]; then
    cat "$outdir/narration.txt"
  else
    echo "(no speech detected — the recording may be silent)"
  fi
else
  echo "(could not transcribe — see $outdir/.narrate.log)"
  sed 's/^/  /' "$outdir/.narrate.log" | head -3
fi

echo
echo "Done. Point Claude at: $outdir"
echo "  frames/        one PNG per distinct screen, named with its timestamp"
echo "  narration.txt  what was said, stamped to the same clock"
