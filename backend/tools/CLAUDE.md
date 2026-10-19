# backend/tools

Scripts a developer or CI runs against a checkout. None of this ships: the wheel and the sdist
take only `mesbah`, `apps` and `config`. Run everything from `backend/` as
`python -m tools.<module>`, except `build_wheel.py`, which runs as a script.

## Layout

```
tools/
  build_wheel.py        builds the frontend into the wheel, then the wheel and sdist
  release/              how a release is versioned (ADR-010)
    version.py          the version in every form, and the commands that move it
    changelog.py        CHANGELOG.md's sections
    stack.py            a running Mesbah and the fake engine, for the release journeys
    tags.py             the release tags in git, and the release before a version
    upgrade.py          the upgrade test: the last release, seeded, then upgraded in place
    seed.py             what the upgrade test makes through a release's own API
    verify.py           what it checks after the upgrade
    client.py           a standard-library HTTP client for both, with the session and CSRF
    contracts.py        the contracts against the last release: breaking, additive or neither
    reference.py        the reference tarball a release keeps
    tests/
```

## Classes and methods

**`build_wheel.main()`** — builds the Angular app, copies it into `mesbah/_spa`, and builds
the wheel and the source archive into `backend/dist/`.

**`release/version.py`**:
- **`Release`** — one release number, with an optional candidate number. It reads as:
  - `final` (`0.1.0`);
  - `semver` (`0.1.0-rc.1`);
  - `pep440` (`0.1.0rc1`, what the wheel is called);
  - `tag` (`v0.1.0-rc.1`);
  - `line` (`0.1`, the `release/0.1` branch it is fixed on).

  `key` orders releases, so a candidate sorts before its release. `bumped()` gives the next
  major, minor or patch.
- **`parse_tag()`** — reads `vX.Y.Z` or `vX.Y.Z-rc.N`, nothing else.
- **`parse_final()`** — reads `X.Y.Z`, nothing else.
- **`current()`** — the version in `mesbah/__init__.py`. It is always final; the candidate
  number comes from the tag.
- **`check()`** — the source is final. Given a tag, it also checks that the tag is that version
  and that `CHANGELOG.md` has its section.
- **`stamp()`** — CI only, just before a build. It writes a candidate's version
  (`0.1.0rc1`) or a nightly's (`0.1.0.devN`) into the source.
- **`set_version()`** — moves the source to a version, never backwards.
- **`prepare()`** — dates the unreleased changes as the source's version.
- **`main()`** — the command line, with `show`, `check`, `pep440`, `stamp`, `set`, `bump`,
  `prepare` and `notes`. It exits 1 with a one-line error.

**`release/stack.py`** — `python -m tools.release.stack start|stop`.
- `start()` refuses a data folder that is not empty or a port that is taken. It then starts the
  fake engine on the engine port, and `mesbah start`, from a checkout or an install, with the
  fake trainer. Unless `--online` is given, HuggingFace is unreachable (`offline()`). It waits
  for health and for the first-run setup, then writes **`Stack`** (`stack.json`): the
  addresses, the data folder, the setup code, the version and the process ids.
- `stop()` sends SIGTERM and waits, and reports a Mesbah that did not stop, an embedded
  PostgreSQL left running, or an engine that did not stop.
- `mesbah_command()`, `version_of()`, `launch()`, `wait_for()`, `answers()`, `alive()` and
  `stop_process()` are its steps; `StackError` is what goes wrong.

**`release/tags.py`** — **`tags()`** lists the `v*` tags in git; **`releases()`** keeps the release
tags among them, in version order; **`previous()`** is the last stable release before a version. `main()` is
`python -m tools.release.tags previous <tag>`, which prints that release's tag or nothing.

**`release/contracts.py`** — `python -m tools.release.contracts --previous <tag> --tag <tag> --out
<folder> [--report-only]`. **`snapshots()`** reads `backend/contracts/` at a git ref, or in the
tree. **`facts()`** and **`flat()`** turn a file into path→value facts, without descriptions.

**`compare()`** gives a **`Verdict`** of **`Change`**s:
- **The public files** (`openapi.json`, `compat.json`, `cli.json`): something removed or changed
  is breaking, and something added is additive. A field made required in a request is breaking.
  This is **`compare_public()`**.
- **Migrations:** one edited or gone is blocking, and a new one is additive
  (**`compare_migrations()`**).
- **Anything else** is internal.

**`allowed()`** refuses:
- a blocking change;
- a patch that does more than add migrations;
- from 1.0, a breaking change without a major bump.

A breaking or additive change also needs a `### Contracts` line in that version's changelog
section. It writes `compare.json` and `contracts-diff.md` (**`markdown()`**).

**`release/reference.py`** — `python -m tools.release.reference --version … --out … --part
name=folder … --result job=result … --note key=value`. **`assemble()`** copies each part into
`mesbah-<version>-reference/`, adds a screenshot gallery (**`gallery()`**), `summary.md`
(**`summary()`**) and `manifest.json` (results, notes, and every file with its size and sha256,
from **`inventory()`** and **`digest()`**), and packs it. It exits 1 when any result is not
`success` or `skipped`.


**`release/upgrade.py`** — `python -m tools.release.upgrade --new <wheel> --work <folder>`. Without
`--from`, it finds the release before the wheel's version. When there is none, it writes a skipped
`upgrade.json` and exits 0. Otherwise, **`fetch()`** downloads that release's wheel from its GitHub
Release, checked against `SHA256SUMS` (**`checksum_matches()`**), and falls back to PyPI.
**`Upgrade.run()`** then:
1. installs it in a venv;
2. starts it through `stack.py`;
3. seeds it with the **seed script of that release's own tag** (`--seed-ref`, or `.` for this
   tree);
4. stops it;
5. installs the new wheel over it, in place;
6. checks the version and plans the migrations;
7. starts it again on the same data with `--existing`;
8. runs `verify.py`;
9. stops it.

Each step is a **`Step`** in the **`Report`** (`upgrade.json`), which passes only when every step
did. **`release_of()`** reads a wheel's version from its name. **`UpgradeError`** is a step that
failed, with what it printed.

**`release/seed.py`** — `python -m tools.release.seed --stack … --state …`. **`seed()`** creates,
through the API:
- the owner and a viewer;
- a dataset;
- a base model the Architect trains;
- a project with v1 and a v2 grown from v1;
- a conversation whose reply is corrected and approved;
- a LoRA export;
- an external engine with a sealed key;
- an API key.

It then writes their ids and secrets to `state.json`. **`train()`**, **`base_model()`**,
**`reply()`** (reading the stream with **`events()`**) and **`finished()`** are its steps.

**`release/verify.py`** — `python -m tools.release.verify`. **`Verifier.checks()`**, against the
upgraded install, cover:
- the setup stays closed;
- both people sign in with their roles;
- the project's versions and parents;
- runs and their metrics;
- the dataset's rows;
- the correction, its thinking and its approval;
- the export downloads;
- the old API key still works on `/v1/models`;
- the engine keeps its sealed key;
- chat still answers;
- a new version trains on top of v2;
- every migration is applied;
- `mesbah doctor` runs.

Each becomes an **`Outcome`** (**`run()`**), written to `verify.json`.

**`release/client.py`** — **`Client`**, with a cookie jar, the CSRF header, an optional bearer key,
`get`, `post`, `patch`, `upload`, `send` (the raw **`Answer`**), `sign_in` and `until`. It raises
**`ClientError`** on a status that is not a success. **`text()`** and **`items()`** narrow what
comes back.

**`release/changelog.py`** — `sections()` and `section()` read the `## [name] - date`
headings and what is under each. `prepare()` renames `[Unreleased]` to a version, leaves a new
empty `[Unreleased]` above it, and refuses a version twice or nothing to release.
`ChangelogError` is what it raises.

## Decisions worth not re-litigating

**A release is seeded by its own seed script.** The upgrade test takes `seed.py` from the
previous release's tag, so the data it makes is what that release's API made. The checks after
the upgrade are this tree's, because they describe what the new release must still read.

**The source never holds a candidate version.** The rc and the release are then the same
commit, so "stable only where its rc passed" is a comparison of two commits, not of two trees
(ADR-010).
