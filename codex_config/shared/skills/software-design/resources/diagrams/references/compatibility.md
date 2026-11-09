# Platform and agent compatibility

## Source of truth

Keep the diagram workflow in the repository root:

- `GUIDE.md` contains the provider-neutral instructions.
- `scripts/` contains reproducible setup and rendering commands.
- `references/` contains tool-specific operational notes.
- `agents/openai.yaml`, `CLAUDE.md`, and `AGENTS.md` are host entrypoints or metadata only.

Do not maintain separate copies of the workflow for each model provider.

## Operating systems

| Platform | Required runtime | Setup | Render |
| --- | --- | --- | --- |
| Windows 10/11 | Node.js 20+, Java 17+, PowerShell 7+, npm | `npm ci` then `pwsh ./scripts/bootstrap.ps1` | `pwsh ./scripts/render-all.ps1` |
| macOS | Node.js 20+, Java 17+, Bash, `curl`, `unzip`, npm | `npm ci` then `bash ./scripts/bootstrap.sh` | `bash ./scripts/render-all.sh` |
| Linux | Node.js 20+, Java 17+, Bash, `curl`, `unzip`, npm | `npm ci` then `bash ./scripts/bootstrap.sh` | `bash ./scripts/render-all.sh` |
| WSL | Node.js 20+, Java 17+, Bash, `curl`, `unzip`, npm | Use the Unix scripts inside WSL | Use the Unix scripts inside WSL |

On a clean checkout, run `npm ci` from `skillRoot` before bootstrap. Bootstrap downloads the configured PlantUML and Structurizr versions into `skillRoot/tools/bin/` when those files are absent; it does not replace an existing tool automatically. Graphviz and D2 use the pinned Node/WASM packages in `skillRoot/node_modules/`, so native `dot` and `d2` binaries are not required. `drawio-headless` is rebuilt during bootstrap so its platform helper is available after `npm ci` in `skillRoot`.

The standard gallery is rendered from `skillRoot/examples/shop/` into `skillRoot/examples/shop/rendered/`.

The `Cross-platform render` GitHub Actions workflow runs the gallery on Ubuntu, macOS, and Windows. The existing `Validate diagrams / render` check remains the fast Linux validation used by branch protection.

## Agent hosts

| Host | Entry point | Notes |
| --- | --- | --- |
| Codex | Root skill folder plus `agents/openai.yaml` | Install the folder under the host's skills directory. `$software-diagrams` and the UI metadata are Codex features. |
| Claude Code | `CLAUDE.md`; optionally `.claude/skills/software-diagrams/GUIDE.md` | Claude Code does not consume `agents/openai.yaml`. |
| OpenCode | `AGENTS.md` or its documented skills directory | Load the root `GUIDE.md`; there is no portable `opencode.yaml` contract used here. |
| DeepSeek Harness | Harness skill/system-instruction configuration plus `GUIDE.md` | The renderer scripts are independent of the model provider. Use `AGENTS.md` when the harness supports repository agent instructions. |
| Other agents | Their documented instruction or skill mechanism | Give the agent the root `GUIDE.md` and keep the repository scripts available. |

The model provider does not change the renderer requirements. An agent must still have Node.js, Java, and the platform utilities listed above, plus network access during bootstrap unless the pinned tools are already cached.

## Windows UTF-8 diagnostics

Before running Python, `npx`, or a helper that prints non-ASCII text in PowerShell 7, initialize UTF-8 output:

```powershell
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
```

If a search helper reports `UnicodeEncodeError` for an emoji or Chinese text, treat it as a console encoding failure. Fix the session encoding and retry before diagnosing a missing skill or invalid diagram.

`bootstrap.ps1` checks Node.js, npm, Java, and PowerShell before downloading tools. It does not install the skill itself, and installing the skill with `npx skills add` does not install renderers.
