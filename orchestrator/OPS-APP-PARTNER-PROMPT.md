# Prompt for base44: the partner portal (paste in one message)

---

Add a partner portal to Albaloo Ops. Keep every existing table, field, permission and
button exactly as it is. Don't add sample data. Don't invent commission rates, prices or
contract terms anywhere in the portal: show only what is stored.

1) PARTNER ENTITY
New entity Partner, all staff edit (owner and manager only):
- partner_id (text, unique; lowercase letters, digits and dashes, 3 to 40 characters;
  check this on save, and never allow it to change after the first lead arrives)
- agency_name, contact_name, email, phone, country, city, website (URL)
- language (en or fa; default en)
- accent (6-digit hex colour without '#'; default 0b6e99)
- status (prospect, active, paused; default prospect)
- notes (long text)
- created_by, created_at

2) PARTNERS ADMIN (owner and manager only)
Add a "Partners" item to the owner and manager menu. It lists partners as cards: agency
name, a status pill (active green, prospect grey, paused amber), country, leads this
month, and leads in total. Leads are counted from Lead rows whose partner_id matches.
"New partner" opens a form for the fields above. It suggests partner_id from the agency
name ("Safar Tour Tabriz" becomes "safar-tour-tabriz") and lets you edit the suggestion.
The partner detail shows:
- the embed code block (section 4)
- that partner's leads
- the users linked to the partner
- an "Invite a login" button. It invites the email with role = partner and
  partner_id = this partner, using the app's own invite.

3) WHAT A PARTNER USER SEES
A user with role partner sees only a "Partner" home and their profile. Hide every other
tab: Today, Review, Social, Sites, Issues, Quotes and Team.
- Data rule: a partner reads only Lead rows where partner_id equals the user's
  partner_id, and only their own Partner row. They can't read ArticleReview, SocialPost,
  Site, Task, Rate, Quote, Metric or HealthItem at all. Enforce this in the entity
  permissions, not only by hiding tabs.
- A partner may change only status and notes on their own leads. Everything else is
  read-only.
- If the partner row is paused, show "Your account is paused. Contact us." and hide the
  leads.

4) PARTNER HOME
- A header with their agency name and three tiles: leads this month, last month, and in
  total. Show 🔥 when any of them is hot.
- "Your enquiry form", a card with three ways to use it:
  (a) Website code. A read-only code box with a Copy button that holds exactly:
      <iframe src="https://cruise24.me/embed/enquiry.html?p={partner_id}&lang={language}&accent={accent}" style="width:100%;border:0;min-height:640px" loading="lazy" title="Cruise enquiry"></iframe>
  (b) Direct link, with a Copy button:
      https://cruise24.me/embed/enquiry.html?p={partner_id}&lang={language}&accent={accent}
      This is for Instagram bios, WhatsApp and Telegram.
  (c) A QR code of the direct link, generated in the browser, with "Download PNG".
  Under it is a language switch (English / فارسی) and a colour picker. Both change only
  the code shown and the preview. They don't save unless the partner presses "Save as my
  default", which writes language and accent on their Partner row.
- "Preview", a live iframe of the direct link at phone width. Under it, the note: "This
  form carries no company name or logo, so it sits on your site as your own form."
- "Your leads", as cards: name, travellers, where, when, date received, the band
  (hot/warm/cold), and status. Tap a card for the full request and the status/notes
  editor. Contact details (email, phone) are shown to the partner for their own leads.
- An empty state for no leads yet: "No enquiries yet. Put the form on your site or share
  the link, and new requests appear here within 15 minutes."

5) LEAD ROWS
Lead already has partner_id from the sync, and it stays sync-owned. On the existing Leads
tab for owner and manager, add a "Partner" filter and show a small agency chip on cards
whose partner_id is set. Look up agency_name from Partner, and fall back to partner_id.

Keep the existing design language: site accent colours, Inter/Vazirmatn, dark mode,
friendly empty states, and RTL when the language is fa.

---

## What fills this (GitHub side)

| Portal part | Filled by | Source |
|---|---|---|
| Partner rows | the team, in the app | nobody else writes Partner |
| Leads with `partner_id` | `tools/ops_leads.py` (every 15 min, heartbeat) | Agent 4 pulls `cruise24.me/api/leads.php`; `api/enquiry.php` stores `partner_id` from the embed's `p=` |
| The form itself | `cruise24-me/embed/enquiry.html` | brand-neutral (compliance `partner_widget_v1`), EN/FA, posts to `api/enquiry.php` |

The partner id reaches the lead untouched: embed `?p=` → POST `partner` → stored
`partner_id` (sanitised `[a-z0-9-]`, ≤40) → Agent 4 record → Lead.partner_id. A lead
whose partner id matches no Partner row is still kept and shown to owner/manager with
the raw id, so a typo in a partner's code never loses an enquiry.
