---
name: interactive-rebase
description: Safely clean, reorder, edit, squash, fixup, drop, and reword local Git history with interactive rebase while preserving logical atomic commits and delegating all final commit-message naming rules to the git-commit skill.
compatibility: opencode
metadata:
  workflow: git-history
  message-rules: git-commit
---

# Interactive Rebase

Use this skill when the user wants to clean up, reorganize, combine, split, delete, or rename existing commits with interactive rebase.

## Core rule: commit-message authority

The `git-commit` skill at `~/.config/opencode/skills/git-commit/SKILL.md` is the canonical authority for commit-message naming.

When an interactive rebase will create, replace, or require a final commit message — including `reword`, `squash`, `fixup -c`, `edit` followed by amend, or a squash result — load the `git-commit` skill and follow it.

Do not duplicate, weaken, or invent another commit-message convention here.

The `interactive-rebase` skill owns history manipulation; the `git-commit` skill owns the final commit subject format, type, scope, and description rules.

If `git-commit` is unavailable, do not invent replacement naming rules. Preserve existing messages where possible and stop before creating a new final message unless the user explicitly provides the message.

## Operating principles

- Treat interactive rebase as history rewriting, not ordinary file editing.
- Make the smallest rebase range that fully solves the requested task.
- Never rewrite commits on a shared branch merely for cosmetic cleanup without explicit user intent.
- Never use destructive history commands as shortcuts when an interactive-rebase operation is sufficient.
- Prefer local, unpushed history for cleanup.
- Never force-push automatically after a rebase unless the user explicitly asks for the push.
- When a rewritten branch is already published, prefer `git push --force-with-lease` over `git push --force`.
- Do not silently drop commits. A `drop` operation must match the user's intent.
- Do not silently reorder commits when doing so could alter dependencies between changes.
- Do not use `--rebase-merges` unless preserving/editing merge commits is actually required.

## Before starting

Inspect the repository state first:

```bash
git status --short --branch
git branch --show-current
git log --oneline --decorate --graph -n 20
```

When the branch has an upstream, determine whether the commits being rewritten are already published:

```bash
git status -sb
git rev-list --left-right --count @{upstream}...HEAD
```

Interpret the result before rewriting:

- `ahead > 0`: there are local commits that may be unpublished.
- `ahead = 0` and `behind = 0`: the branch tip matches its upstream.
- `behind > 0`: the local branch is behind its upstream; do not assume an interactive rebase against the local history is the correct operation.

Also check for an existing rebase operation:

```bash
git status
```

If Git reports that a rebase is already in progress, do not start another rebase. Continue, edit the todo list, or abort the existing operation as appropriate.

## Working-tree safety

A clean working tree is preferred before interactive rebase.

If there are unrelated uncommitted changes:

- Do not mix them into the rebase.
- Do not automatically stash them with `--autostash`.
- Preserve the user's working tree and choose a safe approach.

`--autostash` may be used only when it is clearly appropriate and safe, because the final stash application can itself produce conflicts.

## Choose the operation

Use the most specific operation that matches the request.

### Reword a commit message

Use `reword` when the commit's content should stay unchanged and only its message needs to change.

Typical command:

```bash
git rebase -i HEAD~N
```

Then change only the target line from:

```text
pick <sha> <old subject>
```

to:

```text
reword <sha> <old subject>
```

When Git opens the commit-message editor, load/apply `git-commit` and produce the final one-line message according to that skill.

GitHub documents `reword` specifically for changing a commit message without changing the commit's content.

### Edit a commit

Use `edit` when the commit's content itself needs modification, or when the user wants to amend the commit after Git stops there.

```text
edit <sha> <subject>
```

When stopped:

1. Inspect the commit and working tree.
2. Make only the requested changes.
3. Stage the intended changes.
4. If the final message needs changing, load/apply `git-commit`.
5. Amend the commit.
6. Continue the rebase.

Typical commands:

```bash
git add <paths>
git commit --amend
# or, when preserving the existing message is explicitly intended:
git commit --amend --no-edit
git rebase --continue
```

Do not use `--no-edit` when the user asked for the message to be improved.

### Squash commits

Use `squash` when multiple commits should become one and the resulting commit needs a deliberate combined message.

Example:

```text
pick   aaa1111 feat(onboarding): add goal selection
squash bbb2222 fix(onboarding): handle empty goals
squash ccc3333 style(onboarding): adjust spacing
```

After Git opens the combined commit message editor, load/apply `git-commit` and replace the temporary combined text with one canonical final commit subject.

Do not preserve Git's multi-message editor content as a multi-line final commit message. The project's `git-commit` skill requires the final commit subject to remain one line.

### Fixup commits

Use `fixup` when a later commit should be folded into the previous target commit and its own message should be discarded.

Example:

```text
pick  aaa1111 feat(onboarding): add goal selection
fixup bbb2222 fix(onboarding): correct goal state
```

A `fixup` operation normally keeps the earlier commit's message. If the target commit's final message also needs improvement, use `reword` for that target or use an appropriate amend/reword workflow, then apply `git-commit`.

Do not create a new `fixup!` commit during cleanup when the work can be handled directly by the current interactive rebase.

### Drop a commit

Use `drop` when the user explicitly wants a commit removed.

```text
drop <sha> <subject>
```

Deleting the line also removes that commit from the rebased history. Because this can remove real code changes, verify the user's intended commit before dropping it.

Never use `drop` merely because a commit message looks ugly.

### Reorder commits

Interactive rebase can reorder commits by changing their order in the todo list.

Before reordering, inspect the commits and their file relationships. Do not assume two commits are independent just because they touch different files; later commits can depend on earlier behavior or structure.

Reorder only when:

- the user requested it, or
- it is necessary to achieve the requested squash/fixup result.

After reordering, inspect conflicts and validate the resulting history.

## Autosquash workflow

For a cleanup workflow that already contains `fixup!`, `squash!`, or `amend!` commits, prefer:

```bash
git rebase -i --autosquash HEAD~N
```

Git recognizes these specially formatted messages and moves them next to their target commits, changing the rebase actions to `fixup`, `squash`, or amend-style operations.

The preferred way to create future autosquash commits is Git's `git commit --fixup=...`, `git commit --fixup=amend:...`, `git commit --fixup=reword:...`, or `git commit --squash=...` options.

When autosquash eventually needs a final message change, delegate that message to `git-commit`.

## Editing the rebase todo list safely

A rebase todo list normally looks like:

```text
pick   <sha> <subject>
pick   <sha> <subject>
reword <sha> <subject>
squash <sha> <subject>
fixup  <sha> <subject>
edit   <sha> <subject>
```

Rules:

- Do not edit the SHA values.
- Change commands and ordering only as required.
- Keep the todo list minimal.
- Review the complete todo list before saving it.
- Remember that removing a line removes that commit from the resulting history.

## Merge commits

Standard interactive rebase does not reproduce merge commits in the normal todo list.

Use merge-aware rebase only when the user's objective requires preserving or manipulating merges:

```bash
git rebase -i --rebase-merges <upstream-or-range>
```

Do not introduce merge-preservation complexity into a simple linear-history cleanup.

## Choosing the rebase range

Prefer:

```bash
git rebase -i HEAD~N
```

when the task concerns the last `N` commits.

Prefer a branch/base reference when the task concerns all commits since another branch:

```bash
git rebase -i <base-branch>
```

Choose the smallest range that contains every commit that must be changed.

Do not use `HEAD~100` just to be safe when a smaller range is sufficient.

## Conflict handling

If the rebase stops on a conflict:

1. Inspect the conflicted files and the commit Git is trying to apply.
2. Resolve the conflict deliberately; do not blindly take one side.
3. Review the result.
4. Stage the resolved files.
5. Continue the rebase.

Typical commands:

```bash
git status
git diff
# resolve files
git add <resolved-paths>
git rebase --continue
```

If the rebase cannot safely proceed or the requested rewrite should be abandoned:

```bash
git rebase --abort
```

`git rebase --skip` discards the commit currently being applied. Use it only when skipping that specific commit is explicitly intended or clearly correct after inspection.

Never use `--skip` as a generic conflict workaround.

## Verification after rebase

After a successful rebase, verify both history and working-tree state:

```bash
git status --short --branch
git log --oneline --decorate --graph -n 20
```

When the task changes commit messages, verify the exact final subjects:

```bash
git log --format='%h %s' -n N
```

For code changes or conflict resolutions, run the repository's relevant validation when practical. At minimum, inspect the resulting diff and ensure no unrelated changes were introduced.

Compare the rewritten range when useful:

```bash
git diff <old-base>..<new-tip>
```

Remember that rewritten commits receive new IDs. Changing a commit message creates a new commit ID, and commits after that commit also receive new IDs because their parent changed.

## Published-history policy

Determine whether the rewritten commits are already on a remote before recommending a push.

If history was rewritten locally but not pushed:

- no force push is needed;
- report the rewritten range and new commit IDs when useful.

If the rewritten history is already published:

- warn that the remote history will no longer match local history;
- do not silently push;
- when the user explicitly requests the push, prefer:

```bash
git push --force-with-lease origin <branch>
```

- do not default to `git push --force`.

GitHub specifically cautions against rewriting already-pushed history because collaborators may have based work on the old commits.

## Recovery

If a completed rebase produced an unexpected result, do not panic or immediately reset destructively.

Inspect reflog to locate the pre-rebase branch tip:

```bash
git reflog
```

The reflog records local reference movements and can be used to locate previous branch states.

Use recovery commands only after identifying the correct prior commit.

During an active rebase, prefer the built-in controls:

```bash
git rebase --abort
git rebase --continue
git rebase --skip
```

## Output contract

At completion, report only the useful result:

- what history operation was performed;
- the affected commit range or count;
- the resulting commit subjects when message changes matter;
- whether the branch history was rewritten locally;
- whether a push is still required.

Do not generate a long explanation of Git internals unless the user asks for it.

## Do not

- Do not invent commit-message formats in this skill.
- Do not create multi-line final commit messages when `git-commit` is available.
- Do not force-push automatically.
- Do not rewrite another branch or change branches silently.
- Do not drop commits as a cleanup shortcut.
- Do not use `git reset --hard`, `git push --force`, or other destructive shortcuts when a safer operation is sufficient.
- Do not start a second rebase while one is already in progress.
- Do not hide conflicts or claim a rebase succeeded before verification.
