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

## Found on 28 Sep (Claude in Chrome, read-only)

- Account products: domain cruise24.me (auto-renews 12 Nov 2026, top-tier protection), Websites + Marketing
  "Cruise 24" (cruise24.me) and "Middle East Cruise 24" (middleeastcruise24.godaddysites.com), and
  **Web Hosting, Economy ("Başlangıç Düzeyi"), cPanel, Linux, PHP 8.3, Europe data centre,
  IP 92.205.251.216, cPanel user ekrd2r2976p9**, primary domain cruise24.me.
- Public DNS: cruise24.me and www point to 13.248.243.5 / 76.223.105.230 (Website Builder). So the
  live site is the builder site; the cPanel hosting serves nothing public yet.
- Not yet read: the DNS record list (MX included), disk space, public_html contents, the DPA entity.

## Step 2: staging on the cPanel hosting (live site untouched)

The bundle goes into `public_html`, and a subdomain `staging.cruise24.me` shares that folder so the
site and the request form can be tested on the real server. cruise24.me and www keep pointing at
Website Builder until the legal gaps are filled. `.htaccess` sends `X-Robots-Tag: noindex` for
staging.*. Bundle: `python3 build_bundle.py --draft --parts-mb 28` → three standalone zips of ≤ 28 MiB (the chat's file limit is 30 MiB), 1,882 files in total; verified equal to the single zip.

Prompt for Claude in Chrome (logged in to GoDaddy and cPanel):

```text
You are putting a new version of the Cruise24 website on our GoDaddy cPanel hosting, for testing at staging.cruise24.me. The live site at cruise24.me must NOT change.

Account facts: Web Hosting Economy, cPanel user ekrd2r2976p9, server IP 92.205.251.216, primary domain cruise24.me.

HARD RULES
- Never change, delete or add the DNS records for "@" (cruise24.me), "www", MX, TXT or nameservers. The only DNS change allowed is ADDING one A record named "staging" (Part E).
- Do not buy, renew, upgrade or accept any offer. Do not disconnect the Websites + Marketing site.
- Never delete anything in public_html unless this prompt says so, and never before the backup in Part B exists.
- If GoDaddy asks me to log in, stop and wait for me. When a file-upload dialog opens, stop and let me pick the file.
- If anything is different from what this prompt expects, stop, describe it, and ask me.

PART A — READ FIRST (change nothing)
1. GoDaddy DNS for cruise24.me: copy me EVERY record (type, name, value, TTL), MX and TXT included, and the nameservers. If the nameservers are not GoDaddy's (domaincontrol.com), stop after reporting.
2. cPanel: tell me the disk usage and the disk limit.
3. cPanel File Manager: open public_html (turn on "Show Hidden Files" in Settings) and list everything in it, with sizes.

PART B — BACKUP (only if public_html contains anything other than cgi-bin and .well-known)
4. Select everything in public_html, Compress as Zip Archive named public_html-backup-20260928.zip, then Move that zip to the home folder (/home/ekrd2r2976p9/). Confirm it is there and tell me its size.

PART C — UPLOAD AND EXTRACT
5. The site comes in THREE zip files whose names end in -part1of3.zip, -part2of3.zip and -part3of3.zip (about 28, 28 and 13 MB). In public_html, click Upload. Stop and let me choose the three files. Wait until every upload shows 100 %.
6. Back in File Manager, extract each of the three zips, one at a time, into /public_html (select the zip, click Extract, path /public_html). Each part holds different files, so order does not matter. If it asks to overwrite existing files, tell me which ones before agreeing.
7. Check, and report each number:
   - public_html/journeys contains 1,703 files
   - public_html/index.html is 39,770 bytes
   - public_html/contact.html is 10,070 bytes
   - public_html/data/journeys-index.json is 638,404 bytes
   - public_html/api/enquiry.php is 5,533 bytes
   - public_html/.htaccess and public_html/api/data/.htaccess exist
8. Delete the three part zips from public_html (only those three files).

PART D — SERVER SETTINGS FILE
9. In public_html/api, create a new file named config.php with exactly this content:

<?php
return [
    'signing_secret' => '',
    'notify_to'      => '',
    'notify_from'    => '',
    'ip_salt'        => '037c69b6d0f58afdcbe7a0bc3f522470',
];

PART E — STAGING ADDRESS
10. cPanel → Domains → Create A New Domain: staging.cruise24.me. TICK "Share document root (/home/ekrd2r2976p9/public_html) with cruise24.me". Submit.
11. GoDaddy DNS for cruise24.me: ADD one record: type A, name staging, value 92.205.251.216, TTL 1 hour. If a "staging" record already exists, stop and tell me. Change nothing else.

PART F — TEST (wait 10–15 minutes after step 11)
12. Open https://staging.cruise24.me/ (if HTTPS fails, use http:// and tell me). Report: does the home page load with its photos and video? Any error page?
13. Open /journeys.html: how many sailings does it say it shows? Open any one sailing page: does it load?
14. Open /contact.html and send the form with name "TEST delete me", email test@example.com, anything in the other fields. Report the exact message shown under the button.
15. Open https://staging.cruise24.me/api/data/leads.ndjson.php in the browser: it must show "Not Found" or an empty page, NOT the test data. Report what you see.
16. In File Manager, open public_html/api/data: confirm leads.ndjson.php exists (the test request). Then delete leads.ndjson.php and ratelimit.json.php (only those two files there; keep .htaccess).
17. If every page shows "500 Internal Server Error": rename public_html/.htaccess to htaccess-off, reload, and tell me whether that fixed it.

Finish with a short report: Part A findings, backup name and size (or "public_html was empty"), the step 7 numbers, and the results of steps 12–17.
```

## Step 3: go live (later)

When `python3 build_bundle.py` passes (no `--draft`): upload the final bundle the same way, then
change the `@` and `www` records from Website Builder to 92.205.251.216, keep MX/TXT as they are,
and disconnect the Websites + Marketing site from the domain. That replaces the live site, so it
waits for the legal facts.

## For the privacy page once hosting is settled

GoDaddy is a US company, so the privacy page must name the GoDaddy contracting entity and the basis
for the transfer to the US. Take both from GoDaddy's own Data Processing Addendum for this account;
do not write them from memory.
