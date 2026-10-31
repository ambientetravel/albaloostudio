# Prompt for base44: make Albaloo Ops visual (paste in one message)

---

Redesign Albaloo Ops so it's a pleasure to open on a phone: photo-led, colourful, and
personal for whoever logs in. Keep every existing table, field, permission and button
working exactly as now. Don't add sample data.

DATA CHANGE
- ArticleReview: add field image_url (text). It's filled by the external sync. Never
  invent or fetch images yourself.

LOOK AND FEEL
- Travel-magazine style. Big imagery, generous white space, rounded cards (16px),
  soft shadows, smooth 200ms transitions, skeleton loaders while data loads.
- One accent colour per site, used for that site's chips, card edges and placeholders:
  cruise24.me deep sea blue · cruise24.ir ocean teal · boutimar.com Persian turquoise ·
  boutimar.ir lapis blue · exploreorient.com terracotta · ambientetravel.com olive green ·
  cruisebaz.com coral. Any other site gets slate grey.
- Fonts: Inter for Latin text, Vazirmatn for Farsi. Farsi content is always right-to-left.
- Light and dark mode both look finished. Big touch targets, and a bottom tab bar on phones.

PERSONAL HOME (top of the Review tab)
- A greeting that changes with the time of day: "Good morning, <first name>". Under it,
  a one-line summary for this user's own sites, for example "3 articles to review ·
  2 hot leads · 4 posts waiting".
- When everything is cleared, show a short confetti burst and "All clear for today".

REVIEW TAB
- Each article is a magazine card: image_url as a 16:9 photo with a dark gradient and
  the title over it. When there's no image, use a gradient in the site's colour with
  the site's initial and a subtle pattern (Persian geometric for Farsi, wave lines for
  English). Never a stock photo.
- On the card: a site chip, language flag, word count, house-rules badge (PASS green,
  WARN amber, BLOCK red), and "waiting N days" (red after 3 days).
- Detail page: the full-width photo, then a comfortable reading layout (max 680px,
  18px text, 1.7 line height), with headings and lists rendered from body_markdown.
  The verdict notes sit in a collapsible panel. Publish / Needs edits / Reject stay in
  a sticky bar at the bottom.
- A filter row of site chips (multi-select) and a toggle for Farsi or English.

TODAY TAB
- A hero row of big metric tiles: the number, its label, and a green/red arrow with the
  change from previous.
- Agent cards in a grid: an icon per agent (Scout 🔭, Writer ✍️, Broadcaster 📣,
  Closer 🤝, Auditor 🩺, Cartographer 🗺️, Watcher 👁️, Oracle 🔮, Merge-watch 🔀,
  PR gate 🚦, Dashboard 📊), a coloured status ring (green success, red failure, amber if
  older than 8 days), "last ran N days ago", and a tap to open run_url.
- "Needs you" items as bold cards at the top, then warnings, and "fine" folded away.

LEADS TAB
- Card per lead: a round avatar with the initials of display_name in the site colour,
  a hot 🔥 / warm 🌤️ / cold ❄️ badge, the site chip, and "N hours ago".
- A board view toggle: columns New / Contacted / Quoted / Won / Lost, with drag to
  change status (writes the existing status field).
- Detail: the contact with a Copy button, the draft reply in a message-bubble style with
  Copy, the summary, and the Create quote button.

SOCIAL TAB
- Show each post as it will look on its channel: an Instagram square mock-up (image on
  top, copy below) or a LinkedIn post mock-up. Use the site colour for the account
  avatar.
- When image_url is empty, show a clear amber ribbon: "Needs a photo before it can go
  on Instagram".
- Approve / Reject as large buttons. After Approve, show "Approved: post it by hand.
  Copy text" with a Copy button. Nothing is published automatically.

QUOTES
- Show the quote PDF preview as a card. In the builder, show lines as day-by-day
  timeline steps.

Keep it fast: lazy-load images and cache lists. Every screen needs a friendly empty
state.

---

## After base44 builds it

Tell the "24-hour project strategy" session "visual done". It then:
1. switches `OPS_ARTICLE_IMAGES` on in `ops-sync.yml`, so new article rows carry their photo;
2. runs ops-sync in `images_apply` mode, so the 34 existing rows get theirs.
