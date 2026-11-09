# Claude Code project guidance

For software engineering diagram work, read [`GUIDE.md`](GUIDE.md). It is the provider-neutral source of truth for DSL selection, rendering, validation, and Markdown/LaTeX embedding.

Use the repository-local scripts rather than assuming global renderer installations:

- Windows: `pwsh ./scripts/bootstrap.ps1` and `pwsh ./scripts/render-all.ps1`
- macOS/Linux: `bash ./scripts/bootstrap.sh` and `bash ./scripts/render-all.sh`

Keep editable diagram sources alongside generated outputs. The `agents/openai.yaml` file is Codex-only UI metadata and does not need to be loaded by Claude Code.
