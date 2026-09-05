# Giving Persia at War its own repo

**Status: the hard part is done.** The history is split and waiting on a local
branch. What is left is one click and two commands, both of which need your
GitHub account.

## Why it has to move, in the order the reasons actually matter

1. **Access control, and this is the whole reason.** To let ASTRA or Codex open
   a PR on the game, you must grant it repo access to whatever repo the game is
   in. Today that is `albaloostudio` — which holds the travel business's agent
   orchestration, provider configuration, compliance rules and property paths.
   **Granting an outside agent access to the game currently means granting it
   read of the entire travel operation.** No amount of gate tuning fixes that;
   it is a repository boundary problem and only a repository fixes it.
2. **The game is explicitly not a Boutimar product.** That is a standing rule of
   the project, and it currently lives inside the travel company's orchestrator.
3. **It is the largest thing in there** — 284 tracked files against the
   orchestrator's 80. The tail is wagging the dog.
4. **It cannot be cleanly extracted later.** Every month it stays, more history
   interleaves. Today the separation is clean: of 52 commits touching the game,
   exactly one also touches anything else, and that one file is
   `.claude/launch.json`.
5. CI noise — `.github/workflows` there are travel agent workflows that have no
   business running on a game PR.

## What is already done

    git subtree split --prefix=persia-wars-game -b persia-at-war-standalone

- **52 commits**, full history, every message intact.
- **284 files**, verified: `src/sim` 16, `src/render` 6, `src/assets/units` 25,
  `src/assets/rig` 77, `src/content/data` 13, `docs` 17, `tools/rig` 2.
- The game is at the ROOT of that branch — `src/`, not `persia-wars-game/src/`.

## What only you can do

**1. Create an empty repo.** No README, no .gitignore, no licence — an empty
repo, or the first push needs a merge.

Suggested: **`ambientetravel/persia-at-war`**. The owner is genuinely your call:
`ambientetravel` keeps everything under one account, but the game is not an
Ambiente Tours product and a separate owner would say so. If you pick another
name, change `GAME_REPO` at the top of `tools/pr_review.py` — it is one line and
nothing else references it.

**2. Push the branch to it.**

```bash
cd "/Users/alimozzy/claude websitebuilder"
git push https://github.com/ambientetravel/persia-at-war.git persia-at-war-standalone:main
```

**3. Clone it somewhere outside this folder** and work there from then on.

```bash
git clone https://github.com/ambientetravel/persia-at-war.git ~/persia-at-war
cd ~/persia-at-war && npm install && npx vitest run
```

275 tests should pass. **That is the check that the split worked** — if the
suite is green out of a fresh clone, nothing was left behind.

**4. Only then, remove it from albaloostudio.** Not before. Until the clone is
verified green there are two copies, which is the point: the old one is the
backup, and deleting a backup before testing the restore is how backups fail.

## What changes on the bridge

Nothing structural. `pr_review.py` already lists the new repo and judges it under
`persia_at_war_v1`, so the moment the repo exists the gate covers it:

    python3 tools/pr_review.py --repo ambientetravel/persia-at-war --pr 1

The `persia-wars-game/` path rule stays until the move is done, then stops
matching anything and can be deleted.

**And ASTRA's grant becomes the narrow one it should have been:** PR access to
the game repo, and nothing else. Never admin, never merge, never
write-to-default.
