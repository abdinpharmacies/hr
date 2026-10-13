# Module Change Records and Hotfix Transfers

Create/maintain `<module>/changelog.d` in the existing repository format. Before
editing it inspect `git log -- <module>`, relevant `git show <hash> -- <module>`
and `git diff -- <module>` including staged changes where relevant.

Committed entries contain hash, author, date, original subject, user-facing
bullets and a `Files changed:` list. The `Current changes before commit:` section
must describe the current module diff accurately, not stale bullets. Include
only that module's files. This requirement does not itself authorize a commit.

For authorized hotfix transfers between dev/feature branches, inspect
`git log --oneline <branch>`, select exact commits, then cherry-pick the approved
hashes. Do not merge a whole feature branch unless requested. Preserve existing
worktree changes and resolve conflicts within the requested module scope.
