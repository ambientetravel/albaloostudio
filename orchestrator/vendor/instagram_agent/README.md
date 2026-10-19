# instagram_agent (vendored)

Four files from Jake Schincariol's MIT-licensed instagram-agent-skill
(github.com/Jakeschincariol/instagram-agent-skill, v1.0.0), copied unchanged on
19 Oct 2026 so Agent 3 can apply the same caption rules in CI that the
`instagram-agent` / `ig-*` Claude Code skills apply on Alireza's Mac.

- `caption.py`: caption lint (visible window before "… more", ≤5 hashtags,
  first line, links, one ask, emoji density)
- `humanize.py` + `slop.json`: strips AI tells (slop words, em dashes, invisible
  characters)
- `detect.py`: five-check human score

Standard library only, no network. Audited before vendoring.

**Never run `humanize.py` on Persian (or any Arabic-script) text.** Its
invisible-character pass deletes U+200C, the zero-width non-joiner Persian
words need. `ig_polish.py` skips the humanizer for Arabic-script captions and
only lints them.
