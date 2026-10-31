# Prompt for base44: let the team change an article's photo (paste in one message)

---

Let the team change an article's photo on the Review detail page, the same way they
already give text feedback. Keep everything else as it is. Don't add sample data.

DATA: add these staff-edit fields to ArticleReview:
photo_status (none, pending, removed, requested, needs_credit), photo_credit (text),
photo_licence (text), photo_rights_confirmed (yes/no), photo_requested_by (text),
photo_requested_at (date-time).

ON THE ARTICLE DETAIL PAGE, under the photo, add an "Edit photo" button that opens a
sheet with three choices:

1. Paste a link. A URL field. If the link is from commons.wikimedia.org or
   upload.wikimedia.org, show "Credit and licence are filled in automatically from
   Wikimedia Commons" and hide the credit fields. For any other link, require Credit
   (who took it), Licence (for example "own photo", "CC BY 4.0", "licensed from
   supplier X"), and a checkbox "We have the right to publish this photo". Save is
   disabled until all three are filled.
2. Upload a photo. Upload a JPG or PNG up to 10 MB with the app's file upload, then use
   the uploaded file's public URL as the link. The same credit, licence and rights
   fields are required.
3. Remove the photo, with a confirm step: "Publish this article without a lead photo?"

On Save:
- for a link or an upload: set image_url to the new URL, photo_status to pending,
  photo_requested_by to the current user's name, photo_requested_at to now;
- for remove: set image_url to empty, photo_status to removed, plus requested_by and
  requested_at as above.
The card updates immediately.

BADGES on the card and the detail page:
- pending: "Photo change sent to the writer"
- requested: "Photo change recorded on the draft"
- removed: "No lead photo"
- needs_credit: "Add credit and licence" in red. Tapping it reopens the sheet with the
  link prefilled.

If the verdict notes start with "PHOTO IN THE APP IS A SUGGESTION", show a small
"Suggested photo" label on the photo with an info tip: "The draft has no photo of its
own. This one is a freely licensed Wikimedia Commons match. Keep it by approving, or
change it."

Only users who can see the article (their own sites, or owner and manager) can edit
its photo. Viewers and partners can't.

---

## What happens after Save

The ops-sync job (every 15 minutes, via the heartbeat) posts one comment on the
article's draft: the new photo, credit and licence, or "Photo removed". It then sets
photo_status to requested. A Commons link gets its real creator and licence from
Commons. Any other photo without credit, licence and rights confirmation is refused
and set to needs_credit. The sync never overwrites a photo the team chose.

**Not yet automatic:** swapping the photo file inside the article itself. Each site
stores it differently (Astro front matter, boutimar.ir JSON, the cruise24.ir bundle,
base44 records). Until those adapters exist, the writer applies the request recorded
on the draft.
