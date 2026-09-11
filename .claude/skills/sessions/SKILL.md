---
name: sessions
description: Shows which other Claude sessions are live on this machine, what each is working on, and how to coordinate with one before editing what it holds. Use when a session hook has warned about a peer, before starting the gate or a long Docker run, and whenever work might overlap with another session.
---

# Other sessions

Several Claude sessions run on this machine at once, often in different
worktrees of this repository. `.claude/docs/sessions.md` explains the mechanism;
this is what to do about it.

## 1. Look

```bash
python3 .claude/hooks/session_registry.py --list    # for a person
python3 .claude/hooks/session_registry.py --json    # for a script
```

Each live session reports its name, status, worktree, branch, what it was last
asked to do, and its **plan document**. The plan is the useful part: it says
what that session intends, in its own words, before it does it.

## 2. Read their plan before you decide

If a peer's plan overlaps your work, read it. It is an ordinary markdown file
and it will name the files and the branch. Most apparent conflicts resolve here
— a peer in the same file on a different worktree is not touching your copy.

## 3. Talk to them

Sessions can message each other by name. `ListAgents` lists what is reachable;
`SendMessage` sends:

```
SendMessage(to: "the-other-session", message: "I'm about to rewrite
  engine.py on chore/x. Your plan touches it — are you mid-edit?")
```

Do not build anything else for this. There is one messaging channel and it is
the harness's.

## 4. When to stop and ask the user instead

- A peer is on **your branch**. Two sessions committing to one branch will
  collide in a way no hook can undo. Ask before committing.
- A peer holds **the gate, the test database or the compose project**. Running
  the second one contends for the machine, and for compose the second run
  mutates the first one's stack instead of starting its own. Wait, or ask.
- A peer is **editing the same absolute path** and its plan says it means to.

## 5. Quieting it

```bash
python3 .claude/hooks/session_registry.py --mute 30   # minutes
```

`CLAUDE_SESSIONS_OFF=1` turns the whole thing off for a session. Prefer muting:
the warnings exist because someone lost work without them.

## Never

- Never edit another session's document under `$XDG_RUNTIME_DIR/claude-sessions/`.
  One writer per file is what makes the registry safe without a lock.
- Never treat a resource claim as a lock. Nothing waits on one; it is an
  announcement, and a session that ignores it is not doing anything illegal.
- Never assume a peer that appears in the list is *blocking* you. Read, then
  decide.
