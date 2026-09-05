# The four steps, one at a time

Two are browser work and take a Claude-in-Chrome prompt. Two are terminal and do
not — a `git push` cannot be done from a browser, and a prompt pretending
otherwise would just waste a round trip.

Do them in order. Do not start the next until the previous one reports done.

---

## STEP 1 — create the empty repo · CLAUDE IN CHROME

> Go to https://github.com/new
>
> Fill the form exactly as follows and change nothing else:
>
> - **Owner:** `ambientetravel`
> - **Repository name:** `persia-at-war`
> - **Description:** `An educational draft and auto-battler on real Iranian history.`
> - **Visibility:** **Private**
>
> **Critical — leave the "Initialize this repository with" section completely
> untouched.** Do NOT tick Add a README. Do NOT choose a .gitignore template. Do
> NOT choose a licence. The repository must be created totally empty, because
> history is being pushed into it and any starting commit would collide.
>
> Then click **Create repository**.
>
> When the page loads, tell me:
> 1. the full repo URL,
> 2. whether the page shows the "quick setup — if you've done this kind of thing
>    before" empty-repo screen. If instead it shows a file list with a README,
>    the repo was initialised by mistake — say so and do not try to fix it.
>
> Do not run any of the git commands the page suggests. Do not create anything
> else. Do not change any account or organisation settings.

---

## STEP 2 — push the split history · TERMINAL

Not browser work. Run this in your terminal:

```bash
cd "/Users/alimozzy/claude websitebuilder" && git push https://github.com/ambientetravel/persia-at-war.git persia-at-war-standalone:main
```

**Expect:** a progress counter and `* [new branch] persia-at-war-standalone -> main`.

**If it asks for a username and password:** GitHub stopped accepting passwords
here years ago — the password field wants a Personal Access Token. This is the
same wall that has blocked `boutimarfarsi` and the eclipse branch before, so if
it appears, stop and say so rather than retrying.

---

## STEP 3 — verify by restoring, not by looking · TERMINAL

The only check that means anything is a fresh clone building green. Looking at
the file list on GitHub proves nothing about whether the split dropped something.

```bash
git clone https://github.com/ambientetravel/persia-at-war.git ~/persia-at-war && cd ~/persia-at-war && npm install && npx vitest run
```

**Expect: 275 tests passing.** If they do, the split is sound and `~/persia-at-war`
is the working copy from now on.

**Leave the old copy in `albaloostudio` until this is green.** It is the backup,
and deleting a backup before testing the restore is how backups fail.

---

## STEP 4 — grant ASTRA access · CLAUDE IN CHROME

**This is the step where a wrong click has a real cost**, so it is last and it is
narrow. Only do it after step 3 is green.

> Go to https://github.com/settings/installations
>
> Find the entry for the ChatGPT / Codex GitHub app — it may be listed under
> "Installed GitHub Apps" or under the `ambientetravel` organisation. Open its
> **Configure** page.
>
> Under **Repository access**, choose **Only select repositories**, and add
> exactly one: **`ambientetravel/persia-at-war`**.
>
> **Do not** select "All repositories". **Do not** add `albaloostudio`,
> `boutimar`, `boutimarfarsi` or `exploreorient` — the whole reason this repo was
> created was so the game could be shared without exposing those.
>
> Then read the **Permissions** section back to me before saving. I need to know
> whether it is asking for anything beyond read and write on Contents, Pull
> requests and Metadata. **If it requests Administration, or anything that
> mentions merging or branch protection, stop and tell me — do not save.**
>
> Do not change any other app's access. Do not change organisation settings.

**The boundary being defended:** an outside agent opens a pull request and
nothing more. No merge, no push to `main`, no deploy. More models proposing is
only safe because one gate reviews and one person ships — grant merge rights and
both guarantees are gone at once.
