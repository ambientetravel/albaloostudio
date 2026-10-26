# Prompt for base44: Issues tab + photo editing (paste in one message)

---

Add two things to Albaloo Ops. Keep everything else exactly as it is. Don't add sample data.

PART 1: ISSUES TAB

New entity Task, written by the external sync through the API: key (text, unique),
title, detail (long text), owner (alireza, team, orchestration, strategy-session,
cruise24-me-session), priority (high, medium, low), property (site domain, may be
empty), link (URL), synced_at. Staff edit: status (open, in_progress, done, archived;
default open), notes (long text), updated_by, updated_at.

Visibility: owner and manager see all tasks. Everyone else sees tasks whose property is
empty or in their own properties.

New "Issues" tab with a red badge for open high-priority tasks. Three columns on desktop
(Open / In progress / Done) and a segmented control on phones. Each card shows a
priority colour stripe (high red, medium amber, low grey), the title, an owner chip
("You" when owner is alireza and the user is the owner), the site chip and "Open link".
Tapping a card opens the detail with a status picker and notes. Saving sets updated_by
and updated_at. Archived tasks are hidden behind a "Show archived" toggle.

On the Today tab, add a small "Open issues: N (M high)" tile that opens the Issues tab.

PART 2: EDIT AN ARTICLE'S PHOTO

Add these staff-edit fields to ArticleReview: photo_status (none, pending, removed,
requested, applied, needs_credit), photo_credit (text), photo_licence (text),
photo_rights_confirmed (yes/no), photo_requested_by (text), photo_requested_at
(date-time).

On the article detail page, under the photo, add an "Edit photo" button that opens a
sheet:
1. Paste a link. If it's from commons.wikimedia.org or upload.wikimedia.org, show
   "Credit and licence are filled in automatically from Wikimedia Commons" and hide the
   credit fields. Otherwise require Credit, Licence (for example "own photo",
   "CC BY 4.0", "licensed from supplier X") and the checkbox "We have the right to
   publish this photo". Save is disabled until all three are filled.
2. Upload a photo. Upload a JPG or PNG up to 4 MB with the app's file upload and use
   its public URL as the link. The same credit, licence and rights fields are required.
3. Remove the photo, with a confirm step: "Publish this article without a lead photo?"

On Save:
- for a link or an upload: set image_url to the new URL, photo_status to pending,
  photo_requested_by to the current user's name, photo_requested_at to now;
- for remove: set image_url to empty, photo_status to removed, plus requested_by and
  requested_at.
The card updates immediately.

Badges:
- pending: "Photo change on its way to the article"
- applied: "New photo is in the article" (green)
- requested: "Photo change recorded; a person will finish it" (amber)
- removed: "No lead photo"
- needs_credit: "Add credit and licence" (red). Tapping it reopens the sheet with the
  link prefilled.

If the verdict notes start with "PHOTO IN THE APP IS A SUGGESTION", show a "Suggested
photo" label with an info tip: "The draft has no photo of its own. This is a freely
licensed Wikimedia Commons match. Keep it, or change it."

Only users who can see the article can edit its photo. Viewers and partners can't.

---

## What the sync does with it (GitHub side, every 15 min)

- **Issues:** `orchestrator/ops_tasks.yml` is mirrored into Task. The wording comes from
  GitHub. The status is the team's and is never overwritten. A task removed from the
  file is archived.
- **Photos:** each pending or removed photo is recorded on the article's draft, then
  swapped inside the article file by `tools/photo_swap.py`:
  - Astro sites (boutimar.com, exploreorient.com)
  - boutimar.ir JSON
  - cruise24.ir bundle
  - cruisebaz base44 draft

  The result is applied, or requested with the reason for a person to finish. A photo
  with no credit is refused (needs_credit). Only open drafts are changed.
