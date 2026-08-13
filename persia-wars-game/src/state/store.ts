import { create } from 'zustand';
import {
  capitalById,
  clampArena,
  content,
  draftPool,
  getBattle,
  getCommander,
  getDoctrine,
  getMission,
  getUnit,
  getUpgrade,
} from '../content';
import type { MissionReward } from '../content/types';
import {
  DECK_SIZE,
  MAX_CARD_LEVEL,
  applyTrophyDelta,
  arenaForTrophies,
  canUpgrade,
  cardsToUpgrade,
  coinsToUpgrade,
  rollCardReward,
  COINS_LOSS,
  COINS_WIN,
  type CardState,
} from '../game/progression';
import {
  bookFinished,
  completeMission,
  freshCampaign,
  missionSucceeded,
  rewardFor,
  setCounterHistory,
  type CampaignState,
} from '../game/campaign';
import { net, type ConnState } from '../net/client';
import { sanitizeName, type PlayerInfo, type ServerMessage } from '../net/protocol';
import { aiRoundPick, makeOpponent, type AiOpponent } from '../sim/ai';
import { simulate, type Squad } from '../sim/battle';
import {
  allFielded,
  bothChosen,
  choose,
  commitPicks,
  improviseDeck,
  nextRound,
  scoreRound,
  spendRally,
  startMatch,
  winnerOf,
  type MatchState,
} from '../sim/match';
import {
  beginRecording,
  chooseTape,
  recordRound,
  recordedRivalPick,
  type MatchRecording,
} from '../sim/recording';
import { loadRecordings, saveRecording } from '../game/recordings';
import { assignedName, isAssignedName, mayTypeOwnName, type AgeBracket } from '../game/age';
import { roundSeedFor } from '../sim/roundCore.ts';
import type { BattleLog, Side } from '../sim/types';

export type Screen =
  | 'age'
  | 'profile'
  | 'lobby'
  | 'collection'
  | 'shop'
  | 'codex'
  | 'ladder'
  | 'matchmaking'
  | 'scenario'
  // The Chronicle: the mission map, a mission's setup card, and the capital.
  | 'campaign'
  | 'mission'
  | 'capital'
  // One screen for the whole contest. The offer slides up over the field rather
  // than replacing it, so a seven-round match never leaves the battlefield.
  | 'battle'
  | 'result';
export type Mode = 'online' | 'ai';
export type Reading = 'kid' | 'older';

export interface Codex {
  battles: string[];
  kings: string[];
  units: string[];
}

export interface Profile {
  name: string;
  avatar: number;
  /** Index into ACHAEMENID_PALETTE. */
  banner: number;
}

export interface Settings {
  sfxVolume: number;
  musicVolume: number;
  haptics: boolean;
}

export interface Wallet {
  coins: number;
  gems: number;
}

export type Collection = Record<string, CardState>;

interface Saved {
  profile: Profile | null;
  /**
   * The age BRACKET only — never a birth date. Nothing here needs one, and a
   * children's app should not be holding one. See game/age.ts.
   */
  ageBracket: AgeBracket | null;
  reading: Reading;
  settings: Settings;
  wallet: Wallet;
  collection: Collection;
  deck: string[];
  /** The commander this player leads with. v0.1 §7. */
  commander: string;
  trophies: number;
  bestTrophies: number;
  wins: number;
  losses: number;
  codex: Codex;
  /** Book One progress: missions done, branches taken, capital built. */
  campaign: CampaignState;
  /** ISO date of the last claimed daily reward, so it can only be taken once. */
  lastDailyClaim: string | null;
}

const SAVE_KEY = 'persia-at-war/v3';

/** A new player starts with the arena-1 cards and a legal deck. */
const STARTER_UNITS = ['persian-archer', 'spara-bearer', 'median-spearman', 'persian-cavalry'];

function freshSave(): Saved {
  const collection: Collection = {};
  for (const id of STARTER_UNITS) collection[id] = { count: 0, level: 1 };
  return {
    profile: null,
    ageBracket: null,
    reading: 'kid',
    settings: { sfxVolume: 100, musicVolume: 100, haptics: true },
    wallet: { coins: 500, gems: 25 },
    collection,
    deck: [...STARTER_UNITS],
    commander: 'cyrus',
    trophies: 0,
    bestTrophies: 0,
    wins: 0,
    losses: 0,
    codex: { battles: [], kings: [], units: [] },
    campaign: freshCampaign(),
    lastDailyClaim: null,
  };
}

function load(): Saved {
  const base = freshSave();
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return base;
    const p = JSON.parse(raw) as Partial<Saved>;
    return {
      ...base,
      ...p,
      profile:
        p.profile && typeof p.profile.name === 'string'
          ? { name: p.profile.name, avatar: Number(p.profile.avatar) || 0, banner: Number(p.profile.banner) || 0 }
          : null,
      settings: { ...base.settings, ...(p.settings ?? {}) },
      wallet: { ...base.wallet, ...(p.wallet ?? {}) },
      collection: { ...base.collection, ...(p.collection ?? {}) },
      deck: Array.isArray(p.deck) && p.deck.length === DECK_SIZE ? p.deck : base.deck,
      commander: typeof p.commander === 'string' ? p.commander : base.commander,
      codex: { ...base.codex, ...(p.codex ?? {}) },
      campaign: { ...base.campaign, ...(p.campaign ?? {}) },
    };
  } catch {
    return base;
  }
}

interface State extends Saved {
  screen: Screen;
  mode: Mode;
  battleId: string | null;
  /** The contest in progress: rounds, ledgers, score. Null outside a match. */
  matchState: MatchState | null;
  /**
   * The tape for the match in progress. Deliberately NOT in the saved slice —
   * it is finished tapes that are worth keeping, and they go to their own
   * storage key so a bad one can never take the collection with it.
   */
  recording: MatchRecording | null;
  /**
   * A stored match driving the offline rival's draft, when one is in play.
   * Null means the rival is the ordinary scoring function.
   */
  rivalTape: MatchRecording | null;
  /**
   * How many rounds this rival actually took FROM the tape. A recording is a
   * decision sequence, not a script, so it misses often — and §10 means the
   * game must never claim more of a person than it delivered. This is what the
   * claim is made from.
   */
  rivalTapeHits: number;
  /** The current round's battle. Replaced every round. */
  log: BattleLog | null;

  // Online
  conn: ConnState;
  onlineCount: number;
  queuedCount: number;
  searching: boolean;
  match: { matchId: string; you: Side; opponent: PlayerInfo } | null;
  turnDeadline: number | null;
  notice: string | null;

  /** The computer opponent for the current vs-AI match. Always labelled as such. */
  aiOpponent: AiOpponent | null;

  /** The mission being played, if this is a campaign match. */
  missionId: string | null;
  /** What the mission just finished handed over, for the result screen. */
  lastMissionReward: { kind: string; id: string; name: string } | null;

  /** Rewards from the match just played, for the result screen. */
  lastUnlocked: Codex;
  lastRewards: { coins: number; trophies: number; cards: string[] };

  saveProfile: (name: string, avatar: number, banner: number) => void;
  setReading: (r: Reading) => void;
  setSettings: (patch: Partial<Settings>) => void;
  go: (screen: Screen) => void;
  /** Records the bracket and moves on to the name. */
  setAgeBracket: (bracket: AgeBracket) => void;
  dismissNotice: () => void;
  notify: (message: string) => void;

  // Collection
  setDeckSlot: (slot: number, unitId: string) => void;
  setCommander: (id: string) => void;
  upgradeCard: (unitId: string) => void;
  claimDaily: () => void;
  grantCards: (ids: string[]) => void;

  // Play
  connect: () => void;
  findMatch: () => void;
  cancelSearch: () => void;
  leaveMatch: () => void;
  startSolo: () => void;
  startAiMatch: (battleId?: string) => void;
  chooseBattle: (
    battleId: string,
    seed?: number,
    arena?: number,
    opponentDeck?: string[],
    opponentCommander?: string,
  ) => void;
  makePick: (unitId: string) => void;
  useRally: () => void;
  runAiPick: () => void;
  runRound: () => void;
  finishRound: () => void;
  advanceRound: () => void;
  finishMatch: () => void;
  rematch: () => void;

  // Chronicle
  openCampaign: () => void;
  toggleCounterHistory: () => void;
  openMission: (missionId: string) => void;
  startMission: (missionId: string) => void;
  takeMissionChoice: (missionId: string, choiceId: string) => void;
}

/**
 * Applies a campaign reward to the collection.
 *
 * Cards, traits and doctrines land here as owned content. Commanders and capital
 * pieces live on the campaign state instead. Nothing in this function changes a
 * number on a card — v0.1 §5.1: campaign rewards unlock breadth of choice and
 * must not create a statistical advantage in ranked.
 */
function grantReward(collection: Collection, reward: MissionReward | null): Collection {
  if (!reward) return collection;
  if (reward.kind === 'commander' || reward.kind === 'capital') return collection;
  const existing = collection[reward.id];
  return {
    ...collection,
    [reward.id]: existing ? { ...existing, count: existing.count + 1 } : { count: 1, level: 1 },
  };
}

function rewardName(reward: MissionReward): string {
  switch (reward.kind) {
    case 'card':
      return getUnit(reward.id).name;
    case 'upgrade':
      return getUpgrade(reward.id).name;
    case 'doctrine':
      return getDoctrine(reward.id).name;
    case 'commander':
      return getCommander(reward.id).name;
    case 'capital':
      return capitalById.get(reward.id)?.name ?? reward.id;
  }
}

function randomSeed(): number {
  return Math.floor(Math.random() * 0xffffffff) >>> 0;
}

function savedSlice(s: State): Saved {
  return {
    profile: s.profile,
    ageBracket: s.ageBracket,
    reading: s.reading,
    settings: s.settings,
    wallet: s.wallet,
    collection: s.collection,
    deck: s.deck,
    commander: s.commander,
    trophies: s.trophies,
    bestTrophies: s.bestTrophies,
    wins: s.wins,
    losses: s.losses,
    codex: s.codex,
    campaign: s.campaign,
    lastDailyClaim: s.lastDailyClaim,
  };
}

export const useGame = create<State>((set, get) => {
  const persist = (): void => {
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify(savedSlice(get())));
    } catch {
      // Private browsing or a full quota. Losing progress is survivable; crashing is not.
    }
  };

  return {
    ...load(),
    // The gate comes before the name, because the answer decides whether a name
    // may be typed at all. An existing save with a profile but no bracket is
    // from before the gate existed — it is asked once, then never again.
    screen: !load().ageBracket ? 'age' : load().profile ? 'lobby' : 'profile',
    mode: 'ai',
    battleId: null,
    matchState: null,
    recording: null,
    rivalTape: null,
    rivalTapeHits: 0,
    log: null,

    conn: 'idle',
    onlineCount: 0,
    queuedCount: 0,
    searching: false,
    match: null,
    turnDeadline: null,
    notice: null,
    aiOpponent: null,
    missionId: null,
    lastMissionReward: null,
    lastUnlocked: { battles: [], kings: [], units: [] },
    lastRewards: { coins: 0, trophies: 0, cards: [] },

    saveProfile: (rawName, avatar, banner) => {
      // A player who may not type their own name gets an assigned one whatever
      // arrives here — the restriction is enforced at the store, not only in the
      // screen that happens to be showing.
      const bracket = get().ageBracket ?? 'child';
      // A restricted player still CHOOSES, from the shuffle — so an assigned
      // name that arrives here is kept. Only something they could not have been
      // offered is replaced, which is what makes this an enforcement point
      // rather than a second, contradictory name generator.
      const name = mayTypeOwnName(bracket)
        ? sanitizeName(rawName) || 'Player'
        : isAssignedName(rawName)
          ? rawName
          : assignedName(avatar * 31 + banner * 7);
      set({ profile: { name, avatar, banner }, screen: 'lobby' });
      persist();
      get().connect();
    },

    setReading: (reading) => {
      set({ reading });
      persist();
    },

    setSettings: (patch) => {
      set({ settings: { ...get().settings, ...patch } });
      persist();
    },

    setAgeBracket: (bracket) => {
      set({ ageBracket: bracket, screen: get().profile ? 'lobby' : 'profile' });
      persist();
    },

    go: (screen) => set({ screen }),
    dismissNotice: () => set({ notice: null }),
    notify: (notice) => set({ notice }),

    // ---------------------------------------------------------------- collection

    setDeckSlot: (slot, unitId) => {
      const deck = [...get().deck];
      const existing = deck.indexOf(unitId);
      // Already in the deck elsewhere: swap the two slots rather than duplicating.
      if (existing >= 0 && existing !== slot) deck[existing] = deck[slot];
      deck[slot] = unitId;
      set({ deck });
      persist();
    },

    setCommander: (id) => {
      set({ commander: id });
      persist();
    },

    upgradeCard: (unitId) => {
      const { collection, wallet } = get();
      const card = collection[unitId];
      if (!card || !canUpgrade(card, wallet.coins)) return;
      set({
        collection: { ...collection, [unitId]: { count: card.count - cardsToUpgrade(card.level), level: card.level + 1 } },
        wallet: { ...wallet, coins: wallet.coins - coinsToUpgrade(card.level) },
      });
      persist();
    },

    claimDaily: () => {
      const today = new Date().toISOString().slice(0, 10);
      if (get().lastDailyClaim === today) {
        set({ notice: 'You have already claimed today. Come back tomorrow.' });
        return;
      }
      const { wallet } = get();
      set({
        wallet: { coins: wallet.coins + 500, gems: wallet.gems + 5 },
        lastDailyClaim: today,
        notice: 'Daily reward claimed: 500 coins and 5 gems.',
      });
      persist();
    },

    grantCards: (ids) => {
      const collection = { ...get().collection };
      for (const id of ids) {
        const existing = collection[id];
        collection[id] = existing ? { ...existing, count: existing.count + 1 } : { count: 1, level: 1 };
      }
      set({ collection });
      persist();
    },

    // ---------------------------------------------------------------------- play

    connect: () => {
      const { profile, trophies } = get();
      // The arena travels with the identity: the server needs it to pick the
      // match's pool, and it re-sends on every reconnect.
      if (profile) {
        net.connect({
          name: profile.name,
          avatar: profile.avatar,
          arena: arenaForTrophies(trophies),
          deck: get().deck,
          commander: get().commander,
        });
      }
    },

    findMatch: () => {
      // Always land on the matchmaking screen. If the server is unreachable, or
      // nobody else is queued, that screen falls back to the computer rather
      // than leaving the player staring at a spinner — which is the normal case
      // until there is a real player base.
      set({ searching: get().conn === 'online', screen: 'matchmaking', mode: 'online' });
      if (get().conn === 'online') net.send({ t: 'queue' });
    },

    cancelSearch: () => {
      net.send({ t: 'cancelQueue' });
      set({ searching: false, screen: 'lobby' });
    },

    leaveMatch: () => {
      net.send({ t: 'leaveMatch' });
      set({ match: null, searching: false, turnDeadline: null, screen: 'lobby' });
    },

    startSolo: () => set({ mode: 'ai', screen: 'scenario', match: null, aiOpponent: null }),

    startAiMatch: (battleId) => {
      const s = get();
      const pick = battleId ?? content.battles[Math.floor(Math.random() * content.battles.length)].id;
      const seed = randomSeed();
      set({
        mode: 'ai',
        match: null,
        searching: false,
        aiOpponent: makeOpponent(seed, arenaForTrophies(s.trophies)),
      });
      get().chooseBattle(pick, seed);
    },

    chooseBattle: (battleId, seed, arena, opponentDeck, opponentCommander) => {
      const battle = getBattle(battleId);
      const useSeed = seed ?? randomSeed();
      const s = get();
      // Offline the arena is the player's own rung; online the server decides it
      // (the lower of the two) and sends it with the match.
      const useArena = clampArena(arena ?? arenaForTrophies(s.trophies));
      const mySide: Side = s.mode === 'online' && s.match ? s.match.you : 'a';
      const theirSide: Side = mySide === 'a' ? 'b' : 'a';

      const pool = draftPool(battle, useArena).map((u) => u.id);
      const decks = { a: [] as string[], b: [] as string[] };
      decks[mySide] = s.deck;
      // The computer has no collection, and an online opponent's warband arrives
      // with the match. Either way the deck only seeds slot A of the offer, so a
      // missing one costs variety rather than fairness.
      decks[theirSide] = opponentDeck ?? improviseDeck(pool, useSeed, DECK_SIZE);

      // The opponent leads with the other commander, so a match is always a
      // contest between the two kits rather than a mirror.
      const commanders = { a: '', b: '' } as Record<Side, string>;
      commanders[mySide] = s.commander;
      commanders[theirSide] = opponentCommander ?? (s.commander === 'cyrus' ? 'astyages' : 'cyrus');

      const opened = startMatch(battle, useSeed, useArena, decks, commanders);
      // Only offline, and only from a tape of this same battle and arena — the
      // draft pool is a function of both, so a tape from anywhere else would
      // miss nearly every round and leave the label lying.
      const tape =
        s.mode === 'ai' ? chooseTape(loadRecordings(), battleId, useArena, useSeed) : null;
      set({
        battleId,
        matchState: opened,
        recording: beginRecording(opened, mySide),
        rivalTape: tape,
        rivalTapeHits: 0,
        log: null,
        screen: 'battle',
        // Every vs-AI match gets a named opponent, so the board always has a
        // face across it even when nobody else is online.
        aiOpponent:
          s.mode === 'ai' ? (s.aiOpponent ?? makeOpponent(useSeed, arenaForTrophies(s.trophies))) : null,
      });
    },

    makePick: (unitId) => {
      const { matchState, mode, match } = get();
      if (!matchState || matchState.phase !== 'offer') return;
      const mySide: Side = mode === 'online' && match ? match.you : 'a';
      if (matchState.picked[mySide] !== null) return;
      if (!matchState.offers[mySide].some((c) => c.id === unitId)) return;

      if (mode === 'online') {
        // Never apply optimistically: the server's echo is what advances both
        // clients, so they can never drift apart mid-round.
        net.send({ t: 'pick', unitId });
        return;
      }

      const after = choose(matchState, mySide, unitId);
      set({ matchState: after });
      if (bothChosen(after)) get().runRound();
    },

    /** Comeback B. Visible, once, and only while you are behind. */
    useRally: () => {
      const { matchState, mode, match } = get();
      if (!matchState) return;
      const mySide: Side = mode === 'online' && match ? match.you : 'a';
      if (mode === 'online') {
        net.send({ t: 'rally' });
        return;
      }
      set({ matchState: spendRally(matchState, mySide) });
    },

    runAiPick: () => {
      const { matchState, mode, aiOpponent, rivalTape, rivalTapeHits } = get();
      if (mode !== 'ai' || !matchState || matchState.phase !== 'offer') return;
      if (matchState.picked.b !== null) return;

      // A recorded rival plays back what a PERSON took, and falls back to the
      // scoring function whenever that card is not on the offer it faces —
      // which is the common case, not the exception. The hit is counted so the
      // game can say afterwards how much of the rival was really a person.
      const decision = rivalTape
        ? recordedRivalPick(rivalTape, matchState, 'b', () =>
            aiRoundPick(matchState, 'b', aiOpponent ?? undefined),
          )
        : { cardId: aiRoundPick(matchState, 'b', aiOpponent ?? undefined), recorded: false };

      const after = choose(matchState, 'b', decision.cardId);
      set({
        matchState: after,
        rivalTapeHits: rivalTapeHits + (decision.recorded ? 1 : 0),
      });
      if (bothChosen(after)) get().runRound();
    },

    /** Both cards are in. Fold them into the ledgers and fight the round. */
    runRound: () => {
      const { matchState, battleId } = get();
      if (!matchState || !battleId || !bothChosen(matchState)) return;
      const battle = getBattle(battleId);
      // Recorded BEFORE the commit — the only moment both picks and the reroll
      // counts that produced them are still on the state; nextRound clears the
      // rerolls and the offer they derived is then unreproducible.
      const { recording } = get();
      if (recording) set({ recording: recordRound(recording, matchState) });
      const committed = commitPicks(matchState);
      const squadFor = (side: Side): Squad => {
        const c = getCommander(committed.commanders[side]);
        return {
          side,
          units: committed.ledgers[side].squads,
          doctrines: committed.ledgers[side].doctrines,
          passive: c.passive.id,
          order: c.order.id,
        };
      };
      const squadA = squadFor('a');
      const squadB = squadFor('b');
      // One seed per round, derived from the match seed — so both clients watch
      // the identical fight without the server ever simulating one.
      const roundSeed = roundSeedFor(matchState.seed, matchState.round);
      const log = simulate(battle, squadA, squadB, roundSeed, committed.round);
      set({ matchState: committed, log, turnDeadline: null });
    },

    /** Playback reached the end of the round's log. Score it. */
    finishRound: () => {
      const { matchState, log } = get();
      if (!matchState || !log || matchState.phase !== 'battle') return;
      const scored = scoreRound(matchState, log.winner, log.remaining);
      set({ matchState: scored });
      if (scored.phase === 'over') get().finishMatch();
    },

    /** Dismiss the round banner and open the next round's offer. */
    advanceRound: () => {
      const { matchState } = get();
      if (!matchState || matchState.phase !== 'roundResult') return;
      set({ matchState: nextRound(matchState), log: null });
    },

    finishMatch: () => {
      const s = get();
      const { battleId, matchState, log } = s;
      if (!battleId || !matchState || !log) return;
      const battle = getBattle(battleId);

      // Keep the tape. Its own storage key, and failure there is swallowed —
      // a recording is the one thing in this app that is safe to lose, and it
      // must never be able to cost somebody their collection.
      if (s.recording) saveRecording(s.recording);

      const mySide: Side = s.mode === 'online' && s.match ? s.match.you : 'a';
      const mission = matchState.missionId ? getMission(matchState.missionId) : null;
      // A mission is judged on its own objective, not on who took more rounds —
      // which is the whole point of the survival missions.
      const won = mission
        ? missionSucceeded(mission, matchState.score, mySide)
        : winnerOf(matchState) === mySide;

      const unitIds = allFielded(matchState);
      const newBattles = [battle.id].filter((id) => !s.codex.battles.includes(id));
      const newKings = battle.kings.filter((id) => !s.codex.kings.includes(id));
      const newUnits = unitIds.filter((id) => !s.codex.units.includes(id));

      const trophies = applyTrophyDelta(s.trophies, won);
      const coins = won ? COINS_WIN : COINS_LOSS;
      const cards = rollCardReward(arenaForTrophies(trophies), matchState.seed, won ? 3 : 1);

      const collection = { ...s.collection };
      for (const id of cards) {
        const existing = collection[id];
        collection[id] = existing ? { ...existing, count: existing.count + 1 } : { count: 1, level: 1 };
      }

      // Campaign rewards unlock BREADTH — a card, a trait, a doctrine, a
      // commander, a piece of the capital. v0.1 §5.1 forbids them from creating
      // a statistical advantage, so none of them touches a stat.
      //
      // Counter-History pays NOTHING. It is a second reading of the same book,
      // not a second helping, and an outcome that did not happen should not be
      // rewarded. `completeMission` already refuses to record it; this is the
      // other half, and without it the grant happened anyway.
      const pays = Boolean(mission) && won && !s.campaign.counterHistory;
      const reward = pays ? rewardFor(mission!) : null;
      const campaign = mission && won ? completeMission(s.campaign, mission.id) : s.campaign;

      set({
        campaign,
        lastMissionReward: reward ? { ...reward, name: rewardName(reward) } : null,
        codex: {
          battles: [...s.codex.battles, ...newBattles],
          kings: [...s.codex.kings, ...newKings],
          units: [...s.codex.units, ...newUnits],
        },
        lastUnlocked: { battles: newBattles, kings: newKings, units: newUnits },
        lastRewards: { coins, trophies: trophies - s.trophies, cards },
        collection: grantReward(collection, reward),
        wallet: { ...s.wallet, coins: s.wallet.coins + coins },
        trophies,
        bestTrophies: Math.max(s.bestTrophies, trophies),
        wins: s.wins + (won ? 1 : 0),
        losses: s.losses + (won ? 0 : 1),
        screen: 'result',
      });
      persist();
    },

    // ----------------------------------------------------------- the Chronicle

    openCampaign: () => set({ screen: 'campaign' }),

    /** Counter-History. Refuses to open until the historical book is finished. */
    toggleCounterHistory: () => {
      const c = get().campaign;
      if (!c.counterHistory && !bookFinished(c)) {
        set({ notice: 'Finish the book the way it happened first.' });
        return;
      }
      set({ campaign: setCounterHistory(c, !c.counterHistory) });
      persist();
    },
    openMission: (missionId) => set({ missionId, screen: 'mission' }),

    startMission: (missionId) => {
      const mission = getMission(missionId);
      const s = get();
      const seed = randomSeed();
      const battle = getBattle(mission.scenario);
      // A mission is fought at the player's own rung, so the pool grows with the
      // player rather than being frozen at whatever the story says.
      const arena = arenaForTrophies(s.trophies);
      const pool = draftPool(battle, arena).map((u) => u.id);
      set({
        mode: 'ai',
        match: null,
        missionId,
        aiOpponent: makeOpponent(seed, arena),
        battleId: mission.scenario,
        log: null,
        screen: 'battle',
        matchState: startMatch(
          battle,
          seed,
          arena,
          { a: s.deck, b: improviseDeck(pool, seed, DECK_SIZE) },
          { a: s.commander, b: s.commander === 'cyrus' ? 'astyages' : 'cyrus' },
          { winsNeeded: mission.winsNeeded, missionId },
        ),
      });
    },

    /** A non-battle mission: the branch IS the outcome. */
    takeMissionChoice: (missionId, choiceId) => {
      const s = get();
      const mission = getMission(missionId);
      // Counter-History pays nothing here either.
      const reward = s.campaign.counterHistory ? null : rewardFor(mission, choiceId);
      const campaign = completeMission(s.campaign, missionId, choiceId);
      set({
        campaign,
        collection: grantReward(s.collection, reward),
        lastMissionReward: reward ? { ...reward, name: rewardName(reward) } : null,
        missionId,
        screen: 'result',
        matchState: null,
        recording: null,
        rivalTape: null,
        rivalTapeHits: 0,
        log: null,
      });
      persist();
    },

    rematch: () => {
      const { mode, battleId } = get();
      if (mode === 'online') {
        get().findMatch();
        return;
      }
      // A rematch draws a fresh opponent, so it does not feel like the same
      // person is sitting there forever.
      get().startAiMatch(battleId ?? undefined);
    },
  };
});

// Exposed for debugging and for the browser-side verification pass. Harmless in
// production: it is the same state the UI already renders.
if (typeof window !== 'undefined') {
  (window as unknown as { game: typeof useGame }).game = useGame;
}

/** Convenience selectors used across the collection and lobby screens. */
export function ownedUnitIds(collection: Collection): string[] {
  return Object.keys(collection);
}

export function cardLevel(collection: Collection, unitId: string): number {
  return collection[unitId]?.level ?? 1;
}

export function isMaxed(collection: Collection, unitId: string): boolean {
  return (collection[unitId]?.level ?? 1) >= MAX_CARD_LEVEL;
}

export function totalCardsCollected(collection: Collection): number {
  return Object.keys(collection).length;
}

export const TOTAL_UNIT_CARDS = content.units.length;
export const TOTAL_SPELL_CARDS = content.spells.length;

// ------------------------------------------------------------------- networking

net.onState((conn) => {
  useGame.setState({ conn });
  if (conn !== 'online' && useGame.getState().searching) useGame.setState({ searching: false });
});

net.onMessage((msg: ServerMessage) => {
  const state = useGame.getState();

  switch (msg.t) {
    case 'welcome':
    case 'stats':
      useGame.setState({ onlineCount: msg.online, queuedCount: msg.queued });
      break;

    case 'queued':
      useGame.setState({ searching: true });
      break;

    case 'queueCancelled':
      useGame.setState({ searching: false });
      break;

    case 'match':
      useGame.setState({
        mode: 'online',
        searching: false,
        match: { matchId: msg.matchId, you: msg.you, opponent: msg.opponent },
      });
      // The server owns the seed AND the arena, so both clients build the
      // identical pool without trusting each other. The opponent's warband comes
      // with it so this client can derive their offers as well.
      state.chooseBattle(msg.battleId, msg.seed, msg.arena, msg.opponentDeck, msg.opponentCommander);
      break;

    case 'roundOpen':
      useGame.setState({ turnDeadline: msg.deadline });
      break;

    case 'rallied': {
      const s2 = useGame.getState();
      if (s2.matchState) useGame.setState({ matchState: spendRally(s2.matchState, msg.side) });
      break;
    }

    case 'roundPicks': {
      // Both choices arrive together. Applying them in a fixed side order keeps
      // the two clients' state byte-identical.
      const s0 = useGame.getState();
      const m = s0.matchState;
      if (!m || m.round !== msg.round || m.phase !== 'offer') break;
      const applied = choose(choose(m, 'a', msg.picks.a), 'b', msg.picks.b);
      useGame.setState({ matchState: applied });
      if (bothChosen(applied)) s0.runRound();
      break;
    }

    case 'opponentLeft': {
      const s1 = useGame.getState();
      // Mid-match there is no way to finish: the opponent's future picks are
      // gone. Before the first round is fought nothing has been earned either,
      // so the honest thing is to return to the lobby and say so.
      if (s1.screen === 'battle' || s1.screen === 'matchmaking') {
        useGame.setState({
          match: null,
          matchState: null,
          recording: null,
          rivalTape: null,
          rivalTapeHits: 0,
          log: null,
          searching: false,
          turnDeadline: null,
          screen: 'lobby',
          notice: 'Your opponent left the match.',
        });
      }
      break;
    }

    case 'error':
      useGame.setState({ notice: msg.message });
      break;
  }
});
