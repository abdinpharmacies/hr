# Project workflow for software diagrams

Use this reference when diagrams are being added to an existing repository, especially when the repository has staged changes or a publication policy.

## 1. Write the asset contract first

Before creating files, write a small table or manifest with one row per diagram:

| id | purpose | canonical source | renderer | outputs | documents | publication |
|---|---|---|---|---|---|---|
| `system-overview` | explain module boundaries | `docs/diagrams/sources/system-overview.mmd` | Mermaid | `docs/assets/diagrams/system-overview.svg` | `docs/architecture.md` | output |

Every diagram must have a delivery purpose. `documents` may be an empty array for an independent deliverable. Do not create a second source file containing the same model.

An equivalent JSON manifest is useful for automation:

```json
{
  "profile": "local-source/published-artifacts",
  "diagrams": [
    {
      "id": "system-overview",
      "purpose": "explain module boundaries",
      "source": "docs/diagrams/sources/system-overview.mmd",
      "renderer": "mermaid",
      "outputs": ["docs/assets/diagrams/system-overview.svg"],
      "documents": ["docs/architecture.md"],
      "publication": "output"
    }
  ]
}
```

The `source` is the only canonical model. A Markdown Mermaid block is canonical only when it is explicitly selected as `source`; do not also create a copied `.mmd` file.

## 2. Select a publication profile

Choose one profile before editing files:

- `tracked-source`: source and selected rendered outputs are tracked and published.
- `local-source/published-artifacts`: source and renderer toolchain stay local; selected SVG/PNG outputs are published.
- `local-only-preview`: source and outputs stay local; documents may embed them only in a local preview workflow.

For every profile, record the allowed publish set. Add narrow ignore rules only when needed. `tools/bin/` and `node_modules/` are normally local toolchain paths; ignore `docs/diagrams/sources/` only for a profile that intentionally keeps canonical sources local. Never replace an existing `.gitignore` wholesale and never assume a path can be ignored safely without checking the repository.

Use `publication: source`, `output`, `both`, or `local` for each diagram to state whether the canonical source, rendered outputs, both, or neither are published. With `tracked-source`, the source is eligible for publication and `source`, `output`, or `both` may be selected; with `local-source/published-artifacts`, select `output`; with `local-only-preview`, select `local`.

## 3. Protect Git state

If the repository has existing work and Git state must be protected, run this preflight before writing:

```powershell
git status --porcelain=v2 --untracked-files=all
git diff --cached --name-status
git log -n 5 --format=%s
git branch --show-current
git rev-parse HEAD
git remote -v
```

Keep the output as the preflight record. Write new paths where possible. Do not run `git add -A`, `git reset`, `git restore --staged`, `git commit`, or `git push` unless the user explicitly asks for that operation.

If the user explicitly asks for a commit, stage only the declared publish set. Do not use `git commit-tree`, `git update-ref`, or a temporary `GIT_INDEX_FILE` as a shortcut. If preserving an existing staged state requires an unusual index operation, stop and explain the conflict before mutating it.

After the work, run the same commands and compare the preflight and postflight records when Git state must be preserved or a commit is requested. Report any changed staged or unstaged path, branch, HEAD, or remote.

## 4. Render the user's project

The repository's `scripts/render-all.ps1` and `scripts/render-all.sh` validate only the checked-in `examples/shop/` gallery. Passing that gallery does not prove that a user's project diagram rendered successfully.

For a user project:

1. Run the project's own renderer if it exists.
2. Otherwise use the pinned renderer commands from `references/toolchain.md`.
3. Render every output listed in the manifest.
4. Stop on the first renderer error and repair the canonical source.
5. Print the exact commands, renderer versions, and output paths.

Keep bootstrap separate from rendering:

```powershell
npm ci
pwsh ./scripts/bootstrap.ps1
pwsh ./scripts/render-all.ps1
```

`npm ci` installs the pinned Node packages; bootstrap prepares the Java tools and native draw.io helper; render-all validates this repository's gallery. Neither command automatically discovers diagrams in another repository.

## 5. Validate links and assets

Check all of the following before delivery:

- every document path in the manifest exists;
- every output exists after rendering;
- every Markdown relative link and image reference resolves;
- every published output maps back to one canonical source;
- no source or output is orphaned or silently omitted from the manifest;
- source and output basenames match for one-source/one-output diagrams; multi-view sources may use different output names when the manifest lists the mapping.

For SVG/PNG, perform a visual check after syntax validation. Look for cropped edges, overlapping nodes, missing fonts, unreadable text, incorrect arrow direction, excessive whitespace, and Chinese glyph failures. A file existing on disk is not visual validation.

## 6. Report completion

The final report should include:

- created and modified files;
- canonical source for each diagram;
- published versus local-only files;
- exact render commands and versions;
- link and visual-check results;
- Git preflight and postflight summary;
- unresolved risks or assumptions.
