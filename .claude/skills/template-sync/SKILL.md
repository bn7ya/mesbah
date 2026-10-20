---
name: template-sync
description: Brings the changes made to the Template since this repository last synced into this repository, on their own branch and commit. Use when the template-sync hook says the Template has commits this repository has not taken, or when asked to update from the Template. Not for the Template repository itself.
---

# Sync with the Template

A product is cut from `bn7ya/Template` and then lives on its own. The Template keeps
improving — rules, hooks, agents, shared code — and this is how those changes arrive.

`.claude/template.json` records which Template commit this repository last took. Products
cut with GitHub's "Use this template" share no history with it, so this is never a
`git merge`: the Template's own diff since that commit is replayed onto this tree, and
whatever the product changed itself stays as it is.

## 1. Look first

```bash
python3 .claude/hooks/template-sync.py status
```

`behind` lists the Template commits not taken yet. If `baseline` is null, nobody recorded
where this repository started and its first commit is not an exact copy of any Template
commit. Ask the developer which Template commit it was cut from, then:

```bash
python3 .claude/hooks/template-sync.py mark <sha>
```

## 2. Branch, then apply

The tree must be clean.

```bash
git switch main && git pull
git switch -c chore/sync-template
python3 .claude/hooks/template-sync.py apply
```

Exit 0: every change applied and the sync point moved. Exit 2: some changes collided with
the product's own. Resolve each conflict marker by keeping both intents — the Template's
rule and the product's feature — and ask the developer when the two cannot both hold. Then
`git add` the files and record the sync point:

```bash
python3 .claude/hooks/template-sync.py mark <the sha it printed>
git add .claude/template.json
```

## 3. Gate, commit, PR

Run the full gate from the git-flow skill: a Template change can break a product's
feature. Then:

```
chore(harness): sync with the Template at <short sha>

<one line per Template commit taken, from `status`>

Verified against <the gate, with numbers>.
```

Open one PR for the branch and report the commits taken, any conflict and how it was
resolved, and what the gate returned.

## Never

- Never run it in the Template itself — the hook knows and stays silent.
- Never resolve a conflict by dropping the product's change without asking.
- Never edit `synced` by hand to skip Template commits; skipping one is the developer's call.
