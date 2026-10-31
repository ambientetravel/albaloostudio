# Prompt for base44: Issues, photo editing, Sites and the pipeline overview (paste in one message)

---

Add four things to Albaloo Ops. Keep every existing table, field, permission and button
exactly as it is. Don't add sample data. Every record below is written by an external
sync through the API unless marked "staff edit".

1) ISSUES TAB
New entity Task: key (text, unique), title, detail (long text), owner (alireza, team,
orchestration, strategy-session, cruise24-me-session), priority (high, medium, low),
property (site domain, may be empty), link (URL), synced_at. Staff edit: status (open,
in_progress, done, archived; default open), notes (long text), updated_by, updated_at.
Visibility: owner and manager see all. Others see tasks whose property is empty or in
their properties.
New "Issues" tab with a red badge counting open high-priority tasks. Columns
Open / In progress / Done on desktop, a segmented control on phones. Each card: a
priority stripe (high red, medium amber, low grey), the title, an owner chip ("You" when
owner is alireza and the user is the owner), the site chip, and "Open link". The detail
view has a status picker and notes; saving sets updated_by and updated_at. Archived
tasks sit behind a "Show archived" toggle.

2) EDIT AN ARTICLE'S PHOTO
Add staff-edit fields to ArticleReview: photo_status (none, pending, removed, requested,
applied, needs_credit), photo_credit, photo_licence, photo_rights_confirmed (yes/no),
photo_requested_by, photo_requested_at (date-time).
On the article detail page, under the photo, an "Edit photo" button opens a sheet:
(a) Paste a link. For commons.wikimedia.org or upload.wikimedia.org links, say "Credit
and licence are filled in automatically from Wikimedia Commons" and hide the credit
fields. Otherwise require Credit, Licence and the checkbox "We have the right to publish
this photo".
(b) Upload a JPG or PNG up to 4 MB with the app's file upload; use its public URL. The
same three fields are required.
(c) Remove the photo, after the confirm "Publish this article without a lead photo?".
On Save: set image_url to the new URL (or empty for remove), photo_status to pending (or
removed), photo_requested_by to the user's name and photo_requested_at to now. The card
updates immediately.
Badges:
- pending: "Photo change on its way to the article"
- applied: "New photo is in the article" (green)
- requested: "Recorded; a person will finish it" (amber)
- removed: "No lead photo"
- needs_credit: "Add credit and licence" (red; tapping reopens the sheet with the link
  prefilled)
If verdict_notes start with "PHOTO IN THE APP IS A SUGGESTION", show a "Suggested photo"
label with the tip: "The draft has no photo of its own. This is a freely licensed
Wikimedia Commons match. Keep it or change it."
Only users who can see the article may edit its photo. Viewers and partners can't.

3) SITES TAB ("Can each site receive an article?")
New entity Site: domain (unique), brand, language, market, hosting, adapter,
publishing, can_publish (yes/no), lead_source (yes/no), channels, drafts_waiting
(number), published_total (number), last_draft_at, leads_total (number), leads_hot
(number), pages_in_sitemap (number), pages_shown_by_google (number), coverage_pct
(number), synced_at. Visibility follows the user's properties (owner and manager see
all).
New "Sites" tab. On desktop, a table with columns Site, Brand, Adapter (monospace),
Publishing (a green pill when can_publish = yes, grey "no adapter", amber "on hold"),
Drafts waiting, Published, Leads (with 🔥 for hot), and Google coverage (a thin bar plus
"shown / in sitemap"). On phones, one card per site with the same facts. Tapping a site
opens its detail: the facts above, then three lists from existing data filtered to that
domain: ArticleReview waiting, Lead, SocialPost.

4) PIPELINE OVERVIEW (top of the Today tab, above the existing tiles)
- A funnel built from these Metric rows (by name), each step a bar with its number:
  "Gap candidates found (last cycle)" → "Already briefed, skipped" →
  "Briefs (last cycle)" → "Articles drafted (last cycle)" → "Article PRs waiting".
- A cost card: "Model spend, USD (last cycle)" with its change from previous.
- Health tiles for "Writer failures", "Dead-lettered", "Social posts without a photo";
  red when above 0.
- A sites summary line from Site: "N of M sites can receive an article · X drafts
  waiting · Y leads (Z hot)". Tapping it opens the Sites tab.
- An "Open issues: N (M high)" tile that opens the Issues tab.

Keep the existing design language (site accent colours, Inter/Vazirmatn, dark mode,
friendly empty states).

---

## What fills these (GitHub side, every 15 minutes via the heartbeat)

| App part | Filled by | Source |
|---|---|---|
| Issues | `tools/ops_tasks.py` | `orchestrator/ops_tasks.yml`: GitHub owns the wording, the team owns the status |
| Photo editing | `ops_sync.relay_photo_requests` + `tools/photo_swap.py` | records the change on the draft, then swaps it inside the article (Astro, boutimar.ir JSON, cruise24.ir bundle, cruisebaz base44) |
| Sites | `tools/ops_sites.py` | `sites.yml` + the Notion review board + Leads + the weekly index-coverage report |
| Pipeline funnel | `tools/ops_today.py` | `reports/health-latest.json` |
