# cruise24.me stays on GoDaddy: what that needs

Decision (Alireza, 28 Sep 2026): cruise24.me stays hosted at GoDaddy.

## Which GoDaddy product matters

| Product | Can it run this site? |
|---|---|
| **Websites + Marketing / Website Builder** (what the domain points to today: 13.248.243.5, 76.223.105.230) | **No.** Pages are edited in GoDaddy's builder; there is no file upload and no PHP. The 1,881-file site and the request form cannot go there. |
| **Web Hosting (cPanel)**, Linux | **Yes, as built.** Apache (`.htaccess` works) and PHP (the form works). Upload the bundle in cPanel → File Manager → `public_html`, extract there. |

If the account has no cPanel hosting, getting it is a purchase: Alireza's decision, not a build step.

## Step 1: find out (read-only), with Claude in Chrome

Paste this into Claude in Chrome, logged in to GoDaddy:

```text
I want to know what GoDaddy products hold the domain cruise24.me. READ ONLY: do not buy, renew, change, connect, disconnect or delete anything, and do not accept any offer or upgrade prompt.

1. Open https://account.godaddy.com/products and list every product in the account: its name, the domain it is attached to, and its expiry date.
2. Tell me whether there is a "Web Hosting" product with cPanel (Linux). If yes: its plan name, the PHP version shown in cPanel (Software → Select PHP Version, or MultiPHP Manager), and the disk space.
3. Tell me what cruise24.me is attached to now (Website Builder / Websites + Marketing, or hosting).
4. Open the DNS page for cruise24.me (https://dcc.godaddy.com/control/portfolio/cruise24.me/settings, then DNS) and copy me every record: type, name, value, TTL. Include MX records, so we do not break email.
5. If you see GoDaddy's Data Processing Addendum or privacy terms in the account, tell me the name of the GoDaddy company that is the contracting party for this account.

Then stop. Change nothing.
```

## Step 2: depends on the answer

- **cPanel hosting exists:** I build the bundle (`python3 build_bundle.py`) and write the upload
  prompt: File Manager upload, extract into `public_html`, create `api/config.php`, check PHP
  version, verify every page against the `.sha256` manifest. The DNS switch away from Website
  Builder replaces the current live site, so that step waits for the legal gaps to be filled
  (`build_bundle.py` refuses until then).
- **Only Website Builder:** the choices are to buy GoDaddy cPanel hosting (and point the domain
  to it), or to host the files elsewhere while the domain stays registered at GoDaddy. The
  DirectAdmin account that already runs cruise24.ir is one such place, if its plan allows another domain.

## For the privacy page once hosting is settled

GoDaddy is a US company, so the privacy page must name the GoDaddy contracting entity and the basis
for the transfer to the US. Take both from GoDaddy's own Data Processing Addendum for this account;
do not write them from memory.
