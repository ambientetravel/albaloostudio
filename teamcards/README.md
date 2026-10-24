# TeamCards — in-house HeyDrop replacement

Digital business cards + QR + wallet passes + contact capture, for every brand
(Boutimar, Ambiente Travel, Cruise24 — add more under **Brands**). Self-hosted on
the DirectAdmin server: PHP 8.1+ and SQLite, no build step, no monthly fee, the
contact list stays on our own server.

## What it does

| | |
|---|---|
| **Cards** | One card per person per brand: photo, title, phone, WhatsApp, email, website, LinkedIn, Instagram, office, bio. Brand colours + logo. Card can be switched off. |
| **QR** | Rendered on every card tile; download as PNG (1200 px) or SVG (vector, for print). **Print** page: an 85×55 mm business card and a table-tent QR for stands. |
| **Public card** `/u/<name>` | One-tap call / WhatsApp / email / website, **Save contact** (vCard with photo), and a *Share your details* form: name, email, phone, company, title, message, consent tick. Honeypot + rate limit (8/hour per network). |
| **Contacts** | Every form submission lands here, tagged with card, owner and brand. Search, filter by brand / person / status / event / date, status (new → contacted → qualified → won/lost), notes, CSV export (Excel-safe, UTF-8). |
| **Quick add** | Type in someone met in person who did not scan. Remembers the last event name, so a fair is fast. |
| **Import** | CSV from HeyDrop or any CRM. Matches common header names, skips duplicates (same email + brand). |
| **Wallet** | Apple Wallet `.pkpass` and Google Wallet "Save" link, QR on the pass. Needs one-time credentials — see `WALLET.md`. |
| **Team** | Admin adds people (temporary password shown once). Members see only their own cards and contacts; admins see all. Owners get an email per new contact (if `mail_from` is set). |

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
