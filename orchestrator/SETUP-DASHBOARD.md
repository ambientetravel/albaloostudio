# dashboard.boutimar.com — setup

Architecture credit: Albaloo Studio — albaloostudio.com
Owner: Alireza Mozaffari

One password-gated page showing what the portfolio is doing: which sites can
actually receive an article, what the last scout cost per property, where every
drafted word ended up, and how each site compares to its named rivals. Rebuilt
every Monday 06:00 UTC by the **Portfolio dashboard** workflow.

## Why it is not a static file behind .htaccess

Netafraz serves static files through **nginx directly**. That is already
documented in this repo as the reason `Header` and `Expires` rules only ever
reached PHP and never static HTML — and it has a sharper consequence here: a
`.htaccess` basic-auth block would **not** protect a static `dashboard.html`.
The page would look gated and be readable by anyone with the URL.

So the data lives **outside the web root** and PHP reads it:

```
~/domains/dashboard.boutimar.com/
├── public_html/
│   └── index.php              ← the gate, all nginx can serve
└── private/
    ├── dashboard.html         ← the data, not servable at any URL
    └── dashboard-auth.php     ← the bcrypt hash, never the password
```

---

## 1. Create the subdomain (DirectAdmin)

1. **Account Manager → Domain Setup → Add New Domain**, or **Subdomain
   Management** under `boutimar.com`.
2. Domain: `dashboard.boutimar.com`
3. Let DirectAdmin create the document root. Note the path it reports —
   normally `/home/<user>/domains/dashboard.boutimar.com/public_html`.
4. **SSL Certificates → Free & automatic certificate from Let's Encrypt** for
   `dashboard.boutimar.com`, and tick **Force SSL redirect**. The session
   cookie is marked `secure`, so without HTTPS you will be able to sign in and
   never stay signed in.

## 2. Create the `private/` directory

**File Manager**, go to `domains/dashboard.boutimar.com/`, and create a folder
`private` **as a sibling of `public_html`, not inside it.**

If it ends up inside `public_html`, the data file becomes reachable at a URL
and the whole design is defeated. The workflow's last step checks for exactly
that and fails the run if it finds it.

## 3. Create a scoped FTP account

**FTP Management → Create FTP Account.**

- Username: something like `dashboard@boutimar.com`
- **Custom directory**: `/home/<user>/domains/dashboard.boutimar.com`
  — the domain directory, **not** `public_html`, because the deploy writes to
  both `public_html/` and `private/`.
- A long random password.

Scoped this way the account can see one subdomain and nothing else, and
revoking it is deleting the account.

## 4. Generate the password hash

On your Mac, pick a password and turn it into a bcrypt hash. **Only the hash
leaves your machine.**

```bash
python3 -c "import bcrypt,getpass;print(bcrypt.hashpw(getpass.getpass('Password: ').encode(),bcrypt.gensalt()).decode())"
```

If `bcrypt` is not installed: `python3 -m pip install bcrypt` first.

It prints something starting `$2b$12$…`. Copy that line.

> Paste it into a text editor and look at it before going further. It must
> start with `$2` and be about 60 characters. Twice today a value was stored
> that was not what anyone intended — an 8-character token and a shell command
> — and both times looking at the string first would have caught it.

## 5. Store the four secrets

**https://github.com/ambientetravel/albaloostudio/settings/secrets/actions** →
New repository secret, four times:

| Name | Value |
|---|---|
| `DASHBOARD_FTP_HOST` | your Netafraz FTP host |
| `DASHBOARD_FTP_USER` | the FTP username from step 3 |
| `DASHBOARD_FTP_PASSWORD` | that account's password |
| `DASHBOARD_PASSWORD_HASH` | the `$2b$…` hash from step 4 |

The dashboard password itself is never stored anywhere but your head and your
password manager. The workflow only ever sees the hash.

## 6. Run it

Actions → **Portfolio dashboard** → Run workflow.

Then open **https://dashboard.boutimar.com** and sign in.

## What the workflow checks after deploying

It does not assume the deploy worked. It fetches the live page and fails the
run if any of these is wrong:

- the login form does not render
- **the dashboard content is served without a password** — the failure that
  matters most
- `dashboard.html`, `private/dashboard.html` or `../private/dashboard.html`
  returns 200 at any URL

If the secrets are absent the workflow skips deployment entirely and still
uploads the artifact, so nothing breaks while this is half-configured.

## If the FTP account can only be scoped to `public_html`

Some hosts refuse a custom directory above the web root. Then `private/`
cannot be written by the deploy, and the honest options are, in order:

1. create `private/` by hand once in File Manager and give the FTP user write
   access to it;
2. keep the data inside `public_html` under a long random filename and accept
   that it is protected by obscurity rather than by anything real — the
   workflow's exposure check will fail, and that failure would be correct;
3. move the page to a host where PHP can read above the root.

Do not silently take option 2. A page that looks gated and is not is worse
than one that is obviously open.
