# TeamCards on cards.ambientetravel.com

## Why a subdomain, not base44

ambientetravel.com is a base44 single-page app. base44 serves its own JavaScript
front end and data entities — it does not run PHP or SQLite, which TeamCards is.
So TeamCards runs on the DirectAdmin host and only its **address** lives under
ambientetravel.com:

    ambientetravel.com          → base44 (unchanged, apex A 216.24.57.1)
    cards.ambientetravel.com    → DirectAdmin host running TeamCards

Nothing on the base44 site changes. Card links read
`https://cards.ambientetravel.com/u/<name>`, so the QR codes carry the Ambiente
domain for every sub-brand.

## 1. DNS (zone is on Wix nameservers)

Wix → Domains → ambientetravel.com → Manage DNS records → **A (Host)** → Add record:

| Host name | Points to | TTL |
|---|---|---|
| `cards` | *IP of the DirectAdmin server* | 1 hour |

Add only this one record. Do not touch `@`, `www`, MX or the base44 records.
The IP is the one DirectAdmin shows top-right (or `boutimar.com`'s A record if
TeamCards shares that server).

## 2. DirectAdmin

1. Domain Setup → **Add another domain** → `cards.ambientetravel.com`
   (a separate domain, not a subdomain of boutimar.com). PHP 8.1+ on.
2. SSL Certificates → Let's Encrypt for `cards.ambientetravel.com`
   (after DNS resolves — check with `nslookup cards.ambientetravel.com`).
3. File Manager → `domains/cards.ambientetravel.com/public_html/` → upload
   `teamcards-YYYY-MM-DD.zip` → **Extract here** (paths are docroot-relative).
4. Copy `config.sample.php` → `config.php`. `base_url` is already
   `https://cards.ambientetravel.com`; fill `setup_key`, `ip_salt`,
   `mail_from` (`cards@ambientetravel.com` needs that mailbox/sender allowed on
   this server — otherwise use an address on the server's own domain).
   Set `data_dir` to `/home/USER/teamcards-data` (outside public_html).

## 3. Check

    curl -sI https://cards.ambientetravel.com/index.php?p=login   # 200
    curl -sI https://cards.ambientetravel.com/config.php          # 403
    curl -sI https://cards.ambientetravel.com/data/teamcards.sqlite  # 403
    curl -sI https://ambientetravel.com/                          # unchanged, base44

Then open https://cards.ambientetravel.com/ → setup → Owner account → Owner panel.
