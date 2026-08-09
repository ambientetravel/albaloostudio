# Deploying albaloostudio.com

Architecture credit: **Albaloo Studio** — [albaloostudio.com](https://albaloostudio.com)
Owner: Alireza Mozaffari

The workflow is [`.github/workflows/deploy-albaloostudio.yml`](../.github/workflows/deploy-albaloostudio.yml).
It needs three secrets and about five minutes of your time, once.

---

## The thing that makes this deploy different

This repository root is **both** the albaloostudio.com document root **and** the
working directory for the whole travel portfolio. `index.html` sits beside
`orchestrator/` (which holds `sites.yml`, `SETUP-GSC.md` and the compliance
gate), `CLAUDE.md`, `AGENTS.md`, `docs/`, and a dozen untracked sibling project
folders — one of which has held a live `PORTAL_SECRET` in a PHP file.

A `mirror -R .` of the repo root would publish every one of those to a public
web server.

So the deploy is an **allowlist, not a mirror**. `scripts/stage-site.py` copies
13 named files into `_site/`, and the workflow mirrors `_site/`. A file reaches
the server because it is named in `PUBLISH`, and for no other reason.

The allowlist fails in both directions, on purpose:

* an asset the site references that is **not** in `PUBLISH` fails the run — the
  "I added a photo and forgot to list it" case, which would otherwise deploy a
  page with a broken image;
* a file in `PUBLISH` that is **not** on disk fails the run;
* anything internal named in `PUBLISH` fails the run, and the staged tree is
  re-checked for internal paths afterwards.

**Adding a page or an image means adding it to `PUBLISH` in
[`scripts/stage-site.py`](../scripts/stage-site.py).** That is the design, not
an oversight.

It also leaves ~20MB behind deliberately: the raw Midjourney exports
(`Davan_motion.Full_body_front-facing…mp4` and six siblings) are superseded
originals the site never references. They stay in git; they do not go to the
server.

---

## 1. Create a scoped FTP account (5 min, once)

In the GoDaddy hosting panel (cPanel → **FTP Accounts**):

1. Username: something identifiable — `deploy-albaloostudio`
2. Password: generate a long random one. **You never type this anywhere except
   the GitHub secret box.**
3. Directory: the document root for albaloostudio.com, usually
   `public_html`. Set it explicitly — not the account home. That is the whole
   point: the credential cannot see another site even if it leaks.
4. Quota: unlimited (the media alone is ~19MB).

---

## 2. Put it in GitHub, not in a chat

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `ALBALOO_FTP_HOST` | the FTP hostname from the panel, e.g. `ftp.albaloostudio.com` |
| `ALBALOO_FTP_USER` | the scoped account from step 1 |
| `ALBALOO_FTP_PASSWORD` | its password |

Optional repository **variable** `ALBALOO_FTP_REMOTE_DIR` if the account lands
somewhere other than the directory you want to write to. With a scoped account
it usually lands correctly and you can leave it unset.

> Paste the password only into that box. Not into a chat window, not into a
> file, not into a commit. Anything typed into a conversation persists in its
> transcript.

---

## 3. First run: dry run

**Actions → Deploy albaloostudio.com → Run workflow**, leave *"Connect and list
what WOULD upload"* ticked. Manual dispatch defaults to a dry run precisely so
the first attempt cannot damage anything.

It stages, runs every guard, connects, and prints exactly which files it
*would* upload. Read that list. If it wants to move something that is not one
of the 13, stop and find out why.

Then run it again with the box unticked.

After that, **every push to `main` that touches a site file deploys**. Pushes
that only touch `orchestrator/` or docs do not — see the `paths:` filter.

---

## 4. What the workflow refuses to do

**It never deletes remote files.** `lftp mirror -R` without `--delete` uploads
and overwrites, full stop. The live docroot may hold files that are not in this
repo. If something genuinely has to go, delete it by hand, once.

**It will not deploy a broken or leaky build.** Missing `index.html`,
`sitemap.xml` that is not valid XML, a sitemap listing a `noindex` page, or any
internal path in `_site/` — each fails the run before it connects to anything.

**It verifies against the live URL afterwards**, not against the artifact it
just built. It fetches `https://albaloostudio.com/` and fails if the bytes
differ from what was deployed, then checks `sitemap.xml` and `robots.txt`
return 200.

The www check is a **warning, not a failure**, and that is deliberate: if
`www.albaloostudio.com` does not return 301 after this deploys, `.htaccess` is
not being read on this host and the fix belongs in GoDaddy's domain settings
rather than in the file. Failing the deploy over a host configuration issue
would block every future deploy for a reason the deploy cannot fix.

---

## 5. Rotating or revoking

Delete the FTP account in the panel. That is the entire revocation — no other
credential changes, nothing else on the account was ever reachable from CI.
Create a new one and update the one secret.

---

*Architecture by **Albaloo Studio** — albaloostudio.com. Owner: Alireza Mozaffari.*
