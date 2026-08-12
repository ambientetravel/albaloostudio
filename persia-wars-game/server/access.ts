import { createHmac, timingSafeEqual } from 'node:crypto';
import type { IncomingMessage, ServerResponse } from 'node:http';

/**
 * Access gate for a hosted test build.
 *
 * A LAN build needed no gate: being on the wifi was the gate. Once it is on the
 * open internet, anything reachable is findable, and this game has live
 * multiplayer with a free-text name field aimed at nine-to-fourteen-year-olds.
 * A shared passphrase keeps a team test a team test.
 *
 * Set `ACCESS_PASS` to switch it on. With it unset the server runs open, which
 * is correct for `npm run share` on a LAN and wrong for anything public — the
 * deploy configs set it.
 *
 * HTTP Basic Auth is used because every browser and phone handles it natively
 * with no login screen to build. It is only safe over HTTPS, which every host
 * below terminates for us.
 */
const PASS = process.env.ACCESS_PASS ?? '';
const USER = process.env.ACCESS_USER || 'team';
export const ACCESS_REQUIRED = PASS.length > 0;

/** Secret for the cookie. Derived from the passphrase so there is one thing to set. */
const SECRET = createHmac('sha256', 'persia-at-war').update(PASS).digest();
const COOKIE = 'paw_access';

function token(): string {
  return createHmac('sha256', SECRET).update('granted').digest('hex').slice(0, 32);
}

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

/** Reads our cookie out of a request. Browsers send cookies on same-origin WS upgrades. */
export function hasValidCookie(req: IncomingMessage): boolean {
  if (!ACCESS_REQUIRED) return true;
  const raw = req.headers.cookie ?? '';
  for (const part of raw.split(';')) {
    const [k, v] = part.trim().split('=');
    if (k === COOKIE && v && safeEqual(v, token())) return true;
  }
  return false;
}

function credentialsOk(req: IncomingMessage): boolean {
  const header = req.headers.authorization ?? '';
  if (!header.startsWith('Basic ')) return false;
  const [user, ...rest] = Buffer.from(header.slice(6), 'base64').toString('utf8').split(':');
  const pass = rest.join(':');
  return safeEqual(user, USER) && safeEqual(pass, PASS);
}

/**
 * Returns true when the request may proceed. Otherwise it has already been
 * answered with a 401 challenge.
 */
export function guardHttp(req: IncomingMessage, res: ServerResponse): boolean {
  if (!ACCESS_REQUIRED) return true;
  if (hasValidCookie(req)) return true;

  if (credentialsOk(req)) {
    // Hand out a cookie so the WebSocket upgrade can be checked too — browsers
    // do not reliably resend Basic credentials on a WS handshake.
    res.setHeader(
      'Set-Cookie',
      `${COOKIE}=${token()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800`,
    );
    return true;
  }

  // ASCII only. HTTP header values are latin1, and a stray em-dash here threw
  // ERR_INVALID_CHAR — which crashed the process on the very first
  // unauthenticated request, i.e. on every stranger who found the URL.
  res.writeHead(401, {
    'WWW-Authenticate': 'Basic realm="Persia at War test build", charset="UTF-8"',
    'Content-Type': 'text/plain; charset=utf-8',
  });
  res.end('This test build is password protected.');
  return false;
}

/**
 * Origin allowlist for the socket upgrade. Without it any other website could
 * open a socket to this server from a visitor's browser and sit in the
 * matchmaking queue. `ALLOWED_ORIGINS` is a comma-separated list; unset means
 * same-host only, which covers both the LAN build and a single-domain deploy.
 */
const ALLOWED = (process.env.ALLOWED_ORIGINS ?? '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

export function originAllowed(req: IncomingMessage): boolean {
  const origin = req.headers.origin;
  // Non-browser clients (the test harness, curl) send no Origin.
  if (!origin) return true;
  if (ALLOWED.length > 0) return ALLOWED.includes(origin);
  try {
    return new URL(origin).host === req.headers.host;
  } catch {
    return false;
  }
}
