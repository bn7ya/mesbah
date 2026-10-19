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

**`release/changelog.py`** — `sections()` and `section()` read the `## [name] - date`
headings and what is under each. `prepare()` renames `[Unreleased]` to a version, leaves a new
empty `[Unreleased]` above it, and refuses a version twice or nothing to release.
`ChangelogError` is what it raises.

## Decisions worth not re-litigating

**The source never holds a candidate version.** The rc and the release are then the same
commit, so "stable only where its rc passed" is a comparison of two commits, not of two trees
(ADR-010).
