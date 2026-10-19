# Releasing Mesbah

How a version becomes a release, what it must pass, and how a released line gets its fixes.
ADR-010 records why it works this way. `/release` walks the steps.

## Versions

Mesbah follows [Semantic Versioning](https://semver.org).

| Tag | Wheel on PyPI | `__version__` in the commit |
|---|---|---|
| `v0.1.0-rc.1` | `0.1.0rc1` (TestPyPI) | `0.1.0` |
| `v0.1.0-rc.2` | `0.1.0rc2` (TestPyPI) | `0.1.0` |
| `v0.1.0` | `0.1.0` (PyPI) | `0.1.0` |
| nightly | `0.1.0.devN` (an artifact only) | `0.1.0` |

- **The version lives in one place**, `backend/mesbah/__init__.py`, and is always final.
  - A candidate's number comes from its tag and is stamped into the build, never committed.
  - The OpenAPI version reads it, and `frontend/package.json` has none.
  - `python -m tools.release.version show` prints every form.
- **Tags are `vX.Y.Z` or `vX.Y.Z-rc.N`**, nothing else.
- **While the version starts with 0**, a minor release may change what an earlier one promised.
  From 1.0, only a major release may.
- **The latest minor line gets fixes**, as patches from `release/X.Y`. Earlier lines get none.

## What a release must pass

The release bundle (`.github/workflows/release-bundle.yml`) runs on every release tag, candidate
and stable alike. It also runs every night on `main`, where a failure opens the
`nightly-failure` issue.

| Part | What it checks | Blocks a tag |
|---|---|---|
| CI | The whole gate, as on a push to `main` | yes |
| Build | The wheel and sdist, stamped; `twine check`; `SHA256SUMS` | yes |
| Smoke | The wheel installed alone on Python 3.12 and 3.13: version, `doctor`, start, health, the app, a clean stop; the sdist installs | yes |
| Contracts | `backend/contracts/` against the last release's tag. A change larger than the bump fails; so does a blocking or unexplained change. | yes (reported at night) |
| Journeys | `frontend/e2e/` against the wheel, in English and Arabic | yes |
| Upgrade | The last release seeded through its own API, upgraded in place, then checked | yes (skipped with no earlier release) |
| Reference | Packs all of it; fails if any part did not pass | yes |

The local gate (`git-flow` §6) already includes the strict contract tests and the journeys'
type check. Before tagging, also run `npm run e2e` (`frontend/e2e/CLAUDE.md`).

## Contracts

`backend/contracts/` holds what a release promises, generated from the code:
- the API schema;
- `/v1` and `/ollama` as the official clients read them;
- the CLI;
- the shipped migrations;
- the files Django exchanges with the trainer and exporter.

The normal test run fails on any difference. When a change is meant:

```bash
cd backend && pytest --update-contracts && git diff contracts/
```

Then add a line under `### Contracts` in the changelog's `[Unreleased]` section, in the same
commit.

At release time, `tools/release/contracts.py` classes each difference since the last release:

| Change | Kind | Needs |
|---|---|---|
| A path, field, flag, key or enum value removed or changed; a request field made required | breaking | a minor (0.x) or a major (≥ 1.0) bump |
| Something added | additive | a minor bump |
| A migration added | additive | allowed even in a patch |
| A shipped migration edited or removed | blocking | never allowed: add a new migration |
| The trainer's and exporter's files | internal | nothing |

A breaking or additive change also needs its `### Contracts` line.

## The reference artifact

Every GitHub Release carries `mesbah-<version>-reference.tar.gz`. It is what the next release
is compared with, and what a person opens to see what a version was:

| File | What it is |
|---|---|
| `manifest.json` | version, commit, previous release, each part's result, every file with its sha256 |
| `summary.md` | the results as a table; also the end of the release notes |
| `dist/` | the wheel, the sdist and `SHA256SUMS` |
| `contracts/` | the snapshots this release promises |
| `compare/` | `compare.json` and `contracts-diff.md` against the last release |
| `e2e/` | the Playwright report, `junit.xml`, the stack's logs, and `screens/` with an `index.html` gallery |
| `upgrade/` | `upgrade.json`, `verify.json`, the migration plan and both stacks' logs |

To see what changed between two releases:
- unpack both and diff their `contracts/`;
- open both galleries side by side;
- compare the `summary.md` files.

## Cutting a release

1. **Be ready.**
   - CI on `main` and the last nightly are green.
   - No issue is labelled `release-blocker`.
   - `/sessions` shows nobody else running the journeys, which take ports 8177 and 8178.
2. **Prepare** on a branch:
   ```bash
   cd backend
   python -m tools.release.version set X.Y.Z   # only if main is not already at X.Y.Z
   python -m tools.release.version prepare     # dates [Unreleased] as [X.Y.Z]
   ```
   Read the changelog section. Run the gate, commit `chore(release): prepare X.Y.Z`, open the
   PR and merge it.
3. **Rehearse (optional):** run *Release* by hand with `tag: vX.Y.Z-rc.1` and `dry_run` on.
4. **Tag the candidate** on the merged commit, then watch the run:
   ```bash
   git tag -a vX.Y.Z-rc.1 -m "Mesbah X.Y.Z-rc.1" <sha> && git push origin vX.Y.Z-rc.1
   ```
5. **If it fails,** fix it the normal way, merge, and tag `rc.2` on the new commit. Never move
   or reuse a tag.
6. **Soak:** `pip install --pre -i https://test.pypi.org/simple/ mesbah==X.Y.ZrcN`, and use it.
7. **Release:** tag `vX.Y.Z` on **the same commit as the last candidate**, push it, and
   approve the `pypi` environment when the bundle is green. Then check
   `pip install mesbah==X.Y.Z` in a clean venv.
8. **Move on:** `python -m tools.release.version bump minor` on `main`, so `main` prepares the
   next version.

## Fixing a released line

1. **Fix it on `main` first**, through the normal flow.
2. **The first time a line needs a fix**, cut its branch from the release:
   `git switch -c release/X.Y vX.Y.0 && git push -u origin release/X.Y`.
3. **Branch from `release/X.Y`** and `git cherry-pick -x` the fix. Run
   `python -m tools.release.version set X.Y.(Z+1)` and `prepare`, then open a PR into
   `release/X.Y`.
4. **Tag `vX.Y.(Z+1)-rc.1`, then `vX.Y.(Z+1)`,** on that branch's merged commit.
   - The workflow checks the tag is on `release/X.Y`.
   - A patch may only add migrations.
   - A patch to an older line is not marked latest.

## Set up once

**GitHub, under Settings → Environments:**
- `testpypi`: deployments from tags `v*-rc.*`.
- `pypi`: deployments from tags `v*`, with required reviewers.

**Trusted publishers.** On pypi.org and test.pypi.org, add a pending trusted publisher:
- owner `bn7ya`, repository `mesbah`, workflow `release.yml`;
- environment `pypi`, or `testpypi` on test.pypi.org.

**Rulesets, under Settings → Rules:**
- tags `v*`: nobody may update or delete them. The stable check trusts that a candidate's tag
  never moves.
- branches `release/*`: no force push and no deletion, and a pull request is required.

**Actions:** workflows may create issues, for the nightly failure issue. This is on by default.

## Never

- **Never move or delete a release tag**, or reuse a version.
- **Never release stable without a candidate** on the same commit.
- **Never upload with `twine` by hand.**
- **Never edit a shipped migration.**
