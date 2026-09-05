# Mass, rank, and the comeback — what is built, what is new, what conflicts

*Answering the round-structure proposal. Three of the nine asks already exist,
four are now built, one needs a constraint, and one is a genuine trade-off that
cannot be had both ways.*

## Already in the game

**Comeback bonuses — there are THREE, and they already fire.** This was the
largest single ask and it is done:

| | mechanic | what it does |
|---|---|---|
| **A** | `offerSizeForDeficit` | behind by 1 → **4 cards offered** instead of 3. Behind by 2 → **5** |
| **B** | the **Rally** | rounds lost since your last win; at the threshold you hold a free reroll, and winning empties the meter |
| **C** | `COUNTER_WEIGHT_TRAILING` | when behind, the offer is weighted harder toward cards that **counter what the opponent actually has** |

Worth naming the difference from what was asked for: **all three give you better
OPTIONS. A ×2 would give you more POWER.** Both are legitimate and they feel
completely different — one rewards choosing well, the other just hands you a
bigger number. See the wildcard section below.

**Upgrades already tier through the rounds.** `TIER_MULT = [1, 1.25, 1.55, 1.9]`,
and `tierCapForRound` raises the ceiling as the match runs. In play the card
comes up as **"→ Trained II"** on a unit you already hold — the exact "normal
Rausha, then better Rausha" progression, already working.

**Offers are already symmetric.** Both sides draw `OFFER_SIZE = 3` from the same
derived pool, and the server validates each pick against offers it derives
itself. The **only** asymmetry is the comeback, which is deliberate.

## Built now

**Squads are files of men.** `FILES_BY_TIER = [2, 3, 4, 6]` — a Levy squad draws
two men, a fully drilled one draws six. **Six squads at the cap is 36 a side**,
which is the density asked for.

**Rank is now visible, and it cost no art.** Three upgrade paintings for each of
25 units would have been **75 new images**. Drawing the same figure two, three,
four or six times, with rear ranks slightly smaller and dimmer for depth, reads
as "this squad got stronger" for **zero** new assets.

**Attrition.** Men fall out of the file as the squad's HP drops. A squad that is
nearly dead now *looks* nearly dead from across the board, which the health bar
never managed at this size.

**Wind.** Every man carries his own phase, so a line **ripples** across rather
than tilting as one slab — that is the whole difference between wind and a
wobble. It runs off `elapsedTicks`, not a clock, so it stays inside the rule that
nothing in the render may make two machines disagree.

## SUPERSEDED — the sim DID change

*Everything below this line up to the trade-off section was written before the
per-man simulation was built, and the constraint it defends no longer holds.*

**One ledger entry is now a body of individually simulated men.** Each has his
own position, his own target and his own death.

**The three attempts it took, because each failure was informative:**

1. **Full stats per man.** Army strength scaled with head count, so a Kissian
   levy (8 men) was eight times a war elephant (1) at the same rank, and a
   tier-3 archer beat the cavalry that counters it **forty times out of forty**.
   Head count had quietly outranked the counter triangle, which is the one thing
   the game is built to teach.
2. **Divide atk and def per man.** Armour is a FLAT subtraction, so six spearmen
   each swinging for a sixth could not scratch a chariot — chariots went from
   losing a gorge to winning every seed of it. Fixed by computing the squad's
   whole blow with the original formula and dividing the RESULT by the
   attacker's head count.
3. **Formation depth in the sim.** x is the combat axis, so a rank standing 1.3
   units back is 1.3 units out of the fight — and a spear reaches about 1.5, so
   **Long Reach's entire advantage was swamped by the formation it stood in.**
   Depth now lives in the renderer, exactly as `lane` always did.

**Balance after, measured:** massing/planning **52.2%**, drilling/massing
**40.6%**, drilling/planning **43.3%** — all inside the 35–65% band and barely
moved from 54.2 / 41.1 / 44.4 before. Escalation 5.38× → 5.77×.

**What it cost:** the suite went from 1.6s to 7.2s, and that is after making the
targeting scan only living enemies. The sim does roughly seven times the work.

**And one thing I had argued that was simply wrong:** I claimed real entities
would be too expensive on a phone. Draft Showdown runs about thirty of them
without trouble. The performance objection did not hold; the balance cost was
real, and it was a cost rather than a blocker.

## The old constraint, kept for the record: the sim does not change

**A ledger entry is still ONE SimUnit with one HP pool. The extra men are
cosmetic.** This is not a shortcut, it is the load-bearing decision:

- Real entities would **multiply the simulation by six** — 12 units becomes 72,
  each pathing and target-seeking every tick, on a phone.
- It would **invalidate every balance number already measured**: the 200-match
  rival-style sweeps, the 4.52×→5.38× escalation curve, all three commander
  passives.
- It would **six-fold the desync surface** the server checks both clients
  against.

Nothing in the ask actually required real entities. What was wanted was for the
board to *look* like armies, and it now does.

## The wildcard ×2 — yes, with one condition

> *"a wild card of ×2 for no reason just to make it fun"*

**It must be derived from the round seed.** Not `Math.random()`. The recorder
replays a match byte-identically from a few hundred bytes of decisions, and the
server detects desync by comparing both clients — a genuinely random multiplier
breaks both, silently, and the failure would show up as players being
disconnected mid-match for no visible reason.

Seeded, it is free and it works: both clients roll the same wildcard, the tape
replays it exactly, nothing else has to change.

**The design caution, stated once and then dropped.** In a first-to-4, a random
×2 makes the game less about what you chose. That is the trade these games make
on purpose — it is a real part of why they are sticky — but it argues *against*
the comeback bonuses rather than alongside them, because the comebacks exist to
make losing feel recoverable through skill. **My suggestion: seed the wildcard
off the round AND the deficit**, so it fires more often for the side that is
behind. Then it is still a surprise, still fun, and it is pulling the same
direction as everything else instead of against it.

## The trade that cannot be had both ways

> *"much smaller unit sizes, and the graphic must be more revealing what they are"*

**These are opposites.** A figure drawn at 18px cannot reveal a shield boss, a
scale corselet or a bow type. That information does not fit in the pixels — the
26px ledger fight already proved it in this codebase, where six infantry at that
size were the same brown smudge.

**What actually reads at small size**, in order of strength:

1. **Silhouette** — a pointed cap, a bow taller than the man, a camel's height.
   Every one of the 25 prompts already names its silhouette hook.
2. **Formation shape** — six men in a block is instantly a different thing from
   two men, and *that* is now doing the work of "this one is upgraded."
3. **Colour** — the team ring on the ground, already there.
4. **Motion** — a horse gait against a spearman's tramp.

**So the detail moves to the card**, where the art is drawn full size and the
player is standing still looking at it. On the board, the job is *mass*.

That is the honest split, and it is the one every game in this genre lands on:
you fall in love with the card, and you read the battle.
