---
name: git-flow
description: Turns a feature, fix or refactor request into a GitHub issue, a branch, and a series of small commits that each work on their own. Use before writing code whenever a request adds behaviour, corrects behaviour, or restructures existing code. Not for questions, reviews or reading.
---

# The git flow

Every feature, fix and refactor starts as a GitHub issue and lands as commits small
enough that any one of them can be checked out and run. The issue comes before the
first edit, not after the last one.

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

Rule 2 says nothing ships backend-only or frontend-only, so never split a slice into a
backend commit and then a frontend commit — the first of the two is a commit you cannot
return to. Split by **behaviour** instead. Each issue is a thin vertical slice, both
sides, that stands up on its own:

```
#12  the orders list page    model → repository → service → view → serializer →
                             api → store → component → route → guard
#13  filtering and sorting
#14  bulk actions
```

Check out the commit that closed `#12` and you get an application that starts, serves an
orders page, and passes CI. That is the test of a good split, and the reason the split is
worth the effort.

A small request is one issue. If an issue needs an "and" to describe it, it is two.

## 3. Open the issues

Once, in a fresh clone — GitHub ships neither label:

```bash
gh label create refactor --color 5319e7 --description "Behaviour-preserving restructuring"
gh label create chore --color cfd3d7 --description "Tooling, dependencies and housekeeping"
```

Then one `gh issue create` per unit, in the order they will be built:

```bash
gh issue create --title "Add the orders list page" --label enhancement --body "$(cat <<'EOF'
## What

One paragraph: the behaviour this adds, in the words a user would use.

## Why

The problem it solves. Not the implementation.

## Slice

- Backend: `backend/apps/orders/` — model, repository, service, view, serializer
- Frontend: `frontend/src/app/features/orders/` — api, store, component, route, guard

## Done when

- [ ] The page loads and does what the title says
- [ ] The full gate is green (see the skill, step 6)
- [ ] `ar.json` matches `en.json` key for key, and the page works in RTL (rule 22)
- [ ] Every touched feature directory has a current `CLAUDE.md` (rule 3)
- [ ] The definition of done in `.claude/docs/design-pattern.md` § 6 is met
EOF
)"
```

Keep the issue about behaviour. The design belongs to `architect`, not to the tracker.

## 4. Cut the branch

```bash
git switch main && git pull
git switch -c feat/12-orders-page
```

`<kind>/<issue>-<two-or-three-words>`. The kind matches the commit type. The number is
the issue, and when a request became several issues it is the **lowest** of the batch —
the branch delivers the slice, the issues are its steps.

Cut from `main`, never from another work branch. One slice per branch: if the name needs
an "and", it is two branches.

## 5. Build one issue at a time

Dispatch the specialists in the order `CLAUDE.md` sets out. Do not open the next issue's
work until the current one is committed and pushed — half of `#13` sitting in the working
tree is what makes `#12`'s commit unreturnable.

## 6. The gate — run it before every commit

This is the same set of checks `.github/workflows/ci.yml` runs. It decides whether a
commit is allowed to exist.

```bash
# Backend — from backend/, or prefix each with: docker compose exec backend
ruff check . && ruff format --check . && mypy . \
  && python manage.py makemigrations --check --dry-run \
  && python manage.py spectacular --fail-on-warn --file /dev/null \
  && pytest --cov=apps --cov-report=term-missing

# Frontend — from frontend/, or prefix each with: docker compose exec frontend
npx ng lint && npx ng build --configuration production && npx ng test --watch=false

# Harness — from the repo root
python -m compileall -q .claude/hooks
```

CI also checks two invariants worth confirming by eye before you push: an `ar.json`
beside every `en.json` with an identical key set and no tashkeel (rule 22), and a `CLAUDE.md` in every
`features/*/` and `apps/*/` you touched (rule 3).

Red is not a commit. Fix it, or split the commit smaller until each half is green. Never
`--no-verify`, never "CI will catch it" — the point of the commit is that returning to it
works, and a red commit is a lie about that.

Skip nothing on the grounds that the change looks unrelated. A docs-only commit still
runs the harness check; a backend-only commit still runs the frontend build.

## 7. Commit

```
<type>(<scope>): <subject> (#N)

<Why this change, in prose, hard-wrapped at 80 columns. What the reader needs
in order to understand the diff without reading the issue.>

- <a notable decision, or a file that is not obvious>
- <another>

Verified against <exactly what you ran — the numbers, not the intention>.

Closes #N

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: <the session url>
```

- `<type>` is one of `feat fix refactor docs chore` — the same word as the branch kind.
- `<scope>` is the slice name — `orders`, `accounts` — or `harness`, `infra`, `docs`
  when the change is not a slice.
- `<subject>` is imperative, lower case, no full stop, and the whole line including
  `(#N)` fits in 72 characters.
- The **Verified against** paragraph is not decoration. It is the record that the gate
  ran, and it is how every substantive commit in this repository already ends.
- `Closes #N` closes the issue when the branch merges into `main`. It only works because
  `main` is the default branch — check with `gh repo view --json defaultBranchRef` if an
  issue fails to close.

A real one:

```
feat(orders): add the orders list page (#12)

Orders were only reachable through the admin. This adds the first slice of the
customer-facing page: a paginated, soft-delete-aware list behind the existing
group guard.

- OrderRepository is the only place the ORM is touched (rule 14)
- The store holds the page signal; the component holds none of it

Verified against a local Postgres and Redis: 14 backend tests pass, 22 frontend
tests pass, plus ruff check, ruff format --check, makemigrations --check,
spectacular --fail-on-warn, ng lint and a production build.

Closes #12
```

Stage the paths you changed, by name. `git add -A` sweeps in whatever else is lying
around and turns a small commit into an unreviewable one.

## 8. Push, then open the PR

Push after every green commit — a commit that only exists on this machine is not a
backup:

```bash
git push -u origin feat/12-orders-page
```

When the last issue in the batch is committed, open one PR for the branch:

```bash
gh pr create --fill --base main --body "Closes #12
Closes #13
Closes #14"
```

One `Closes` per line — GitHub only parses the keyword when it precedes each number.

CI runs only when the branch is merged into `main`, never on a pull request. The gate in
step 6 is therefore the only check a branch gets before it merges — which is the reason it
is not optional. After the merge, read the run on `main` and report it.

## Never

- Never edit code before the issue exists.
- Never commit on a red gate.
- Never amend, rebase or force-push a commit that has been pushed. `git push --force` is
  denied in `.claude/settings.json` and that is deliberate.
- Never put two issues in one commit, or one issue in two commits.
- Never commit `.env`, a key, or anything `.gitignore` covers — including `prompt.txt`.

## Reporting

Report, in this order: the issue numbers opened and their titles; the branch name; each
commit as `<sha> <subject>`; what the gate returned for each; the PR url; and anything
you deliberately left out of the batch and why.
