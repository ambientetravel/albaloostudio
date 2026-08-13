/**
 * Persia at War — matchmaking server.
 *
 * Run with `npm run server`. Node loads this TypeScript directly via type
 * stripping, which is why it can share sim/roundCore.ts and sim/rng.ts with the
 * browser instead of keeping a second, drifting copy of the draft rules.
 *
 * What it does: pairs waiting players, assigns the match seed, runs the round
 * clock, holds both picks until both have arrived, and validates each pick
 * against the same offer it derives itself. What it deliberately does not do:
 * simulate battles. Both clients run the identical deterministic sim on the
 * shared seed and reach the same result on their own — and both report that
 * result back, so a disagreement is caught rather than silently tolerated.
 */
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { existsSync, readFileSync, statSync, createReadStream } from 'node:fs';
import { dirname, extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { networkInterfaces } from 'node:os';
import { WebSocketServer, type WebSocket } from 'ws';
import { ACCESS_REQUIRED, guardHttp, hasValidCookie, originAllowed } from './access.ts';
import { checkName } from './moderation.ts';

import {
  RALLY_AT,
  ROUNDS_MAX,
  WINS_NEEDED,
  addPick,
  emptyLedger,
  matchWinner,
  offersFor,
  type CardIndex,
  type Ledger,
  type OfferCard,
  type Side,
} from '../src/sim/roundCore.ts';
import { assignedName, isAssignedName } from '../src/game/playerNames.ts';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = join(here, '..', 'src', 'content', 'data');
const readJson = <T>(file: string): T => JSON.parse(readFileSync(join(dataDir, file), 'utf8')) as T;

interface UnitRow {
  id: string;
  era: string;
  arena: number;
  atk: number;
  def: number;
  hp: number;
  /** Needed to derive slot C's counter weighting the same way the client does. */
  class: string;
  counters: string[];
  confidence: string;
  earliestAttested: number | null;
}
interface UpgradeRow {
  id: string;
  arena: number;
  trait: string;
  appliesTo: string[];
  confidence: string;
}
interface DoctrineRow {
  id: string;
  arena: number;
  confidence: string;
}
interface CommanderRow {
  id: string;
  affinity: 'wide' | 'deep';
  passive: { id: string };
}
interface BattleRow {
  id: string;
  era: string;
  yearNumeric: number;
}
interface ArenaRow {
  id: number;
}

const units = readJson<UnitRow[]>('units.json');
const upgrades = readJson<UpgradeRow[]>('upgrades.json');
const doctrines = readJson<DoctrineRow[]>('doctrines.json');
const commanders = readJson<CommanderRow[]>('commanders.json');
const commanderOr = (id: unknown): CommanderRow =>
  commanders.find((c) => c.id === id) ?? commanders[0];
/** Mirrors content/index.ts `isPlayable`. Only outright fiction is barred. */
const playable = (confidence: string): boolean => confidence !== 'fictional';
const battles = readJson<BattleRow[]>('battles.json');
const arenas = readJson<ArenaRow[]>('arenas.json');
const MAX_ARENA = arenas.length;

function clampArena(n: unknown): number {
  const v = Math.floor(Number(n));
  if (!Number.isFinite(v)) return 1;
  return Math.min(MAX_ARENA, Math.max(1, v));
}

/**
 * Same rule as content/index.ts draftPool(): verified, era match, the date
 * attestation gate, and the arena the MATCH is being played in.
 *
 * A test (src/net/online.test.ts) asserts this agrees with the client's version
 * for every arena and every scenario — if the two ever drift, the draft desyncs.
 */
function poolFor(battle: BattleRow, arena: number): UnitRow[] {
  return units.filter(
    (u) =>
      playable(u.confidence) &&
      u.era === battle.era &&
      u.arena <= arena &&
      (u.earliestAttested === null || u.earliestAttested <= battle.yearNumeric),
  );
}

// Deliberately not `PORT`: dev harnesses set that for the web server, and
// inheriting it makes the socket server collide with Vite on the same port.
const PORT = Number(process.env.WS_PORT ?? 5184);
const TURN_MS = 25_000;
/**
 * How long the server waits to be told a round's result before giving up on the
 * match. A round's combat is at most ~35 seconds at 1x, and a player can slow
 * playback, so this is deliberately generous.
 */
const ROUND_RESULT_MS = 180_000;

/**
 * With `SERVE_DIST=1` this process also serves the production build over HTTP,
 * and the sockets ride the same port. That is what makes a test build one
 * command and one URL — a static host alone would ship a dead BATTLE button,
 * because online play needs this process running.
 */
const DIST = join(here, '..', 'dist');
const SERVE_DIST = process.env.SERVE_DIST === '1' && existsSync(DIST);

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.mp4': 'video/mp4',
  '.map': 'application/json; charset=utf-8',
};

function serveStatic(req: IncomingMessage, res: ServerResponse): void {
  const url = (req.url ?? '/').split('?')[0];

  // Uptime pings must not be behind the password, or the host will call a
  // healthy server dead and restart it in a loop.
  if (url === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, players: players.size, matches: matches.size }));
    return;
  }

  if (!guardHttp(req, res)) return;
  // Contain every request inside dist/ — no traversal out of the build.
  const rel = normalize(decodeURIComponent(url)).replace(/^(\.\.[/\\])+/, '');
  let file = join(DIST, rel);
  if (!file.startsWith(DIST + sep) && file !== DIST) file = DIST;
  if (!existsSync(file) || statSync(file).isDirectory()) file = join(DIST, 'index.html');
  if (!existsSync(file)) {
    res.writeHead(404).end('not found');
    return;
  }

  const type = MIME[extname(file).toLowerCase()] ?? 'application/octet-stream';
  const size = statSync(file).size;

  // Range support, so the arena films can be scrubbed and stream properly.
  const range = req.headers.range;
  if (range && type.startsWith('video/')) {
    const m = /bytes=(\d*)-(\d*)/.exec(range);
    const start = m && m[1] ? Number(m[1]) : 0;
    const end = m && m[2] ? Number(m[2]) : size - 1;
    res.writeHead(206, {
      'Content-Type': type,
      'Content-Range': `bytes ${start}-${end}/${size}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': end - start + 1,
    });
    createReadStream(file, { start, end }).pipe(res);
    return;
  }

  res.writeHead(200, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes' });
  createReadStream(file).pipe(res);
}

/** Every LAN address this machine answers on, for the share banner. */
function lanAddresses(): string[] {
  const out: string[] = [];
  for (const list of Object.values(networkInterfaces())) {
    for (const n of list ?? []) {
      if (n.family === 'IPv4' && !n.internal) out.push(n.address);
    }
  }
  return out;
}

interface Player {
  id: string;
  ws: WebSocket;
  name: string;
  avatar: number;
  /** The rung the client claims to be on. See the note in startMatch(). */
  arena: number;
  /** The player's warband, which seeds slot A of their offers. */
  deck: string[];
  /** The commander they lead with. Decides affinity and passive. */
  commander: string;
  alive: boolean;
  match: Match | null;
}

interface Match {
  id: string;
  battle: BattleRow;
  arena: number;
  poolIds: string[];
  upgradeIds: string[];
  doctrineIds: string[];
  /** Class, counter and trait facts, so the server derives the same offers. */
  cards: CardIndex;
  seed: number;
  players: Record<Side, Player>;
  decks: Record<Side, string[]>;
  round: number;
  ledgers: Record<Side, Ledger>;
  score: Record<Side, number>;
  commanders: Record<Side, string>;
  /** Comeback B, tracked here too so a reroll can be validated, not trusted. */
  rallyMeter: Record<Side, number>;
  rerolls: Record<Side, number>;
  /** This round's choices. Held until both are in — they are simultaneous. */
  picked: Record<Side, OfferCard | null>;
  /**
   * Each client's report of who won the round. The server does not simulate, so
   * this is how it learns the score — and two reports that disagree mean the
   * clients have desynced, which ends the match rather than letting it drift.
   */
  reported: Record<Side, Side | 'draw' | null>;
  timer: ReturnType<typeof setTimeout> | null;
}

const players = new Map<string, Player>();
const queue: Player[] = [];
const matches = new Map<string, Match>();

/**
 * Per-IP connection ceiling. One person opening a few tabs is normal; a script
 * opening hundreds is not, and this process holds every player in memory.
 */
const MAX_PER_IP = Number(process.env.MAX_PER_IP ?? 8);
const MAX_PLAYERS = Number(process.env.MAX_PLAYERS ?? 400);
const perIp = new Map<string, number>();

function ipOf(req: IncomingMessage): string {
  // Hosts terminate TLS in front of us, so the real address is in the header.
  const fwd = req.headers['x-forwarded-for'];
  const first = Array.isArray(fwd) ? fwd[0] : (fwd ?? '').split(',')[0].trim();
  return first || req.socket.remoteAddress || 'unknown';
}

function withinRateLimit(req: IncomingMessage): boolean {
  if (players.size >= MAX_PLAYERS) return false;
  return (perIp.get(ipOf(req)) ?? 0) < MAX_PER_IP;
}

let counter = 0;
const nextId = (prefix: string): string => `${prefix}${(++counter).toString(36)}${Date.now().toString(36).slice(-4)}`;

function send(p: Player, msg: unknown): void {
  if (p.ws.readyState === p.ws.OPEN) p.ws.send(JSON.stringify(msg));
}

/**
 * Names come from a closed set of 144, so this checks MEMBERSHIP rather than
 * shape — and that is the whole point of closing the set.
 *
 * The old version stripped disallowed characters and truncated to 14, which is
 * a shape check: it would have passed any slur that happened to be spelled in
 * letters. Enforcing membership means a modified client cannot put arbitrary
 * text in front of another player at all, and the game needs no profanity list
 * in any language — there is no user-generated text left in it to filter.
 */
function sanitizeName(raw: unknown): string {
  const name = String(raw ?? '').trim();
  return isAssignedName(name) ? name : assignedName(name.length);
}

function broadcastStats(): void {
  const msg = { t: 'stats', online: players.size, queued: queue.length };
  for (const p of players.values()) send(p, msg);
}

function dequeue(p: Player): void {
  const i = queue.indexOf(p);
  if (i >= 0) queue.splice(i, 1);
}

// ---------------------------------------------------------------- matchmaking

function tryMatch(): void {
  while (queue.length >= 2) {
    const a = queue.shift()!;
    const b = queue.shift()!;
    if (a.ws.readyState !== a.ws.OPEN || a.match) continue;
    if (b.ws.readyState !== b.ws.OPEN || b.match) {
      if (a.ws.readyState === a.ws.OPEN && !a.match) queue.unshift(a);
      continue;
    }
    startMatch(a, b);
  }
  broadcastStats();
}

function startMatch(a: Player, b: Player): void {
  const battle = battles[Math.floor(Math.random() * battles.length)];
  // The LOWER of the two arenas, so a new player is never handed an opponent
  // drafting cards they have not seen yet.
  //
  // Known limitation: with no server-side accounts, the arena is whatever the
  // client claims. Overstating it only helps against an opponent who is already
  // higher, and it cannot affect anyone else's ladder — but a real fix needs
  // persisted profiles server-side.
  const arena = Math.min(a.arena, b.arena);
  const pool = poolFor(battle, arena);
  const poolIds = pool.map((u) => u.id);
  const openUpgrades = upgrades.filter((u) => playable(u.confidence) && u.arena <= arena);
  const openDoctrines = doctrines.filter((d) => playable(d.confidence) && d.arena <= arena);
  const cards: CardIndex = {
    ...Object.fromEntries(
      pool.map((u) => [u.id, { kind: 'unit' as const, cls: u.class, counters: u.counters }]),
    ),
    ...Object.fromEntries(
      openUpgrades.map((u) => [
        u.id,
        { kind: 'upgrade' as const, appliesTo: u.appliesTo, trait: u.trait },
      ]),
    ),
    ...Object.fromEntries(openDoctrines.map((d) => [d.id, { kind: 'doctrine' as const }])),
  };
  const match: Match = {
    id: nextId('m'),
    battle,
    arena,
    poolIds,
    upgradeIds: openUpgrades.map((u) => u.id),
    doctrineIds: openDoctrines.map((d) => d.id),
    cards,
    seed: Math.floor(Math.random() * 0xffffffff) >>> 0,
    players: { a, b },
    // A deck card outside this match's pool is simply ignored by the offer
    // logic, so an over-claimed warband buys nothing.
    decks: { a: sanitizeDeck(a.deck), b: sanitizeDeck(b.deck) },
    round: 1,
    ledgers: { a: emptyLedger(), b: emptyLedger() },
    score: { a: 0, b: 0 },
    commanders: { a: commanderOr(a.commander).id, b: commanderOr(b.commander).id },
    rallyMeter: { a: 0, b: 0 },
    rerolls: { a: 0, b: 0 },
    picked: { a: null, b: null },
    reported: { a: null, b: null },
    timer: null,
  };
  matches.set(match.id, match);
  a.match = match;
  b.match = match;

  for (const side of ['a', 'b'] as Side[]) {
    const me = match.players[side];
    const them = match.players[side === 'a' ? 'b' : 'a'];
    send(me, {
      t: 'match',
      matchId: match.id,
      battleId: battle.id,
      seed: match.seed,
      you: side,
      arena: match.arena,
      opponent: { name: them.name, avatar: them.avatar },
      opponentDeck: match.decks[side === 'a' ? 'b' : 'a'],
      opponentCommander: match.commanders[side === 'a' ? 'b' : 'a'],
    });
  }
  openRound(match);
}

function sanitizeDeck(deck: unknown): string[] {
  if (!Array.isArray(deck)) return [];
  return deck.filter((id): id is string => typeof id === 'string').slice(0, 8);
}

function offerFor(match: Match, side: Side): OfferCard[] {
  const commander = commanderOr(match.commanders[side]);
  const other: Side = side === 'a' ? 'b' : 'a';
  return offersFor({
    seed: match.seed,
    round: match.round,
    side,
    deficit: Math.max(0, match.score[other] - match.score[side]),
    rerolls: match.rerolls[side],
    affinity: commander.affinity,
    startsTrained: commander.passive.id === 'kings-levy',
    poolIds: match.poolIds,
    upgradeIds: match.upgradeIds,
    doctrineIds: match.doctrineIds,
    deck: match.decks[side],
    ledgerSelf: match.ledgers[side],
    ledgerOpponent: match.ledgers[side === 'a' ? 'b' : 'a'],
    cards: match.cards,
  });
}

/** Opens a round's offer window for both players at once. */
function openRound(match: Match): void {
  if (match.timer) clearTimeout(match.timer);
  match.picked = { a: null, b: null };
  match.reported = { a: null, b: null };
  match.rerolls = { a: 0, b: 0 };

  const deadline = Date.now() + TURN_MS;
  const msg = { t: 'roundOpen', round: match.round, deadline };
  send(match.players.a, msg);
  send(match.players.b, msg);

  // Nobody should be able to freeze a stranger's game by walking away.
  match.timer = setTimeout(() => {
    for (const side of ['a', 'b'] as Side[]) {
      if (match.picked[side] === null) match.picked[side] = offerFor(match, side)[0] ?? null;
    }
    releasePicks(match);
  }, TURN_MS + 500);
}

/**
 * Both choices are in. Release them together — sending the first as it arrived
 * would tell the second player what they are up against before they had chosen.
 */
function releasePicks(match: Match): void {
  if (match.picked.a === null || match.picked.b === null) return;
  if (match.timer) clearTimeout(match.timer);

  const picks = { a: match.picked.a, b: match.picked.b };
  // Only the id crosses the wire; each client re-derives the kind and the
  // upgrade's target from its own offer, so the two cannot disagree.
  const msg = { t: 'roundPicks', round: match.round, picks: { a: picks.a.id, b: picks.b.id } };
  send(match.players.a, msg);
  send(match.players.b, msg);

  match.ledgers = {
    a: addPick(match.ledgers.a, picks.a, match.round, match.cards),
    b: addPick(match.ledgers.b, picks.b, match.round, match.cards),
  };

  // The battle itself needs no server involvement: both clients hold the seed
  // and both ledgers, and the sim is deterministic. We wait to be told the
  // result — by both of them.
  match.timer = setTimeout(() => endMatch(match, null), ROUND_RESULT_MS);
}

/** A client reports who won the round. The second report settles it. */
function reportRound(match: Match, side: Side, round: number, winner: Side | 'draw'): void {
  if (round !== match.round) return;
  if (match.reported[side] !== null) return;
  match.reported[side] = winner;

  const { a, b } = match.reported;
  if (a === null || b === null) return;

  if (a !== b) {
    // The two clients computed different battles from the same seed and the
    // same ledgers. That is a bug, not cheating we can adjudicate — and playing
    // on would show the two players different games.
    const message = 'The two devices disagreed on the result. The match was stopped.';
    send(match.players.a, { t: 'error', message });
    send(match.players.b, { t: 'error', message });
    endMatch(match, null);
    return;
  }

  if (a === 'a') match.score.a += 1;
  else if (a === 'b') match.score.b += 1;

  // The Rally meter climbs on a loss and empties on a win.
  if (a !== 'draw') {
    match.rallyMeter[a] = 0;
    const loser: Side = a === 'a' ? 'b' : 'a';
    match.rallyMeter[loser] += 1;
  }

  match.round += 1;
  if (matchWinner(match.score, match.round) !== null) {
    endMatch(match, null);
    return;
  }
  openRound(match);
}

function endMatch(match: Match, notify: Player | null): void {
  if (match.timer) clearTimeout(match.timer);
  matches.delete(match.id);
  for (const side of ['a', 'b'] as Side[]) {
    const p = match.players[side];
    if (p.match === match) p.match = null;
  }
  if (notify) send(notify, { t: 'opponentLeft' });
}

// -------------------------------------------------------------------- sockets

/**
 * A thrown request handler takes the whole process down with it, which for a
 * hosted build means one malformed request ends everyone's match. Nothing in
 * here is worth a crash — log it, return 500, stay up.
 */
function safeHandler(req: IncomingMessage, res: ServerResponse): void {
  try {
    serveStatic(req, res);
  } catch (err) {
    console.error('[persia-at-war] request failed:', err);
    if (!res.headersSent) res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('server error');
  }
}

const http = SERVE_DIST ? createServer(safeHandler) : null;
const wss = http
  ? new WebSocketServer({
      server: http,
      // Refuse the upgrade before a socket exists, rather than accepting and
      // closing: an unauthenticated client should never occupy a connection.
      verifyClient: ({ req }, done) => {
        if (!originAllowed(req)) return done(false, 403, 'Origin not allowed');
        if (!hasValidCookie(req)) return done(false, 401, 'Unauthorised');
        if (!withinRateLimit(req)) return done(false, 429, 'Too many connections');
        done(true);
      },
    })
  : new WebSocketServer({ port: PORT });
if (http) http.listen(PORT, '0.0.0.0');

// Both, not either: when the sockets ride an HTTP server, `ws` re-emits the
// HTTP server's errors on itself, and an EventEmitter with no 'error' listener
// throws instead of reporting. A busy port should print one clear line.
const onFatal = (err: NodeJS.ErrnoException): void => {
  console.error(
    err.code === 'EADDRINUSE'
      ? `\n[persia-at-war] port ${PORT} is already in use.\n` +
        `  Stop the other process, or pick another port:  WS_PORT=5181 npm run serve\n`
      : `[persia-at-war] server error: ${err.message}`,
  );
  process.exit(1);
};
wss.on('error', onFatal);
http?.on('error', onFatal);

wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
  const ip = ipOf(req);
  perIp.set(ip, (perIp.get(ip) ?? 0) + 1);

  const player: Player = {
    id: nextId('p'),
    ws,
    name: 'Player',
    avatar: 0,
    arena: 1,
    deck: [],
    commander: commanders[0].id,
    alive: true,
    match: null,
  };
  players.set(player.id, player);
  send(player, { t: 'welcome', playerId: player.id, online: players.size, queued: queue.length });
  broadcastStats();

  ws.on('message', (raw: unknown) => {
    let msg: { t?: string; [k: string]: unknown };
    try {
      msg = JSON.parse(String(raw)) as { t?: string };
    } catch {
      return;
    }

    switch (msg.t) {
      case 'hello': {
        const name = sanitizeName(msg.name);
        // Shape first, then content. A name that fails moderation does not
        // disconnect the player — it just does not become their name, and they
        // are told why so they can pick another.
        const verdict = checkName(name);
        if (name.length >= 2 && !verdict.ok) {
          send(player, { t: 'error', message: verdict.reason });
          player.name = 'Player';
          break;
        }
        player.name = name.length >= 2 ? name : 'Player';
        player.avatar = Number.isFinite(msg.avatar) ? Math.max(0, Math.min(7, Number(msg.avatar))) : 0;
        player.arena = clampArena(msg.arena);
        player.deck = sanitizeDeck(msg.deck);
        player.commander = commanderOr(msg.commander).id;
        break;
      }

      case 'queue': {
        if (player.match || queue.includes(player)) break;
        queue.push(player);
        send(player, { t: 'queued' });
        tryMatch();
        break;
      }

      case 'cancelQueue': {
        dequeue(player);
        send(player, { t: 'queueCancelled' });
        broadcastStats();
        break;
      }

      case 'pick': {
        const match = player.match;
        if (!match) break;
        const side: Side = match.players.a === player ? 'a' : 'b';
        if (match.picked[side] !== null) break;
        // Validate against the offer this client should have been shown, derived
        // here from the same seed, round and ledgers rather than taken on trust.
        const offer = offerFor(match, side);
        const chosen = offer.find((c) => c.id === msg.unitId);
        if (typeof msg.unitId !== 'string' || !chosen) {
          if (process.env.DEBUG_OFFERS) {
            console.log(
              `[reject] round ${match.round} side ${side} wanted ${String(msg.unitId)} · server offered ${offer
                .map((c) => c.id)
                .join(',')} · score ${JSON.stringify(match.score)} · rerolls ${JSON.stringify(match.rerolls)}`,
            );
          }
          send(player, { t: 'error', message: 'That card was not on offer' });
          break;
        }
        match.picked[side] = chosen;
        // Held, not relayed: releasing the first would tell the second player
        // what they are up against before they had chosen.
        releasePicks(match);
        break;
      }

      case 'rally': {
        const match = player.match;
        if (!match) break;
        const side: Side = match.players.a === player ? 'a' : 'b';
        // Checked here, never trusted: the meter and the spend both live on the
        // server, so a client cannot award itself a reroll.
        if (match.picked[side] !== null) break;
        if (match.rallyMeter[side] < RALLY_AT || match.rerolls[side] !== 0) break;
        match.rerolls[side] += 1;
        // Echoed to BOTH players. v0.1 §8 wants the comeback visible; a reroll
        // the opponent cannot see is the rubber band it is trying not to be.
        const msg = { t: 'rallied', side, round: match.round };
        send(match.players.a, msg);
        send(match.players.b, msg);
        break;
      }

      case 'roundResult': {
        const match = player.match;
        if (!match) break;
        const side: Side = match.players.a === player ? 'a' : 'b';
        const winner = msg.winner;
        if (winner !== 'a' && winner !== 'b' && winner !== 'draw') break;
        reportRound(match, side, Number(msg.round), winner);
        break;
      }

      case 'leaveMatch': {
        const match = player.match;
        if (match) {
          const opponent = match.players.a === player ? match.players.b : match.players.a;
          endMatch(match, opponent);
        }
        break;
      }

      case 'pong':
        player.alive = true;
        break;
    }
  });

  ws.on('close', () => {
    const n = (perIp.get(ip) ?? 1) - 1;
    if (n <= 0) perIp.delete(ip);
    else perIp.set(ip, n);

    dequeue(player);
    players.delete(player.id);
    const match = player.match;
    if (match) {
      const opponent = match.players.a === player ? match.players.b : match.players.a;
      endMatch(match, opponent);
    }
    broadcastStats();
  });
});

// Drop sockets that stopped answering, so the online count means something.
setInterval(() => {
  for (const p of players.values()) {
    if (!p.alive) {
      p.ws.terminate();
      continue;
    }
    p.alive = false;
    send(p, { t: 'ping' });
  }
}, 20_000);

function banner(): void {
  const lines = [
    '',
    SERVE_DIST ? '  PERSIA AT WAR — test build' : '  PERSIA AT WAR — matchmaking server',
    '',
    `  On this machine   http://localhost:${PORT}`,
  ];
  if (SERVE_DIST) {
    for (const ip of lanAddresses()) lines.push(`  On the network    http://${ip}:${PORT}`);
    if (lanAddresses().length === 0) lines.push('  (no network address found — same-machine only)');
  } else {
    lines.push(`  Sockets           ws://localhost:${PORT}`);
  }
  lines.push(
    '',
    `  ${battles.length} scenarios · ${arenas.length} arenas · first to ${WINS_NEEDED} of ${ROUNDS_MAX} rounds`,
    `  Access ${ACCESS_REQUIRED ? 'PASSWORD PROTECTED' : 'open (no ACCESS_PASS set)'}`,
  );
  lines.push('');
  const width = Math.max(...lines.map((l) => l.length)) + 2;
  console.log('\n' + '='.repeat(width));
  console.log(lines.join('\n'));
  console.log('='.repeat(width) + '\n');
}

if (http) http.on('listening', banner);
else wss.on('listening', banner);
