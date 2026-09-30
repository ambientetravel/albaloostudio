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
staging.*. Bundle: `python3 build_bundle.py --draft --parts-mb 10` → eight standalone zips of ≤ 10 MiB (28 MiB parts timed out in the chat's file transfer), 1,882 files in total; verified equal to the single zip.

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
5. The site comes in EIGHT zip files whose names end in -part1of8.zip … -part8of8.zip (3 to 10 MB each, all starting DRAFT-cruise24-me-20260928-147dfef). In public_html, click Upload. Stop and let me choose the eight files. Wait until every upload shows 100 %.
6. Back in File Manager, extract each of the eight zips, one at a time, into /public_html (select the zip, click Extract, path /public_html). Each part holds different files, so order does not matter. If it asks to overwrite existing files, tell me which ones before agreeing.
7. Check, and report each number:
   - public_html/journeys contains 1,703 files
   - public_html/index.html is 39,770 bytes
   - public_html/contact.html is 10,070 bytes
   - public_html/data/journeys-index.json is 638,404 bytes
   - public_html/api/enquiry.php is 5,533 bytes
   - public_html/.htaccess and public_html/api/data/.htaccess exist
8. Delete the eight part zips from public_html (only those eight files).

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

## Staging progress (28 Sep, Claude in Chrome)

- Backup: `/home/ekrd2r2976p9/public_html-backup-20260928.zip`, 4,073 bytes (original public_html:
  cgi-bin, 404.shtml, home.html, layout-styles.css; those four are still in public_html, harmless).
- Extracted into `/home/ekrd2r2976p9/c24-extract` first, no collisions, moved into public_html (22 items,
  hidden files included). Checked in place: journeys 1,703 files, index.html 39,770, contact.html 10,070,
  data/journeys-index.json 638,404, api/enquiry.php 5,533, .htaccess 322, api/.htaccess 279,
  api/data/.htaccess 183, api/config.php 162 bytes. The part zips and c24-extract are in cPanel Trash.
- cPanel subdomain staging.cruise24.me → /public_html. DNS: A `staging` → 92.205.251.216 (saved, resolves).
- Disk: 181 MB of 10 GB; 2,218 of 250,000 files.
- **Blocked:** HTTPS for staging. The hosting's only certificate covers cruise24.me, www and the cPanel
  names, not staging, and expired Feb 2026. Chrome forces https, so http:// does not help.
  AutoSSL tried 28 Sep: cPanel answers **"You do not have the feature "autossl"."** GoDaddy has it off
  on this plan. SSL/TLS Status: cruise24.me, www, mail "expired 25 Feb 2026, will not renew via AutoSSL
  (not issued via AutoSSL)"; staging and mail.staging "not covered".
  For the tests: Alireza clicks through Chrome's warning (Advanced → Proceed), then tests 12–17.

## SSL: free route chosen (Alireza, 28 Sep): Let's Encrypt via acme.sh

AutoSSL is off on this plan and the only certificate expired 25 Feb 2026, so cruise24.me would show a
security warning the moment `@` points here. The route: SSH on, acme.sh in the home folder, certificates
installed into cPanel with acme.sh's `cpanel_uapi` deploy hook, renewed by acme.sh's own cron (60 days).

**Now: staging only.** Let's Encrypt's HTTP check must reach this server, and cruise24.me / www still
point at Website Builder, so only staging.cruise24.me can be issued by the web check today. Prompt below.

**At go-live, in this order:**
1. Issue cruise24.me + www by DNS check (they still point at Website Builder):
   `~/.acme.sh/acme.sh --issue --dns -d cruise24.me -d www.cruise24.me --keylength ec-256 --yes-I-know-dns-manual-mode-enough-go-ahead-please`
   It prints two `_acme-challenge` TXT values; add them in GoDaddy DNS, wait ~10 min, then run the
   same command with `--renew` instead of `--issue`. Deploy with `--deploy -d cruise24.me --ecc --deploy-hook cpanel_uapi`.
2. Check in SSL/TLS Status that cruise24.me and www are covered.
3. Move the `@` A record to 92.205.251.216. Check https://cruise24.me/ loads without a warning.
4. Switch renewal to the automatic web check: re-issue with
   `--issue -d cruise24.me -d www.cruise24.me -w /home/ekrd2r2976p9/public_html --keylength ec-256 --force`,
   deploy again, then delete the two `_acme-challenge` TXT records.
5. Remove the staging certificate from renewal (`--remove -d staging.cruise24.me --ecc`), then the
   staging subdomain and its `staging` A record. See "Shared folder = shared certificate slot".
Manual DNS-mode certificates do not renew on their own; step 4 is what makes them automatic.

**Done 28 Sep:** SSH on (GoDaddy settings "SSH Access: On"; cPanel Terminal opens by direct link,
not in the menu). acme.sh v3.1.6 in ~/.acme.sh, default CA Let's Encrypt, cron
`11 5,11,17,23 * * * … acme.sh --cron`. Certificate for staging.cruise24.me issued (Let's Encrypt YE1,
ECC, ends 27 Dec 2026; next renewal ~26 Nov 2026). Deploy via `cpanel_uapi` succeeded; the
`install_ssl … exit 255` warnings come from a GoDaddy post-install hook and did not stop it.

**Shared folder = shared certificate slot.** staging shares cruise24.me's document root, so cPanel
installed the staging certificate on the **cruise24.me** vhost, replacing the old (expired 25 Feb 2026,
not publicly served) certificate for cruise24.me/www/mail/cpanel/webmail. Harmless now, but it sets
two go-live rules:
- The go-live certificate (cruise24.me + www) replaces the staging one on that slot; that is expected.
- **Then remove staging from renewal**, or its 60-day renewal will re-deploy onto the same slot and
  knock out the cruise24.me certificate:
  `~/.acme.sh/acme.sh --remove -d staging.cruise24.me --ecc`
  and delete the staging subdomain in cPanel and the `staging` A record in DNS.

Prompt for Claude in Chrome (staging certificate + tests):

```text
Set up free, auto-renewing SSL (Let's Encrypt, via acme.sh) on our GoDaddy cPanel hosting, for staging.cruise24.me only. Then run the staging tests.

Account facts: Web Hosting Economy, cPanel user ekrd2r2976p9, home /home/ekrd2r2976p9, document root /home/ekrd2r2976p9/public_html, server IP 92.205.251.216.

HARD RULES
- Do not buy, renew, upgrade or accept any offer or paid certificate.
- Do not change any DNS record. Do not touch cruise24.me or www in any way.
- Only type the commands below, exactly as written, one at a time. Do not add sudo or change any path.
- After each command, copy me its last lines of output. If a command prints an error, stop and paste the whole error.
- If GoDaddy asks me to log in or for a 2FA code, stop and wait for me.

PART 1 — TURN ON SSH
1. In GoDaddy: My Products → Web Hosting (cPanel) → Settings (or the hosting dashboard). Find "SSH access" and switch it ON. Tell me what the page says after saving.
2. Open cPanel → Advanced → Terminal. If a warning appears, click "I understand and want to proceed". If there is no Terminal in cPanel, stop and tell me.

PART 2 — INSTALL acme.sh (in the cPanel Terminal)
3.  curl -fsSL https://get.acme.sh | sh
4.  ~/.acme.sh/acme.sh --version
5.  ~/.acme.sh/acme.sh --set-default-ca --server letsencrypt
6.  crontab -l | grep acme
    (step 6 must show one line containing "acme.sh --cron". If it shows nothing, tell me.)

PART 3 — CERTIFICATE FOR staging.cruise24.me
7.  ~/.acme.sh/acme.sh --issue -d staging.cruise24.me -w /home/ekrd2r2976p9/public_html --keylength ec-256
    (Success ends with lines like "Your cert is in:" and "Full-chain cert is in:".)
8.  ~/.acme.sh/acme.sh --deploy -d staging.cruise24.me --ecc --deploy-hook cpanel_uapi
    (Success says "Success" / "Certificate successfully deployed".)
9.  ~/.acme.sh/acme.sh --list
10. In cPanel → SSL/TLS Status: tell me the status line for staging.cruise24.me and the certificate's expiry date.
11. Open https://staging.cruise24.me/ in a new tab. It must load with NO privacy warning. Tell me what you see.

PART 4 — STAGING TESTS (only once step 11 loads without a warning)
12. On https://staging.cruise24.me/ : does the home page load with its photos and video? Any error?
13. Open /journeys.html: how many sailings does it say it shows? Open any one sailing page: does it load?
14. Open /contact.html and send the form with name "TEST delete me", email test@example.com, anything in the other fields. Copy me the exact message shown under the button.
15. Open https://staging.cruise24.me/api/data/leads.ndjson.php : it must show "Not Found" or an empty page, NOT the test data. Tell me what you see.
16. In cPanel File Manager, open public_html/api/data: confirm leads.ndjson.php exists. Then delete leads.ndjson.php and ratelimit.json.php (only those two; keep .htaccess).
17. If every page shows "500 Internal Server Error": rename public_html/.htaccess to htaccess-off, reload, and tell me whether that fixed it.

Finish with a short report: SSH status, the output of steps 4, 6, 7 (last lines), 8 and 9, the step 10 status and expiry, and the results of steps 11–17.
```

## DNS for cruise24.me (read 28 Sep; nameservers ns73/ns74.domaincontrol.com)

| Type | Name | Value | Note |
|---|---|---|---|
| A | @ | "WebsiteBuilder Site" | **change at go-live** to 92.205.251.216 |
| A | staging | 92.205.251.216 | added 28 Sep |
| CNAME | www | cruise24.me. | follows @, no change needed |
| CNAME | email | email.secureserver.net. | GoDaddy mail, keep |
| CNAME | pic, res | apps.odysol.com. | third-party app, keep |
| CNAME | _domainconnect | _domainconnect.gd.domaincontrol.com. | keep |
| CNAME | bounces.cloud2.em, sable.cloud2._domainkey | GoDaddy email-marketing (600 s) | keep |
| CNAME | secureserver1/2._domainkey | s1/s2.dkim.cruise24_me.970.onsecureserver.net. | DKIM, keep |
| MX | @ | smtp.secureserver.net. (0), mailstore1.secureserver.net. (10) | keep |
| TXT | @ | google-site-verification=Y7YD…LhIMU | keep |
| TXT | @ | v=spf1 include:secureserver.net -all | keep |
| TXT | _dmarc | v=DMARC1; p=none; rua=…@dmarc.cloud2.em.secureserver.net (600 s) | **duplicate, see below** |
| TXT | _dmarc | v=DMARC1; p=reject; rua=mailto:dmarc_rua@onsecureserver.net; | **duplicate, see below** |
| SRV | _autodiscover._tcp | 0 0 443 autodiscover.secureserver.net. | keep |

**Two DMARC records.** The DMARC standard allows exactly one; with two, receiving servers ignore both,
so the domain has no DMARC policy in effect, and one says `none` while the other says `reject`.
This predates the website work and touches email delivery, so it is not changed here. Decide which
policy is wanted (usually the `p=none` one first, with reports, then tighten) and delete the other.

## Form fix deployed to staging (28 Sep)

The first staging form test lost an enquiry while resetting the form: consistent with the honeypot
field (then named `website`) being filled, which made the server answer ok and discard it. Fixed in
9fa8938: honeypot hits are stored with `suspect: honeypot`, the pipeline skips them, the field is now
`c24_nb`. Replaced on the server: index.html 39,805, contact.html 10,105, api/enquiry.php 5,685,
api/leads.php 2,974 bytes (old copies in /home/ekrd2r2976p9/c24-backup-20260928b). Retest on
https://staging.cruise24.me/contact.html: thank-you shown, lead stored clean (no "suspect"), test data
deleted. Staging is complete; only the hero video playing has not been seen by a person yet.

## The last legal gap: GoDaddy's contracting company (29 Sep)

The privacy page must name the GoDaddy company that hosts the site. The build environment cannot reach
godaddy.com. Read-only prompt for Claude in Chrome:

```text
Read only; change nothing and accept nothing. Open https://www.godaddy.com/legal/agreements/data-processing-addendum (if it redirects, follow it; if there is a country selector, choose Germany / Deutschland). Copy me, word for word:
1. The sentence that names the GoDaddy company that is the party to the addendum (the "GoDaddy" / processor entity), with its address if given.
2. The sentence(s) saying how personal data transferred outside the EU/EEA is protected (for example Standard Contractual Clauses or the EU-US Data Privacy Framework).
3. The addendum's "last revised" date.
Then open https://www.godaddy.com/legal/agreements/universal-terms-of-service-agreement and copy me the sentence that names the contracting GoDaddy company for customers in Germany or the EU.
```

## Step 3: go live (prompt ready 29 Sep)

Final bundle `dist/cruise24-me-20260929-587f349.zip` (66.1 MB, 1,871 files; build_bundle.py passed with no
blockers), sent as eight parts of ≤ 10 MiB, verified equal to the zip. `.htaccess` redirects http and www
to https://cruise24.me/ and leaves staging alone (tested on Apache 2.4: 301s, 200 on the final address,
noindex on staging, 403 on api/data and api/.htaccess). The prompt backs up, uploads, turns on the inbox
copy to res@cruise24.me, checks staging, issues cruise24.me + www + staging by DNS check, stops for
Alireza's "yes, switch" before the `@` record moves, checks the live site, then re-issues by web check
(automatic renewal) and removes staging.

```text
Go-live for cruise24.me on our GoDaddy cPanel hosting. The new site replaces the Website Builder site. Work through the parts in order and report after each part.

Account facts: Web Hosting Economy, cPanel user ekrd2r2976p9, home /home/ekrd2r2976p9, document root /home/ekrd2r2976p9/public_html, server IP 92.205.251.216. acme.sh is already installed in ~/.acme.sh. cPanel Terminal opens by direct link.

HARD RULES
- Do not buy, renew, upgrade or accept any offer.
- DNS: only the changes named in Parts E, F and H. Never touch MX, the SPF/DMARC/google TXT records, the DKIM or email CNAMEs, "pic", "res", or the nameservers.
- Do not delete the Websites + Marketing site; it is our way back.
- Type terminal commands exactly as written, one at a time; copy me the last lines of each. If one prints an error, stop and paste it.
- If GoDaddy asks for a login or 2FA code, or a file-upload dialog opens, stop and wait for me.
- PART F has a hard stop: do not save the @ change until I say "yes, switch".

PART A — BACKUP
1. File Manager, Show Hidden Files on. Select everything in public_html, Compress as public_html-backup-20260929.zip, Move it to /home/ekrd2r2976p9/. Report its size.

PART B — UPLOAD THE FINAL SITE
2. In public_html click Upload; stop and let me pick the eight files cruise24-me-20260929-587f349-part1of8.zip … part8of8.zip. Wait for 100 % on all.
3. Extract each of the eight zips into /public_html, one at a time. This time existing files WILL be replaced by the new versions; that is intended.
4. Report each: public_html/index.html 39,239 bytes; imprint.html 9,029; privacy.html 10,961; contact.html 10,216; .htaccess 641; assets/site.css 31,313; api/enquiry.php 5,685; media/hero-balcony-1920.mp4 5,569,586; the journeys folder has 1,703 files; api/config.php still exists.
5. Delete the eight part zips from public_html. Then delete these 14 unused files (they are in the backup): media/1d6fe463-Cover-video.mp4, media/2752c37b-Hero-video.mp4, media/cruisehost/11.jpg, media/cruisehost/M2.jpg, media/cruisehost/M4.jpg, media/cruisehost/M5.jpg, media/cruisehost/W9.jpg, media/variety/croatia.jpg, media/variety/grand-hero.jpg, media/variety/italy-2.jpg, media/variety/italy-3.jpg, media/variety/sey-2.jpg, media/variety/sey-3.jpg, media/variety/variety-hero.jpg.

PART C — ENQUIRY COPIES BY EMAIL
6. Edit public_html/api/config.php so it reads exactly:

<?php
return [
    'signing_secret' => '',
    'notify_to'      => 'res@cruise24.me',
    'notify_from'    => 'res@cruise24.me',
    'ip_salt'        => '037c69b6d0f58afdcbe7a0bc3f522470',
];

PART D — CHECK ON STAGING (keep each tab in front while it loads)
7. https://staging.cruise24.me/ : is the big headline in a serif font ("The sea, taken slowly.")? Any error?
8. https://staging.cruise24.me/imprint.html : does it show "Hauptstr. 81" and "Amtsgericht Montabaur, HRB 24620"?
9. https://staging.cruise24.me/contact.html : send the form once, name "TEST go-live", email test@example.com. Copy me the message under the button. Then ask me to check the res@cruise24.me inbox for an email "Cruise24 request: TEST go-live", and wait for my answer.

PART E — CERTIFICATE FOR cruise24.me, www AND staging (cPanel Terminal)
10. ~/.acme.sh/acme.sh --issue --dns -d cruise24.me -d www.cruise24.me -d staging.cruise24.me --keylength ec-256 --yes-I-know-dns-manual-mode-enough-go-ahead-please
    It prints three pairs of "Domain:" and "TXT value:". Copy all three to me exactly.
11. GoDaddy DNS for cruise24.me: ADD three TXT records, TTL 1/2 hour (or the lowest offered):
    name _acme-challenge          → the TXT value printed for '_acme-challenge.cruise24.me'
    name _acme-challenge.www      → the value for '_acme-challenge.www.cruise24.me'
    name _acme-challenge.staging  → the value for '_acme-challenge.staging.cruise24.me'
    Change nothing else.
12. Wait 10 minutes, then:
    ~/.acme.sh/acme.sh --renew -d cruise24.me --ecc --yes-I-know-dns-manual-mode-enough-go-ahead-please
    Success ends with "Your cert is in". If it says "Verify error", wait 10 more minutes and run it once more; if it fails again, stop and paste the output.
13. ~/.acme.sh/acme.sh --deploy -d cruise24.me --ecc --deploy-hook cpanel_uapi
    (The "install_ssl … exit 255" warnings seen last time are expected; it must end with "Success".)
14. ~/.acme.sh/acme.sh --remove -d staging.cruise24.me --ecc
15. cPanel → SSL/TLS Status: report the status and expiry for cruise24.me, www.cruise24.me and staging.cruise24.me.
16. Open https://staging.cruise24.me/ : it must load with no privacy warning.

PART F — THE SWITCH (hard stop)
17. GoDaddy DNS for cruise24.me: open the A record "@" (value "WebsiteBuilder Site") for editing and set the value to 92.205.251.216, TTL 1/2 hour. DO NOT SAVE YET. Tell me what the dialog says (including any warning about the website being disconnected) and wait until I write "yes, switch". Then save. Do not touch the www CNAME or any other record.

PART G — CHECK THE LIVE SITE (15–30 minutes after the switch; keep tabs in front)
18. Open https://cruise24.me/ , http://cruise24.me/ and https://www.cruise24.me/ . Each must end at https://cruise24.me/ with NO privacy warning, showing the new site (serif headline "The sea, taken slowly."). If you still see the old Website Builder site, wait 15 minutes and try again (DNS takes up to an hour).
19. Open https://cruise24.me/imprint.html and https://cruise24.me/journeys.html (how many sailings does it say?).
20. On https://cruise24.me/contact.html send the form once as "TEST live". Copy me the message. Then in File Manager delete public_html/api/data/leads.ndjson.php and ratelimit.json.php (keep .htaccess).

PART H — MAKE RENEWAL AUTOMATIC AND REMOVE STAGING (only after Part G passed)
21. ~/.acme.sh/acme.sh --issue -d cruise24.me -d www.cruise24.me -w /home/ekrd2r2976p9/public_html --keylength ec-256 --force
22. ~/.acme.sh/acme.sh --deploy -d cruise24.me --ecc --deploy-hook cpanel_uapi
23. ~/.acme.sh/acme.sh --list   (cruise24.me must be listed, staging must not)
24. GoDaddy DNS: DELETE the three _acme-challenge TXT records and the A record "staging". Nothing else.
25. cPanel → Domains: remove staging.cruise24.me. If it offers to delete files or the document root, say NO: it shares public_html with the live site.
26. Open https://cruise24.me/ once more: still loads, no warning.

Finish with one report: backup size, the Part B numbers, Part D answers, Part E outputs (steps 10, 12, 13, 15), the Part G results, and Part H outputs (21–23).

WAY BACK, if the live site misbehaves after Part F: set the A record "@" back to the Website Builder site (GoDaddy: Websites + Marketing → "Cruise 24" → connect domain cruise24.me), then tell me.
```

## Live since 29/30 Sep; speed update 30 Sep

cruise24.me, www and staging resolve to 92.205.251.216 (checked 30 Sep 09:25 UTC). Alireza reported
slow and sometimes missing photos and video in Chrome and Safari. Cause: every video got its file on page
open (home 17 videos, 35 MB) and held the few connections GoDaddy Economy allows per visitor, starving the
photos; no compression or cache headers. Fixed in f31f544 (lazy videos, direct photo src, media re-encoded
72 → 25 MB, gzip + 30-day cache). Update bundle `cruise24-me-20260930-f31f544` (5 parts, 43.7 MB).
**Speed update live 30 Sep** (Claude in Chrome): backup public_html-backup-20260930.zip 66,010,248 bytes;
five parts extracted (15 + 38 + 372 + 1,234 + 212 files); all seven check sizes matched; api/config.php
and api/data untouched; home page and hero video, destinations (16 photos) and journal (6 photos) load
with no broken files or console errors.
Part H: steps 21–23 ran on 29 Sep; step 24 stopped at the 2FA prompt, so the TXT records
`_acme-challenge` and `_acme-challenge.www`, the A record `staging` and the cPanel domain
staging.cruise24.me still exist (harmless). Before deleting them, confirm `Le_Webroot` in
~/.acme.sh/cruise24.me_ecc/cruise24.me.conf is the public_html path, not "dns".

```text
Update the live cruise24.me site with a faster version. Same procedure as before; no DNS change, no settings change.

Account: cPanel user ekrd2r2976p9, document root /home/ekrd2r2976p9/public_html.
Rules: do not buy or accept anything; do not touch DNS; do not edit or delete public_html/api/config.php or anything in public_html/api/data; stop for any login, 2FA code or file-upload dialog.

1. Backup: File Manager, Show Hidden Files on. Select everything in public_html, Compress as public_html-backup-20260930.zip, Move it to /home/ekrd2r2976p9/. Report its size.
2. In public_html click Upload; stop and let me pick the five files cruise24-me-20260930-f31f544-part1of5.zip … part5of5.zip. Wait for 100 % on all.
3. Extract each of the five into /public_html, one at a time. Existing files will be replaced; that is intended.
4. Report the exact sizes: index.html 35,826 bytes; .htaccess 1,765; assets/site.js 7,378; destinations.html 22,270; media/hero-balcony-1920.mp4 2,282,956; media/hero-balcony-1080sq.mp4 601,918; media/variety/kusadasi.jpg 232,737. Confirm api/config.php still exists.
5. Delete the five part zips from public_html (only those five).
6. Open https://cruise24.me/ in a new tab kept in front, and reload once with Ctrl+Shift+R (Cmd+Shift+R on Mac). Does the page and its hero video appear? Any error page? Then open https://cruise24.me/destinations.html and https://cruise24.me/journal.html : do the photos appear?
Finish with a short report of steps 1–6.
```

## For the privacy page once hosting is settled

GoDaddy is a US company, so the privacy page must name the GoDaddy contracting entity and the basis
for the transfer to the US. Take both from GoDaddy's own Data Processing Addendum for this account;
do not write them from memory.
