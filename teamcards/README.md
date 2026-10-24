# TeamCards — in-house HeyDrop replacement

Digital business cards + QR + wallet passes + contact capture, for every brand
(Boutimar, Ambiente Travel, Cruise24 — add more under **Brands**). Self-hosted on
the DirectAdmin server: PHP 8.1+ and SQLite, no build step, no monthly fee, the
contact list stays on our own server.

## What it does

Built to match HeyDrop Teams (mapped screen by screen on 24 Oct 2026) and go past it where a fair-going sales team needs more.

| | |
|---|---|
| **Cards** | One card per person per brand. Personal details, company details (blank = brand default), photo, bio. Search and brand filter. |
| **Link blocks** | Ordered, drag-and-drop buttons: Exchange contacts, Save contact, Link, Email, Call, SMS, WhatsApp, Navigate, Book a meeting, Pay, Text (heading/subheading/body), Social icons (16 networks incl. Telegram, WhatsApp, Aparat, Tripadvisor). Show/hide each. |
| **Designs** | 4 card templates (Classic, Minimal, Photo hero, Dark) and 3 wallet colours (brand, dark grey, white), per card or brand default. |
| **Card URL** | Custom link name with **Check availability**; warns that changing it breaks printed QR codes. |
| **QR** | PNG (1200 px) / SVG download, printable 85×55 mm card + table tent. |
| **Public card** `/u/<name>` | Blocks in order, company footer, **Share** sheet (QR, copy link, WhatsApp, SMS, email, Telegram, LinkedIn), **Let's connect** sheet: name, email *or* phone, + company / title / note, consent. Can pop up by itself on load. Honeypot + rate limit. |
| **Contacts** | Every capture tagged with card, owner, brand, source (Card form / Quick add / AI scanner / Import). Search, filters, status pipeline, notes, event tags, Excel-safe CSV export, CSV import. |
| **Quick add + AI scanner** | Photograph a business card or badge → Claude reads it → you check and save. Remembers the event and card between entries. |
| **Team** | Invite by email or copyable link (7-day, single use), roles, Invited/Active status, resend/cancel, password-reset link. Members see only their own cards and contacts. |
| **Bulk create** | Many rows or a CSV (name, email, mobile, title, admin) → users + cards on one brand, invites included. |
| **Brands** | Colours, logo, tagline, company details, default design. **Save for new cards** or **Save for all cards** (resets every card of the brand to the brand). |
| **CRM hand-off** | Each new contact is POSTed to a webhook (Zapier/Make catch hook → HubSpot, Pipedrive, Sheets…), HMAC-signed. |
| **Wallet** | Apple `.pkpass` and Google Wallet save link, QR on the pass, in the chosen colour. Credentials: `WALLET.md`. |
| **Settings** | Admin page showing which of the above are switched on in `config.php`, plus a webhook test. |

Ahead of HeyDrop: multiple brands in one install, lead status / notes / events, AI scanner in the browser (theirs is mobile-app only), WhatsApp/Telegram-first sharing, any CRM via webhook, self-hosted data. Not copied: their 16 templates (4 here), the native mobile app.

### Webhook payload

    POST <webhook_url>
    X-Albaloo-Timestamp: 1767225600
    X-Albaloo-Signature: sha256=<HMAC-SHA256(webhook_secret, "<timestamp>.<body>")>
    {"event":"contact.created","contact":{"id":12,"name":"…","email":"…","phone":"…","company":"…","job_title":"…",
     "note":"…","event":"ATM Dubai","source":"qr|manual|scan|import","consent":1,"created_at":"…",
     "brand":"Boutimar","brand_domain":"boutimar.com","owner":"…","owner_email":"…","card":"slug"}}

## Files

    index.php      dashboard (login, cards, contacts, quick add, import, team, brands, account)
    card.php       public card + share-your-details form
    vcf.php        Save contact
    wallet.php     Apple / Google Wallet
    export.php     CSV
    lib.php        DB schema, auth, helpers (SQLite, auto-migrates)
    tools/heydrop-capture.js   Chrome console script to map HeyDrop (not deployed)
    build_bundle.py            → dist/teamcards-YYYY-MM-DD.zip

## Run locally

    cp config.sample.php config.php   # set setup_key, base_url=http://127.0.0.1:8099, pretty_urls=false
    php -S 127.0.0.1:8099
    open http://127.0.0.1:8099        # → setup page, enter the setup_key, create the admin

## Deploy (DirectAdmin)

Assumed address: **cards.boutimar.com** (internal tool; one install serves all
brands, each card shows its own brand). Any subdomain works — set `base_url` to
it **before printing any QR**, because printed codes point there forever.

1. DirectAdmin → Subdomain Management → create `cards` under boutimar.com.
   Let's Encrypt SSL on it.
2. File Manager → `domains/boutimar.com/public_html/cards/` (or the subdomain's
   own docroot if the panel created one) → upload `dist/teamcards-*.zip`,
   **extract there**. Paths in the zip are docroot-relative, no `public_html/` prefix.
3. In that folder copy `config.sample.php` → `config.php`, fill `base_url`,
   `setup_key` (12+ random chars), `ip_salt`, `mail_from` (e.g. `cards@boutimar.com`).
   Better: set `data_dir` to a folder outside public_html.
4. Make `data/` and `uploads/` writable by PHP (755 is normally enough on DirectAdmin).
5. Open `https://cards.boutimar.com/` → setup → create the admin → Brands
   (logos, colours) → Team → Cards.

Check after deploy:

    curl -sI https://cards.boutimar.com/config.php        # 403
    curl -sI https://cards.boutimar.com/data/teamcards.sqlite  # 403
    curl -sI https://cards.boutimar.com/u/<a-card-slug>   # 200

## Getting the most out of HeyDrop first

`tools/heydrop-capture.js` — paste into Chrome DevTools on heydrop.app while
logged in, click through every screen, run `HDX.download()`. It saves a JSON
map of screens, form fields, buttons and API shapes. Contact values are
replaced by their type (`string:email`), tokens/passwords/headers are never
recorded. Send the file back and anything HeyDrop does that TeamCards does not
gets added. Separately, export the contacts from HeyDrop as CSV and load them
under **Contacts → Import CSV**.
