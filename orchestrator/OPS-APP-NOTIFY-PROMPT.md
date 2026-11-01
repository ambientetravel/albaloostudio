# Paste into the base44 builder (Albaloo Ops app) — team notifications by field

Paste everything below the line into the base44 chat for app `albaloo-ops-core`. Do NOT change any existing entity, its fields, or any access rules. Add only what is described.

---

Add a notification system to the Albaloo Ops app. The pipeline (an outside job) will write `Notification` rows; the app shows each person the ones for their field and, if they chose it, e-mails them.

**1. Two new entities.**

`Notification` (the pipeline writes these; people only read them and mark them read):
- `key` text (unique — never create two with the same key)
- `kind` text
- `field` text — one of: persian_content, english_content, sales, social, technical, owner
- `level` text — info, action, warn, critical
- `property` text
- `title` text
- `body` text
- `link` text
- `created_at` text (ISO date-time)
- `read_by` list of text (e-mails of people who have marked it read)
- `emailed` list of text (e-mails already sent this notification — so nobody is e-mailed twice)

`TeamMember` (Alireza fills this in):
- `name` text
- `email` text
- `fields` list of text — which of the six fields this person covers (multi-select with those exact values)
- `delivery` text — `bell` (default) or `bell_and_email`
- `active` yes/no (default yes)

Only the app owner can create, edit or delete `TeamMember` rows. Signed-in team members can read `Notification` rows and add their own e-mail to `read_by`; they cannot edit anything else. Notification and TeamMember must NOT be readable without signing in.

**2. A bell in the header of every screen.**
- Shows the number of unread notifications for the signed-in person: unread = their e-mail is not in `read_by`, and `field` is one of the fields on their TeamMember row. The owner (field `owner`) sees `owner` notifications plus everything else.
- Clicking it opens a panel, newest first, grouped by field, each with level colour (critical red, action amber, warn yellow, info grey), title, body, and a "Open" button that goes to `link` when there is one. A "Mark all read" button.
- A "My notifications" filter on the full list page by field and level.

**3. A Team page (owner only).**
A simple table of TeamMember rows with add / edit / remove, the six fields as checkboxes per person, and a delivery choice per person. Add a short line under it: "People are told only about the fields ticked here."

**4. E-mail (build it, but leave it OFF).**
Add an owner-only switch on the Team page, "Send e-mail notifications", default OFF. When it is on, for each new Notification, send ONE e-mail to every active TeamMember whose `delivery` is `bell_and_email` and whose `fields` include the notification's field (the owner gets owner notifications), using the app's built-in e-mail. Subject = the notification title, body = `body` plus the `link`. Record the recipient in `emailed` so nobody gets it twice. Group notifications that arrive in the same minute into one e-mail per person. Do not send anything while the switch is off.
