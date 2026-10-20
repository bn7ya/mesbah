# ADR-010: Releases go candidate first, then stable, and pass one bundle

**Status:** accepted — 2026-10-19 (#23)

## Context

Mesbah ships to people who keep their data in it: projects, corrections, versions and API
keys, in a data folder or a PostgreSQL database that outlives every install. A release that
breaks the API a client depends on, or that cannot open the previous release's data, costs
them work. Mesbah had no release yet:

- The version was written in three places.
- Nothing pinned the API, the compatible APIs, the CLI, the migrations or the data folder.
- The browser journeys had been walked once by hand.
- Any `v*` tag went straight to PyPI.

## Decision

- **Semantic Versioning.** While the version starts with 0, a minor release may break what an
  earlier one promised, and says so under **Contracts** in `CHANGELOG.md`. From 1.0, only a
  major release may.
- **The version lives only in `backend/mesbah/__init__.py`, and is always final** (`X.Y.Z`).
  - The release candidate number is the tag's: `vX.Y.Z-rc.N`.
  - CI stamps it into the checkout just before building, so the wheel is `X.Y.ZrcN`.
  - A nightly is stamped `X.Y.Z.devN`.
- **Candidate first, then stable, on the same commit.**
  - A candidate tag runs the whole release bundle, publishes to TestPyPI, and only then creates
    its GitHub pre-release.
  - A stable tag is refused unless a candidate tag sits on the same commit and that pre-release
    exists, made by the workflow with its reference artifact.
  - Stable runs the bundle again on its own wheel, so the bytes published are the bytes tested,
    and publishes to PyPI behind the `pypi` environment's reviewers.
  - Publishing lives in `release.yml` itself, because PyPI's trusted publishing does not accept
    a reusable workflow.
- **The release bundle is one reusable workflow** (`release-bundle.yml`). It runs on every
  release tag, blocking, and nightly on `main`, reporting. Pushes keep the normal CI. Its parts:
  - **CI itself**, called, not copied.
  - **Contract snapshots in `backend/contracts/`**, generated from the code and compared
    strictly by the normal test run. A deliberate change is accepted with `--update-contracts`
    in the same commit as the code, with a CHANGELOG line. At release time the snapshots are
    compared with the previous release's and classified as breaking, additive or none. A bump
    smaller than the change is refused. A shipped migration that changed or disappeared blocks
    the release whatever the bump.
  - **The journeys** (`frontend/e2e/`), Playwright against a real `mesbah start` of the built
    wheel, in English and in Arabic. They run with no GPU and no network:
    - the fake trainer trains;
    - a fake engine stands behind the built-in engine's real HTTP layer;
    - a model trained from nothing serves as the base, so HuggingFace is never needed.
  - **The upgrade test.** The previous release's wheel is seeded by that release's own seed
    script, then upgraded in place and checked. It is skipped while there is no previous
    release.
  - **The reference artifact**, `mesbah-<version>-reference.tar.gz`, attached to every GitHub
    Release. It holds the wheel, the sdist, `SHA256SUMS`, the contracts and their diff, the
    reports, the screenshots and the logs. It is what the next release is compared with.
- **Fixes to a released line ship from `release/X.Y`.** The fix lands on `main` first, then
  is cherry-picked and released as `X.Y.Z+1`. A patch may not change a contract beyond adding a
  migration.

## Consequences

- **A checkout of a candidate commit reads `0.1.0`;** only its wheel says `0.1.0rc1`.
- **A broken candidate is never re-tagged.** The fix gets a new commit and `rc.N+1`, because
  TestPyPI and tags never take a version twice.
- **Changing an endpoint, a CLI flag or the data folder is cheap but never silent.** The
  snapshot diff is in the commit, and the release says what kind of change it was.
- **A `/template-sync` that brings back a version in `package.json`** or the spectacular
  setting fails a test, and this decision is reapplied.

### Rejected

- **Committing `X.Y.ZrcN` and then a release commit.** The stable commit would never be the one
  that was tested.
- **Pixel-comparing screenshots.** Fonts differ between runners. Screenshots are kept for a
  person to compare, and only their list is checked.
- **Faking chat with request interception in the browser.** It would bypass the reply service,
  the engine client and persistence, so the journeys would test a mock.
