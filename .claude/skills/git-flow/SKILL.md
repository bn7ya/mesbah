---
name: git-flow
description: Turns a feature, fix or refactor request into a GitHub issue, a branch, and a series of small commits that each work on their own. Use before writing code whenever a request adds behaviour, corrects behaviour, or restructures existing code — and this session isn't already working a pre-assigned branch for the task. Not for questions, reviews or reading.
---

# The git flow

Every feature, fix and refactor starts as a GitHub issue and lands as commits small
enough that any one of them can be checked out and run. The issue comes before the
first edit, not after the last one.

This is an **optional, available** workflow for mesbah — not the only one. A session
already working a specific pre-assigned branch for a task (the common case when
Claude Code is invoked on a scheduled/remote task) does not need to open its own
issue first; that instruction, when given, takes precedence over step 3 below.

## 1. Classify the request

| The request | Type | Label | Issue first? |
|---|---|---|---|
| Adds behaviour a user can see | `feat` | `enhancement` | Yes |
| Corrects behaviour that is wrong | `fix` | `bug` | Yes |
| Changes structure, not behaviour | `refactor` | `refactor` | Yes |
| Documentation only | `docs` | `documentation` | No |
| Tooling, dependencies, the harness | `chore` | `chore` | No |

A question, a review, a read or a piece of advice is none of these. Answer it and stop —
do not open an issue for it.

## 2. Split it into units that work

One issue is one commit is one thing that runs.

`.claude/docs/design-pattern.md` §1 says a slice touching the Django migration ships
both sides together, so never split it into a backend commit and then a frontend
commit — the first of the two is a commit you cannot return to. Split by **behaviour**
instead. Each issue is a thin vertical slice that stands up on its own:

```
#12  the projects list page    model → repository → service → view → serializer →
                                api → component
#13  filtering and sorting
#14  bulk actions
```

Check out the commit that closed `#12` and you get an application that starts, serves
a projects page, and (on the Django side) passes its checks. That is the test of a
good split, and the reason the split is worth the effort.

A change to the **live** FastAPI + Angular product (`backend/app/`) is simpler — there
is no repository/service split there — but the same "each commit runs on its own"
rule still applies.

A small request is one issue. If an issue needs an "and" to describe it, it is two.

## 3. Open the issues

Once, in a fresh clone — GitHub ships neither label:

```bash
gh label create refactor --color 5319e7 --description "Behaviour-preserving restructuring"
gh label create chore --color cfd3d7 --description "Tooling, dependencies and housekeeping"
```

Then one `gh issue create` per unit, in the order they will be built:

```bash
gh issue create --title "Add the projects list page" --label enhancement --body "$(cat <<'EOF'
## What

One paragraph: the behaviour this adds, in the words a user would use.

## Why

The problem it solves. Not the implementation.

## Slice

- Backend: `backend/apps/projects/` (Django migration target) or
  `backend/app/features/projects/` (live FastAPI product) — say which
- Frontend: `frontend/src/app/features/projects/`

## Done when

- [ ] The page loads and does what the title says
- [ ] Every touched feature directory has a current `CLAUDE.md`
- [ ] The definition of done in `.claude/docs/design-pattern.md` § 6 is met (Django side)
EOF
)"
```

Keep the issue about behaviour. The design belongs to `architect`, not to the tracker.

## 4. Cut the branch

```bash
git switch main && git pull
git switch -c feat/12-projects-page
```

`<kind>/<issue>-<two-or-three-words>`. The kind matches the commit type. The number is
the issue, and when a request became several issues it is the **lowest** of the batch —
the branch delivers the slice, the issues are its steps.

Cut from `main` (or the branch a task explicitly assigned), never from another
unrelated work branch. One slice per branch: if the name needs an "and", it is two
branches.

## 5. Build one issue at a time

Dispatch the specialists `architect` lays out. Do not open the next issue's work until
the current one is committed and pushed — half of `#13` sitting in the working tree is
what makes `#12`'s commit unreturnable.

## 6. The gate — run it before every commit

Mesbah has no `.github/workflows/ci.yml` yet — these are the closest equivalent to
what a CI gate would run, taken from each side's own `CLAUDE.md`.

```bash
# Django migration target — from backend/, with the docker-compose.django.yml stack
# up (or .venv-django activated locally, see backend/CLAUDE.md)
python manage.py makemigrations --check --dry-run \
  && python manage.py spectacular --fail-on-warn --file /dev/null \
  && python -m pytest apps \
  && ruff check .

# Live FastAPI backend — no automated test suite yet; the canonical check is the
# smoke flow described in backend/CLAUDE.md's "Verify" section, run by hand:
# project → task → session → correction → dataset → run prep → version tree →
# cascade delete.

# Frontend — from frontend/
npm run build   # must be warning-clean, per frontend/CLAUDE.md

# Harness — from the repo root
python -m compileall -q .claude/hooks
```

Also confirm by eye before you push: a `CLAUDE.md` in every `features/*/` and
`apps/*/` you touched (root `CLAUDE.md`'s convention), and — if you touched a
component's Arabic strings — that RTL still works and technical terms stayed English.

Red is not a commit. Fix it, or split the commit smaller until each half is green. Never
`--no-verify`, never "I'll catch it later" — the point of the commit is that returning to
it works, and a red commit is a lie about that.

Skip nothing on the grounds that the change looks unrelated. A docs-only commit still
runs the harness check; a backend-only commit still runs the frontend build if the
frontend imports anything it changed.

## 7. Commit

```
<type>(<scope>): <subject> (#N)

<Why this change, in prose, hard-wrapped at 80 columns. What the reader needs
in order to understand the diff without reading the issue.>

- <a notable decision, or a file that is not obvious>
- <another>

Verified against <exactly what you ran — the numbers, not the intention>.

Closes #N

Co-Authored-By: Claude <noreply@anthropic.com>
Claude-Session: <the session url>
```

- `<type>` is one of `feat fix refactor docs chore` — the same word as the branch kind.
- `<scope>` is the slice name — `projects`, `training` — or `harness`, `infra`, `docs`
  when the change is not a slice.
- `<subject>` is imperative, lower case, no full stop, and the whole line including
  `(#N)` fits in 72 characters.
- The **Verified against** paragraph is not decoration. It is the record that the gate
  ran.
- `Closes #N` closes the issue when the branch merges into `main`. It only works because
  `main` is the default branch — check with `gh repo view --json defaultBranchRef` if an
  issue fails to close.

A real one:

```
feat(projects): add hardware-fit badges to the model picker (#12)

Beginners had no signal on whether a model would actually run on their
GPU. This adds a plain-language fit badge (comfortable/tight/too_large)
computed from the detected VRAM and the model's parsed parameter count.

- core/hardware.estimate_model_fit() is the one heuristic; models/service.py
  wires it into both /featured and /search
- ModelFitBadge is a shared frontend component, reused by projects-page.ts
  and models-page.ts

Verified against a local run: backend byte-compiles clean, `npm run build`
is warning-clean.

Closes #12
```

Stage the paths you changed, by name. `git add -A` sweeps in whatever else is lying
around and turns a small commit into an unreviewable one.

## 8. Push, then open the PR

Push after every green commit — a commit that only exists on this machine is not a
backup:

```bash
git push -u origin feat/12-projects-page
```

When the last issue in the batch is committed, open one PR for the branch:

```bash
gh pr create --fill --base main --body "Closes #12
Closes #13
Closes #14"
```

One `Closes` per line — GitHub only parses the keyword when it precedes each number.
Then let CI (once it exists) or manual review run and report the result.

## Never

- Never edit code before the issue exists, unless the task explicitly assigned this
  branch and skips the issue step.
- Never commit on a red gate.
- Never amend, rebase or force-push a commit that has been pushed. `git push --force`
  is denied in `.claude/settings.json` and that is deliberate.
- Never put two issues in one commit, or one issue in two commits.
- Never commit `.env`, a key, or anything `.gitignore` covers — including `prompt.txt`.

## Reporting

Report, in this order: the issue numbers opened and their titles; the branch name; each
commit as `<sha> <subject>`; what the gate returned for each; the PR url; and anything
you deliberately left out of the batch and why.
