---
name: release
description: Walks a Mesbah release from a green main to a tagged candidate and then the stable release, or a patch on a released line, by .claude/docs/releasing.md. Use when asked to release, cut a candidate, publish a version, or ship a fix to a released version. Stops before every tag push and every approval, which belong to the person.
---

# Releasing

Read `.claude/docs/releasing.md` first. It is the procedure; this skill is how to walk it. A
release is outward-facing and permanent: a tag that was pushed, or a version that reached an
index, can never be taken back. So every push of a tag, and every approval of the `pypi`
environment, waits for the person to say so in this conversation.

## 1. Where are we?

- **Which version?**
  - `cd backend && python -m tools.release.version show`.
  - `git tag --list 'v*' --sort=-v:refname | head` for what was released.
  - `python -m tools.release.tags previous v<version>` for what this release is compared with.
- **Is `main` green?**
  - The last CI run on `main` and the last nightly *Release bundle* run both passed.
  - No open issue is labelled `release-blocker` or `nightly-failure`.

  Report what is red, and stop.
- **A first release or a patch?** A patch is made on `release/X.Y` (releasing.md, *Fixing a
  released line*). Everything else is made on `main`.

## 2. What changed?

```bash
cd backend
python -m tools.release.contracts --previous <previous tag> --tag v<version>-rc.1 \
  --out /tmp/contracts --report-only
```

Read `contracts-diff.md` with the person:
- A **breaking** change needs a minor bump while the version starts with 0, and a major one
  from 1.0.
- **Additive** needs a minor bump.
- A patch may only add migrations.
- **Blocking** means a shipped migration was edited: that is a bug to fix before anything else.

If the bump is wrong, propose `python -m tools.release.version set X.Y.Z` and why.

## 3. Prepare

On a branch named `chore/<n>-prepare-X.Y.Z` (git-flow):

```bash
cd backend
python -m tools.release.version prepare
```

Show the person the new changelog section. It must say what a user gets in plain words, and
list every contract change under `### Contracts`. Run the gate, commit
`chore(release): prepare X.Y.Z`, push, and open the PR. The person merges it.

## 4. The candidate

1. Find the merged commit on `main` (or `release/X.Y`).
2. Offer the rehearsal: run *Release* by hand with that tag and `dry_run`.
3. Ask before tagging, then:

   ```bash
   git tag -a vX.Y.Z-rc.N -m "Mesbah X.Y.Z-rc.N" <sha>
   git push origin vX.Y.Z-rc.N
   ```

4. Watch the run.
   - **When it fails:** download the `reference` artifact, read `summary.md` and the failing
     part's report, and fix through git-flow. The next candidate is `rc.N+1` on the new
     commit; a tag is never moved.
   - **When it passes:** the GitHub pre-release and TestPyPI have it. Give the person the
     install line for trying it.

## 5. The release

Only when the person says the candidate is good. Then:

1. Ask before tagging.
2. Tag `vX.Y.Z` on **the same commit** as the last candidate, and push it.
3. The run checks the candidate, runs the bundle again, and waits at the `pypi` environment.
   Tell the person it waits for their approval there; never approve it yourself.
4. Afterwards, check that `pip install mesbah==X.Y.Z` works in a clean venv.
5. Propose `python -m tools.release.version bump minor` on `main`, so it prepares the next
   version.

## Never

- **Never move, delete or reuse a tag.**
- **Never tag stable on a commit without a passed candidate.**
- **Never publish by hand**, with `twine` or anything else.
- **Never push a tag or approve an environment without the person's word** in this
  conversation.
