# Hosting the test build

Everything needed to put this online is in the repo. **I could not run the
deploy** — this machine has no host CLI installed and no account credentials, so
the last step is yours. It is one command once you have an account.

---

## What it needs from a host, and why most will not do

This is **not a static site**. Online play needs a process that stays alive and
holds every open socket in memory, and the game and the sockets must share an
origin so the WebSocket is same-origin.

That rules out Netlify, GitHub Pages, Cloudflare Pages and Vercel's static tier:
they serve files, and the BATTLE button would be dead. It also rules out any
plan that sleeps on idle — a cold start drops every socket and ends every match
in progress.

**What it does need:** one small always-on container with WebSocket support.
512 MB is plenty.

---

## Option A — Fly.io (recommended)

Keeps a machine running, WebSockets work, and a single shared-cpu-1x machine is
a few dollars a month.

```bash
brew install flyctl && fly auth login
```

```bash
fly launch --no-deploy --copy-config --name persia-at-war-test
```

```bash
fly secrets set ACCESS_USER=team ACCESS_PASS='pick-something-long'
```

```bash
fly deploy
```

`fly.toml` is already written, including the health check and
`auto_stop_machines = false` — do not turn that off, it is what stops matches
dying when the machine idles.

## Option B — Render

Simplest dashboard. `render.yaml` is written; use the **starter** plan, not
free — free sleeps, and a sleeping server drops sockets.

1. New → Blueprint → point at this repo.
2. Set `ACCESS_PASS` in the dashboard when prompted (it is marked `sync: false`
   so it never lands in git).
3. Deploy.

## Option C — anywhere that runs a container

```bash
docker build -t persia-at-war .
```

```bash
docker run -p 8080:8080 -e ACCESS_USER=team -e ACCESS_PASS='pick-something-long' persia-at-war
```

Works on Railway, Koyeb, a DigitalOcean droplet, or your own box.

---

## Settings

| Variable | What it does |
|---|---|
| `ACCESS_PASS` | **Set this.** Turns on the password gate. Unset = anyone with the URL can play. |
| `ACCESS_USER` | Username for the prompt. Defaults to `team`. |
| `WS_PORT` | Port. Hosts usually set this; default 8080 in the image. |
| `SERVE_DIST` | `1` to serve the built game as well as the sockets. Set in the image. |
| `ALLOWED_ORIGINS` | Comma-separated. Unset means same-host only, which is right for one domain. |
| `MAX_PER_IP` | Connection ceiling per address, default 8. |
| `MAX_PLAYERS` | Total ceiling, default 400. |

Give the team the URL plus the username and password. The browser prompts once
and remembers for a week.

---

## What was hardened to make this safe to expose

A LAN build needed none of this — being on the wifi was the security. These went
in because "reachable from home" means "reachable by anyone who finds the URL".

- **Password gate.** HTTP Basic Auth, which every browser and phone handles
  natively. On success the server sets a signed cookie so the WebSocket upgrade
  can be checked too, since browsers do not resend Basic credentials on a socket
  handshake. Verified: no password 401, wrong password 401, correct 200.
- **Origin allowlist on the socket.** Without it any other website could open a
  socket from a visitor's browser and sit in your matchmaking queue. Verified:
  a foreign `Origin` is refused 403 even holding a valid cookie.
- **Name moderation.** Names are the one piece of free text one player shows
  another, and the audience is nine to fourteen. Normalisation defeats padding,
  repeats and character substitution, so `f-u-c-k`, `M0derator` and `4dm1n` are
  all caught. Impersonation (`admin`, `official`, `staff`) is refused separately
  from profanity, because in a children's product it is the more dangerous of
  the two.
- **Connection ceilings.** 8 per address, 400 total. Verified: the ninth
  connection from one address is refused.
- **The health endpoint bypasses the gate**, or the host would call a healthy
  server dead and restart it forever.
- **Request handlers cannot crash the process.** They used to: a non-ASCII
  character in the auth header threw `ERR_INVALID_CHAR` and killed the server on
  the *first unauthenticated request* — that is, on the first stranger who found
  the URL. Fixed, and the handler is wrapped so nothing else can do it either.

---

## Still true, and still blocking a real launch

The gate makes this safe to hand to a team. It does **not** make the game ready
for the public.

- **The word list is a starter, English only.** The mechanism is sound and
  tested; the list needs replacing with a maintained, multi-language one. The
  audience includes Farsi speakers and it covers none of that.
- **No reporting, blocking or muting.** If a tester meets a name that got
  through, they have no way to flag it.
- **No age gate and no parental consent flow.** Required before any real-money
  path, and for under-13s in the US regardless.
- **No accounts.** Progress is per-device and per-browser. Clearing site data
  resets a tester.
- **Nothing charges money** — the Bazaar's euro prices are still a display shell.

Keep the URL within the team.
