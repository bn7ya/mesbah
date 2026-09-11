# Working alongside other sessions

More than one Claude session runs on this machine at once, and a project of any
size is soon checked out as several worktrees. Before the session hooks nothing told one
session that another existed, and it costs real work: two Docker gates running together time each
other out, a backgrounded `pytest` holds the test database the other session
needs, and two sessions in one file overwrite each other.

Every session now writes a short document about itself and reads everybody
else's. This is what it says, where it lives, and why it is shaped this way.

## What is written, and what is only read

Almost nothing needs storing, because the harness already keeps it:

| Where | What |
|---|---|
| `~/.claude/sessions/<pid>.json` | one document per live session — id, name, cwd, status, `pid`, `procStart`, `pidDomain` |
| `~/.claude/file-history/<session>/<sha256(abs path)[:16]>@v<n>` | every file that session edited, one entry per version |
| `~/.claude/plans/<slug>.md` | the plan documents, all projects in one flat directory |

So a session writes down only the five things the harness has no idea about:
the **worktree**, the **branch**, the **issue** parsed from the branch name,
the **intent** — the first line of the last prompt — and its own notification
bookkeeping. Everything else is derived when it is read:

- **liveness** from `pidDomain` and field 22 of `/proc/<pid>/stat`;
- **the plan** by intersecting the session's file history with `~/.claude/plans/`;
- **who edited a file** by hashing its absolute path and globbing the file history.

`ListAgents` already answers most of "who is live". The reason this exists
anyway is narrow and real: **the model will never call `ListAgents` unprompted.**
A hook is unconditional and costs nothing.

## Where it lives

`$XDG_RUNTIME_DIR/claude-sessions/`, falling back to `~/.cache/claude-sessions/`
at mode 0700. Not in the repository, not in `.git`, and not scoped to a
repository at all.

The pain is **machine**-scoped. Two Docker gates contend for one machine whether
or not they are the same project, and a session working in another repository
would be invisible to a per-repository registry. The runtime directory is also
tmpfs, so a reboot reaps the whole thing correctly and for free — presence data
that outlives its process is a lie, and this makes outliving impossible.

`git rev-parse --git-common-dir` was the tempting alternative and is a trap
twice over: it answers the bare string `.git` from the main worktree and an
absolute path from a linked one, and nothing ever cleans a directory git does
not recognise.

## Why nothing here takes a lock

**One writer per file, always: the session the file describes.** Readers never
write to a peer's document. Claims are named `claims/<resource>@<session>.json`
so that a resource two sessions want still has one file each. Under that
invariant there is no write-write contention anywhere and no lock is needed.
Writes are `mkstemp` in the same directory, `fsync`, then `os.replace`, so no
reader can observe a half-written file. Every read is guarded anyway.

A claim is an **announcement, not a lease**. Nothing waits on one, and nothing
is blocked by one. A lease would need a TTL, a steal-after-expiry rule and crash
recovery, and getting it wrong means a session waiting forever on a resource
held by a process that died — worse than the collision it was preventing. Since
liveness is derived, a dead holder simply stops being returned.

There is no `SessionEnd` hook, deliberately. It is not guaranteed to fire on
`kill -9`, so relying on it would leave documents that lie. Deriving liveness
from the harness's own registry removes the problem instead of mitigating it: a
document no live session backs is never rendered, however old it is.

## Why it stays quiet

A hook that talks on every prompt gets deleted, and then none of the rest of
this matters. Two hooks already run on every prompt, one of which prints fifteen
lines whenever the prompt looks like work.

- **`SessionStart`** prints nothing at all when no other session is live, which
  is the common case. Otherwise: at most five peers, hard cap twelve lines.
- **`UserPromptSubmit`** hashes the live set into a digest and prints nothing
  while that digest holds. Only four things may interrupt — a session appeared,
  a session we had named ended, a session moved onto our branch, a session
  entered our worktree — at most one notice per kind per ten minutes, hard cap
  six lines.
- **The file warning** compares **absolute** paths. Two sessions editing
  `backend/app/features/inference/engine.py` in two worktrees are editing two different
  files and are not in conflict; comparing repository-relative paths would
  invent that conflict, and a warning that is usually wrong gets switched off.
  Anything under a `.claude` directory and `prompt.txt` are exempt, as is a
  touch older than thirty minutes.

`.claude/hooks/test_session_hooks.py` asserts the silence — five identical
prompts, exactly one of which may speak — and CI runs it. That test is what
protects the feature's life.

## It warns; it does not block

A file conflict prints a warning naming the other session and lets the edit
through. One person drives both sessions and knows things the hook does not, so
the decision belongs where the knowledge is. Turning a warning into a stop is
one line in `file-conflict-warn.py`: add `"permissionDecision": "ask"` to the
`hookSpecificOutput` it already emits.

To switch the whole feature off, set `CLAUDE_SESSIONS_OFF=1` — the first line of
every session hook. To quieten one session for a while, `/sessions mute`.

## Known, and not fixed here

Every worktree's `docker-compose.django.yml` declares the same project name, so a second
`docker compose up` from another worktree does not start a second stack: it
reuses and mutates the first one. That is the real mechanism behind the
deadlocked test database. `resource-claim.py` makes the collision **visible** at
the moment it is about to happen; the fix is a per-worktree
`COMPOSE_PROJECT_NAME`, and it is its own chore.
