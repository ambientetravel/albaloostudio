#!/usr/bin/env python3
"""
Persia at War inventory seed for the external-analyst bridge.

Why this exists: the same reason `build_seed.py` exists for the websites. Across
three manifests the external model proposed a fabricated date, schema that was
already live, and content that was already built — every time because it could
not see what existed. A game is worse, not better: an analyst asked to improve a
game it cannot play will propose the feature you shipped last week.

So this generates, from the repo itself, a factual map of what IS built, what
was MEASURED, what was DECIDED and why, and what is off-limits. Read-only. Run
it before any handoff so the numbers are the current ones.

    python3 orchestrator/bridge/inventory/build_game_seed.py
"""
import json, pathlib, re, subprocess, datetime

ROOT = pathlib.Path(__file__).resolve().parents[3]
GAME = ROOT / 'persia-wars-game'
DATA = GAME / 'src' / 'content' / 'data'
OUT = pathlib.Path(__file__).resolve().parent / 'persia-at-war-seed.json'


def js(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def const(path, name):
    """Pull a numeric/array constant out of source, so the seed never drifts."""
    src = (GAME / path).read_text(encoding='utf-8')
    m = re.search(rf'{name}\s*=\s*([^;]+);', src)
    return m.group(1).strip() if m else None


def tests():
    try:
        r = subprocess.run(['npx', 'vitest', 'run', '--reporter=dot'], cwd=GAME,
                           capture_output=True, text=True, timeout=900)
        m = re.search(r'Tests\s+(\d+)\s+passed', r.stdout + r.stderr)
        return int(m.group(1)) if m else None
    except Exception:
        return None


units = js('units.json')
cards = [c['id'] for c in js('upgrades.json')] + [c['id'] for c in js('doctrines.json')]
arenas = js('arenas.json')
missions = js('missions.json')

have_units = {p.stem for p in (GAME / 'src/assets/units').glob('*.png')}
have_cards = {p.stem for p in (GAME / 'src/assets/cards').glob('*.png')}
have_arenas = {p.stem for p in (GAME / 'public/art/arenas').glob('*')} - {'README.md'}
# Rigs: a unit is rigged only if it is on the runtime allowlist AND has parts.
rig_dirs = {p.name for p in (GAME / 'src/assets/rig').glob('*') if (p / 'rig.json').exists()}
allow = (GAME / 'src/render/unitArt.ts').read_text()
rigged = sorted(d for d in rig_dirs if f"'{d}'," in allow or f"'{d}'\n" in allow)

seed = {
    'generated': datetime.date.today().isoformat(),
    'project': 'Persia at War — standalone educational draft + auto-battler',
    'read_this_first':
        'This is a factual map of what ALREADY EXISTS. Do not propose anything '
        'listed under built_and_working or decided_and_closed. Proposals that '
        'restate them are rejected at review as redundant, which is what '
        'happened to three earlier manifests on the website side.',

    'audience': 'Ages 9-14, especially the Iranian diaspora. NOT a Boutimar product.',
    'stack': 'React 19 + Vite 7 + TypeScript 5.7, PixiJS v8 battle canvas, Zustand. '
             'Own WebSocket matchmaking server (Node type-stripping, shares sim/roundCore.ts). '
             'NOT Unity. No C#. Suggestions requiring a Unity rewrite are out of scope.',

    'built_and_working': {
        'milestones': 'M1-M6 complete. M7 (shipping) started.',
        'round_loop': 'Up to 7 rounds, first to 4. Three-card offer, SIMULTANEOUS picks '
                      'held by the server and released together. Army Ledger persists across '
                      'rounds; battlefield resets.',
        'card_kinds': 'unit (rank/numbers), upgrade (trait/behaviour), doctrine (army-wide). '
                      'They must not do each other jobs — that is M2 and it is load-bearing.',
        'comeback': 'A: offer widens 3->4->5 with deficit. B: Rally reroll at 2 losses. '
                    'C: exhaustion ramp guarantees round termination.',
        'commanders': 'Cyrus (breadth passive) vs Astyages (early-Trained head start). '
                      'Balanced to under 55% across 200 simulated matches.',
        'rivals': 'Three offline styles — massing / drilling / planning — differing in which '
                  'card KIND they buy. Every pairing 35-65% with side advantage cancelled.',
        'recorder': 'A whole match stores as ~867 bytes of decisions and replays to a '
                    'byte-identical state. Server can therefore VERIFY a result, not trust it.',
        'campaign': f'{len(missions)} missions, Book One. Two are survive-objectives. '
                    'Counter-History unlocks after, tracks separately, pays nothing.',
        'honesty_layer': 'Every unit/battle carries evidence text, sources, disputed list and a '
                         'five-level confidence. Shown to everyone, not behind a toggle.',
        'tests_passing': tests(),
        'per_man_simulation': (
            'One ledger entry spawns a BODY OF MEN, each his own simulated unit with his '
            'own position, target and death. The squad stat line is DIVIDED among them, so '
            'head count changes how a squad looks and how it comes apart, never how strong '
            'it is. Damage is computed at squad scale by the original formula and the '
            'RESULT divided by the attacker head count — armour is a flat subtraction, so '
            'dividing atk alone made six spearmen unable to scratch a chariot. Formation '
            'depth is RENDER ONLY: x is the combat axis, and a rank standing 1.3 units back '
            'is 1.3 units out of the fight, which swamped Long Reach entirely when it was '
            'tried in the sim.'
        ),
        'head_count': (
            'units.json carries `count` per unit — Kissian levy 8, Persian archer 6, '
            'Immortal 3, war elephant 1 — multiplied by rank. Six squads is about 28 men a '
            'side at Levy and about 40 by rounds six and seven.'
        ),
        'wildcard': (
            'Some rounds a side pick counts DOUBLE, announced BEFORE the choice so it is a '
            'decision rather than a surprise. Derived from (seed, round, side, deficit) and '
            'never Math.random, because the recorder replays byte-identically and the server '
            'detects desync by comparing clients. Measured: 8.2% level, 25.7% one behind, '
            '42.5% two behind, capped 46%.'
        ),
        'skeletal_rigs': (
            f'{len(rigged)} of 25 units are cut into parts on pivots and animated: '
            + ', '.join(rigged) + '. Mounted rigs gallop (Muybridge 1878 — airborne when '
            'the legs are GATHERED, not extended); foot rigs march. The other 15 draw as '
            'still sprites on the procedural gait. Not Rive or Spine: Pixi Container is '
            'already a transform hierarchy. What a real tool would add is MESH deformation '
            'so a leg bends rather than swinging rigid.'
        ),
        'unit_identity': (
            'Every unit is a PERSON — Zarina, Artavazda, Karkish — with the contingent as '
            'subtitle. Fictional individuals, real period names, several from the Persepolis '
            'Fortification Tablets. No card is named after a specific historical person on '
            'purpose. All 25 fit the 9-character Army Ledger ceiling.'
        ),
        'board_is_a_carpet': (
            'The battle floor carries a Pazyryk-derived border in the surround (5th-4th c. '
            'BCE, the only carpet contemporary with these arenas). Pattern in the FRAME, '
            'quiet field, because a carpet is identified by its borders and because units '
            'draw at 22-85px. The carpet is the BOARD, not terrain — nobody fought on a rug.'
        ),
    },

    'measured_not_guessed': {
        'escalation': 'Army power 4.0 (round 1) -> 21.6 (round 7) = 5.38x, increments '
                      '+2.8 +2.4 +2.5 +2.9 +3.2 +3.8. Was 4.52x flat before a fix.',
        'match_length': 'Of 60 measured matches, 42 reached round 5, only 10 reached round 7. '
                        'Average final army 4.63 squads against a cap of 6. The designed '
                        'climax round happens in about one match in six.',
        'reference_game_comparison': 'The mobile game this takes its shape from offers cards '
                                     'worth +2 to +5 units early and +5 to +8 late, with armies '
                                     'reaching 40+. Its picks ALTERNATE; ours are simultaneous.',
        'constants': {
            'TIER_MULT': const('src/sim/roundCore.ts', 'TIER_MULT'),
            'MAX_SQUADS': const('src/sim/roundCore.ts', 'MAX_SQUADS'),
            'WINS_NEEDED': const('src/sim/roundCore.ts', 'WINS_NEEDED'),
            'ROUNDS_MAX': const('src/sim/roundCore.ts', 'ROUNDS_MAX'),
        },
    },

    'decided_and_closed': [
        'No age gate. Removed deliberately — the audience is 9-14, so an adult path served '
        'nobody and existed only to grant the one privilege carrying all the risk.',
        'Nobody types a name. All 144 display names come from a closed set the SERVER checks '
        'membership against, so no profanity list is needed in any language.',
        'No kid/older reading toggle. It was the evidence layer and it defaulted to off — '
        '24 of 25 units cited a source in the long text and 1 of 25 in the short one.',
        'No screen shake, no hit-stop. The reference game has neither.',
        'Simultaneous picks, not alternating. Load-bearing for server offer-validation and '
        'desync detection. Changing it is a real decision, not a tweak.',
        'Dark Achaemenid palette — ochre, oxblood, lapis, gold. Not up for a brightening pass.',
    ],

    'designed_but_not_built': {
        'commanders_v03': (
            'NINE commanders agreed with kits and campaigns — Cyrus, Darius, Surena, '
            'Shapur I, Rostam Farrokhzad, Babak Khorramdin, Yaqub ibn al-Layth, Shah Ismail '
            'I, Nader Shah. Four of the nine end in DEFEAT. Only Cyrus and Astyages exist in '
            'code. Balance cost: 36 pairings, and the harness plays both sides, so 72 sweeps.'
        ),
        'anjoman': (
            'انجمن فرزانگان — giants of Persian science and poetry as powers, each derived '
            'from actual work (Biruni measured, so he SEES; Ferdowsi kept Persian alive, so '
            'he brings back a lost squad; Hafez rerolls because the fal IS a reroll). The '
            'PLAYER visits, not the commander, which is what makes the 1,500-year gap honest.'
        ),
        'women': (
            'Artemisia I (real via Herodotus, Carian Greek NOT Persian, kit is refusing a '
            'round) and Purandokht (Sasanian queen regnant with coins, five years before '
            'Qadisiyya). Four famous names are EXCLUDED as unsourced modern inventions — '
            'Pantea Arteshbod, Apranik, Youtab, Artemisia-as-Persian.'
        ),
        'festivals': 'Client-computable from the calendar, so no server. Blocked on accounts.',
    },
    'art_status': {
        'units': f'{len(have_units)}/{len(units)}',
        'cards': f'{len(have_cards)}/{len(cards)}',
        'arenas': f'{len(have_arenas)}/{len(arenas)}',
        'commanders': '0/2', 'capital': '0/5', 'kings': '0/4', 'missions': f'0/{len(missions)}',
        'note': 'Prompts already written for units, cards and arenas. Do not write more prompts.',
    },

    'open_questions_where_outside_view_helps': [
        'Why would a 10-year-old stop playing at round 3? Adversarial critique of the loop.',
        'Genre teardown with LIVE retrieval — what is actually working now in the '
        'Clash-Royale-like / auto-battler space. This is the one surface we are blind to.',
        'Educational-game conventions for 9-14: session length, reading load, what holds them.',
        'Soft-launch strategy: markets, store category, comparable titles, ASO.',
        'Retention: we have no daily loop worth the name beyond a daily reward.',
    ],

    'do_not_route_here': [
        'Balance numbers. We measure with harnesses and 248 tests; an opinion about TIER_MULT '
        'that has not run the sweep is noise.',
        'ANY historical claim. A general model will confidently assert the Cyrus Cylinder is a '
        'charter of human rights — a claim our own mustNotClaim names explicitly and bans. '
        'History goes to a historian, never to an LLM.',
        'Code review, refactors, test strategy.',
        'Art prompts — written already for units, cards and arenas.',
        'Anything requiring Unity or a rewrite.',
    ],

    'hard_rules_on_anything_returned': [
        'Persian Gulf. Never Arabian Gulf. Every label, map and codex line.',
        'Never invent a date, a figure, a source or an attribution.',
        'The book-level mustNotClaim list applies to any text it writes — especially the '
        'Cyrus Cylinder human-rights framing, Cyrus being young at the revolt, and the '
        'exposure-and-shepherd story being biography.',
        'Medes are not villains. This is an Iranian dynastic war, not a clash of civilisations.',
        'Audience 9-14: no gore, no dismemberment, no ethnic caricature.',
        'No modern political reading, in either direction.',
    ],
}

OUT.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'wrote {OUT.relative_to(ROOT)}')
for k in ['units', 'cards', 'arenas']:
    print(f"  art {k}: {seed['art_status'][k]}")
print(f"  tests passing: {seed['built_and_working']['tests_passing']}")
