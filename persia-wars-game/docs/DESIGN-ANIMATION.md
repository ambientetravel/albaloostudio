# Enhancing the movement — what actually moves the needle

*Answering: better sim, better movement, other tools, other models, real-time 3D.*

## The short version

**The simulation is not the bottleneck and neither is the model.** The movement
is limited by one thing: **the sprites are single still images being pushed
around by maths.** A gallop is currently a sine wave applied to a photograph of
a standing horse. No amount of better code or a smarter model fixes that — the
horse has no legs that move.

**The fix is a 2D skeletal animation pipeline on the art you already have.**
That is a tool decision, not a model decision, and it does not need new artwork.

## 3D — no, and here is the reasoning rather than the verdict

| | what it would cost |
|---|---|
| Engine | PixiJS out, three.js or Babylon in. The battle canvas is rewritten |
| Art | **All 25 units and 9 commanders re-made as rigged 3D models.** The Midjourney → Nano Banana → `spriteprep.py` pipeline becomes worthless |
| Bundle | Models, textures and skeletons are megabytes where PNGs are kilobytes — and a large part of this audience is on Iranian connections |
| Phone | 90 skinned meshes with shadows is a much harder problem than 90 sprites |
| Look | The house style is hand-painted gouache, museum illustration. That IS the identity, and it is 2D by nature |

**And the decisive one: Draft Showdown is 2D.** The game you are benchmarking
against does not use 3D, so 3D is not what you are seeing when it looks better
than ours. What you are seeing is **drawn animation frames**.

3D is not wrong forever — it is wrong for this game, at this size, with this art
direction, against this reference.

## What actually produces the difference

### 1 · Skeletal animation — the real answer

Cut each existing sprite into parts (head, torso, upper arm, forearm, thigh,
shin, weapon, horse legs), pin them to a skeleton, and animate the skeleton. A
gallop becomes a real four-beat gait instead of a bounce.

**It uses the art that already exists.** No redraw. That is the whole reason
this is the recommendation and not "commission animation".

| tool | notes |
|---|---|
| **Rive** | Web-first, small runtime, free tier, good editor. Best fit for a web game — check current pricing, it has changed before |
| **DragonBones** | Free and open, mature, runtimes for web. The budget answer |
| **Spine** | The industry standard, `pixi-spine` runtime exists, paid licence with tiers. What most games in this genre actually use |

**Realistic scope:** one rig per *silhouette*, not per unit — there are only
about eleven silhouettes (spear, shield, bow, horse, horse-bow, camel, chariot,
elephant, club, lasso). Rig eleven skeletons, then every unit sharing a
silhouette reuses one. Four clips each: idle, walk, attack, death. **That is
~44 clips, not 25 × 4.**

### 2 · Muybridge, which is free and perfect for this game

**Eadweard Muybridge, *The Horse in Motion*, 1878** — the photographic sequences
that settled whether all four hooves leave the ground in a gallop. **Public
domain.** He went on to photograph humans walking, running and carrying loads.

For a game about history, animating a Persian horse from the photographs that
founded motion study is both the correct technical reference **and its own codex
entry.** It costs nothing and it is more accurate than anything a model will
invent.

### 3 · The one simulation upgrade genuinely worth doing

**The field is one-dimensional.** Units have `x` only; `lane` is a drawing
convention the simulation cannot feel. So there is **no flanking, no wheeling,
no envelopment** — Surena's whole kit at Carrhae is horse-archers working the
flanks, and the sim cannot express it.

Giving the sim a real `y` would allow flanking, a line that can be turned, and
cavalry that goes around instead of through. **That is a genuine upgrade with
visible payoff**, and it is a bigger job than the animation: every balance
number is measured against a 1-D field.

Do the animation first. It is cheaper and it is what you are actually seeing.

## Where AI helps, and where it does not

**Does not:**
- **Generating sprite sheets.** Frame-to-frame consistency is exactly where
  image models fail — you get eight pictures of eight slightly different horses.
- **A better chat model.** Nothing about a walk cycle is bottlenecked on
  reasoning. Opus, GPT, Gemini all write the same easing function.
- **Video models** (Sora, Veo, Kling) make video, not sprite sheets with alpha
  channels and stable pivots.

**Does:**
- **Cutting a sprite into rigging parts.** Ask Nano Banana for the same
  character with the arm separated, the leg separated — that is an edit task,
  which image models are good at, rather than a generation task.
- **Turnarounds and consistent poses** from a locked `--sref`, which is already
  how the arena set was kept consistent.
- **Writing the runtime integration** once a tool is chosen.

## Recommendation, in order

1. **Pick Rive or DragonBones** and rig ONE silhouette — the horse, since a
   gallop is the most visibly wrong thing today. One rig, four clips. If it
   looks right in the battle canvas, do the other ten.
2. **Animate from Muybridge**, not from imagination.
3. **Leave the simulation alone** until the animation is done, then consider the
   2-D field for flanking.

**No new hardware is needed.** None of this is compute-bound; it is one person
in an animation editor for a few evenings per rig.
