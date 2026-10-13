# AI Workflow

Codex and OpenCode CLI profiles for Flutter, React, Node and Odoo. Run the root
`setup.py` from this checkout. Its current location is `/home/abdin_02/ai_workflow`;
another machine can keep the complete directory anywhere, including paths with spaces.

## Requirements

- Python 3.11+ to run setup.
- Node.js LTS (22+) and npm when installing or upgrading a CLI. Compatible CLIs
  already on PATH can be configured without Node.
- Linux/macOS with Bash, or native Windows with PowerShell 7; x64 or ARM64.
- Windows Developer Mode or equivalent permission to create symbolic links.

Setup detects the OS, architecture, Linux distribution and WSL status. It does
not install Python, Node, shells or OS packages. Missing prerequisites produce
an actionable error. Run as your normal user, not with `sudo`.

## Install

### Linux

```bash
cd /path/to/ai_workflow
python3 setup.py
python3 setup.py --apply
source ~/.bashrc
```

The first command previews changes without writes or downloads. `--dry-run`
explicitly selects the same mode. `--apply` installs missing tools and configures
the workflow. Compatible installed versions are kept unless `--upgrade` is used.

### macOS

Use Bash even if your default terminal uses Zsh:

```bash
bash -l
python3 /path/to/ai_workflow/setup.py
python3 /path/to/ai_workflow/setup.py --apply
source ~/.bash_profile
```

Linux defaults to `~/.bashrc`; macOS to `~/.bash_profile`.
Use `--bashrc PATH` to select another Bash startup file. Do not source these
launchers in Zsh or Fish.

### Native Windows

Install the prerequisites, then open a new PowerShell 7 terminal:

```powershell
winget install --id Microsoft.PowerShell --source winget
winget install --id Python.Python.3.14 --source winget
winget install --id OpenJS.NodeJS.LTS --source winget
```

Enable Developer Mode for symbolic links. From the workflow checkout:

```powershell
py -3 setup.py --powershell-profile "$PROFILE"
py -3 setup.py --powershell-profile "$PROFILE" --apply
. $PROFILE
```

Pass the `$PROFILE` of your actual PowerShell host. Setup checks link creation
before installing packages or changing configuration; it does not change
execution policy. If scripts are blocked, review `Get-ExecutionPolicy -List`
and your machine's policy. WSL is optional and uses the Linux route instead.

## What gets installed

Missing tools use the official npm packages `@openai/codex@latest` and
`opencode-ai@1`. Codex must be >= 0.134.0. OpenCode stays on the 1.x family used
by these profiles; OpenCode 2 requires a separate migration. Official npm
installation references: [OpenAI](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)
and [OpenCode](https://opencode.ai/docs/).

New CLI installations use `~/.local/share/ai-workflow/npm` as a private prefix.
Setup adds its executable directory to PATH in the selected startup file; it
does not change npm's global prefix or remove other installations. Downloads
need internet access. A failed package installation stops before workflow
configuration is applied.

The existing Codex installer generates native profile TOML, creates profile and
skill links, and applies plugin ownership policy. Root setup sources both tools'
launcher files using managed shell blocks. Repeated unchanged setup does not
duplicate blocks or create new backups. Existing unmanaged settings and
credentials are preserved; launcher/link conflicts stop the operation.

Plain `codex` and every `codex-<profile>` command read Markdown files directly
from `codex_config/shared/instructions/` on every launch. This is enabled by the
normal `python3 setup.py --apply` installation; no extra flag is needed. Edit
those shared files and start a new session to pick up changes, without rerunning
setup. Shared rule contents are passed to the process and are not stored in
`~/.codex/config.toml` or profile TOML files.

Setup does not create a global `~/.codex/AGENTS.md`. It removes the old
workflow-owned entry symlink and preserves unrelated personal guidance. The
`--install-shared-rules` flag is accepted only for compatibility. Reload your
shell after first installation using the command printed by setup.

## Start working

Authenticate separately on each new machine:

```text
codex login
opencode auth login
```

Then enter your project directory and run its shortcut:

| Command | Selected profile |
| --- | --- |
| `codex-flutter` | Codex Flutter |
| `codex-jaspr` | Codex Jaspr |
| `codex-react` | Codex React |
| `codex-node` | Codex Node |
| `codex-odoo` | Codex Odoo 19 |
| `opencode-flutter` | OpenCode `profiles/flutter` |
| `opencode-jaspr` | OpenCode `profiles/jaspr` |
| `opencode-react` | OpenCode `profiles/react` |
| `opencode-node` | OpenCode `profiles/node` |
| `opencode-python` | OpenCode `profiles/python` |
| `opencode-odoo` | Alias for OpenCode `profiles/python` |

These are shell functions: they preserve the project directory and forward
arguments. Codex uses `--profile`; OpenCode sets `OPENCODE_CONFIG_DIR` for the
invocation and restores its previous value in PowerShell. Plain `codex` and
`opencode` remain available. Start fresh sessions after changing profiles or
instructions; these launchers do not switch existing desktop/IDE conversations.
Codex Odoo and OpenCode Python/Odoo have separate rules and skill sets.

## Rules and skills

| Resource | Source / runtime location |
| --- | --- |
| Setup entry point | `setup.py` |
| Codex build manifests | `codex_config/profiles/*/profile.json` |
| Odoo rules | `codex_config/profiles/odoo/instructions/odoo-core.md`, `odoo-review-rules.md` |
| Generated Odoo instructions | `codex_config/profiles/odoo/config.toml` |
| Odoo runtime link | `~/.codex/odoo.config.toml` |
| Other runtime profiles | `~/.codex/{flutter,jaspr,react,node}.config.toml` |
| Shared / profile skills | `codex_config/shared/skills`, `codex_config/profiles/*/skills` |
| Skill links | `~/.agents/skills/ai-workflow-*` |
| Plugin policy | `codex_config/plugin-profiles.json` |
| OpenCode profiles | `opencode_config/profiles/*/opencode.jsonc` |
| Shell launchers | `{codex_config,opencode_config}/shell/launchers.{bash,ps1}` |

`CODEX_HOME` or `--codex-home` changes the Codex runtime destination;
`--skills-dir` changes skill-link placement. Normally keep the defaults.
Edit Markdown/manifests for permanent rule changes, then rerun setup.

Profile rules are assembled into `developer_instructions`. `/status` can show
`Agents.md: <none>` while the Odoo profile is active: this field does not list
profile developer instructions or skills. Project `AGENTS.md` files still load
independently. Prose guidance differs from command-approval `.rules` files.

Shared skills (`find-skills`, `git-commit`, `git-interactive-rebase`,
`trello-workflow`, `writing-guidelines`) are enabled in plain Codex and every
profile. Domain skills remain profile-specific. Flutter, Jaspr, React and Node have
specialist agents; Odoo uses conditional review instructions in the main session.

`dart-flutter@dart-flutter` is enabled only for Flutter. Unlisted plugins keep
their existing settings. Setup does not install plugins, MCP servers or external
tools on a new machine: install/connect them separately and authenticate there.
Discover plugin IDs with `codex plugin list --json`, edit `plugin-profiles.json`,
then reinstall to change ownership. See the [Codex guide](codex_config/README.md#plugin-isolation).
Profile selection organizes configuration; project and managed overrides can
still apply, and accounts/sessions are not isolated.

### Jaspr

Use `codex-jaspr` or `opencode-jaspr` from a Jaspr project. The profile includes nine
Jaspr skills, nine selected existing Dart skills, three Dart/Jaspr state skills,
and the existing shared skills. Three specialists cover planning, UI, and data flow.
The Dart/Flutter plugin stays Flutter-only. Jaspr inherits your model settings.

Eight library-specific skills were added to Flutter: `bloc-signals`, `signals-dart`,
`signals-flutter`, `signals-hooks`, `signals-lint`, `signals-migration-6-to-7`,
`signals-preact-dart`, and `kaisel`. These skills do not prescribe changing an
existing app's state management or router. Nothing new is enabled in plain Codex
or OpenCode. See [source decisions](codex_config/profiles/jaspr/source-map.md).

### OpenCode skill isolation

OpenCode also discovers `~/.agents/skills`, including Codex's linked domain skills.
`OPENCODE_CONFIG_DIR` adds a configuration layer; it does not turn off discovery.
Setup merges `opencode_config/opencode.jsonc`'s `permission.skill` policy into the
user's global OpenCode config. Other model/provider/tool settings are preserved.
The target is under `${XDG_CONFIG_HOME:-~/.config}/opencode`: existing
`opencode.jsonc` is preferred, otherwise `opencode.json`. Automatic merging accepts
strict JSON; JSONC comments/trailing commas cause a preflight refusal rather than
silently losing comments. Backups go under `setup-backups/`.

Plain `opencode` allows only the five shared workflow skills and the built-in
`customize-opencode`. Other skills default to `deny`. Flutter allows its Dart/Flutter
skills, React its three active local skills, Node `node-service-workflow`, and
Python/Odoo its Odoo skills. The profiles include the shared allowlist too.
Node/Odoo domain skills and the extra shared skills come from Codex's links when
both tools are installed. Add a general skill name to the allowlists explicitly.

Apply only this policy to an existing installation, without changing Codex or CLIs:

```bash
python3 setup.py --opencode-only
python3 setup.py --opencode-only --apply
```

Restart OpenCode after changing permissions. `opencode debug skill` reports all
**discovered** skills, including denied ones; inspect `opencode debug agent build`
and `opencode debug agent plan` for effective permissions. OpenCode hides denied
skills from the agent and rejects loading them. Project or per-agent overrides
can change these defaults. See [official skill permissions](https://opencode.ai/docs/skills/#configure-permissions)
and [configuration merging](https://opencode.ai/docs/config/#precedence-order).

## Update and relocate

```bash
python3 setup.py --skip-cli-install --apply
python3 setup.py --upgrade
python3 setup.py --upgrade --apply
```

Use `--codex-version 0.159.3 --opencode-version 1.18.32` to select exact releases.
These flags affect packages being installed; add `--upgrade` to replace a detected
CLI. The private-prefix copy takes precedence without uninstalling other copies.
Windows commands also need `--powershell-profile "$PROFILE"`.

Transfer the full source checkout except `setup-backups/`, `codex_config/backups/`,
`codex_config/installation.json`, caches, `node_modules/` and credentials. Keep
`opencode_config/profiles/global` beside the other profiles. Do not transfer
runtime `.codex` or `.agents` trees. Rerun setup to regenerate destination paths.
When moving within the same machine, uninstall the old managed Codex integration
first: links pointing to another checkout are treated as conflicts.

## Verify

```bash
python3 setup.py --skip-cli-install
type codex-odoo opencode-odoo
codex-odoo --version
opencode-odoo --version
codex --profile odoo debug prompt-input
opencode-odoo debug config
```

An unchanged preview has empty `write`, `symlink`, `remove_owned_links` and
`npm_install`. Version output checks availability only. `debug prompt-input`
shows the locally assembled Codex input without a model request: look for
`# Active workflow profile: odoo`. Its output may include personal guidance;
review it before sharing. In PowerShell use `Get-Command` instead of `type`.

If shortcuts are missing, reload the selected startup file in the correct shell.
Install Node LTS and reopen the terminal when npm is missing. Use `--upgrade` for
an outdated Codex. Reconcile reported function/link conflicts before rerunning.

Regression checks, using temporary homes and no model requests:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tests/verify_opencode.py
python3 -B codex_config/tests/verify_profiles.py
python3 -B codex_config/tests/verify_plugin_profiles.py
python3 -B codex_config/tests/verify_powershell.py
```

Validation runs on Linux. Platform detection and PowerShell generation are
tested locally; native Windows/macOS execution and real package downloads on
those systems still need platform validation.

## Backups and removal

Codex keeps backups in `codex_config/backups/` and locations in
`codex_config/installation.json`. Root setup keeps shell backups with manifests
under `setup-backups/`. Inspect them before restoring to preserve later edits.

```bash
python3 codex_config/scripts/uninstall.py
python3 codex_config/scripts/uninstall.py --apply
```

Then remove only the `ai_workflow OpenCode launchers` and `ai_workflow CLI PATH`
marked blocks from the selected shell file. Open a new terminal. Uninstall keeps
sources, credentials and CLI packages. This setup restores workflow resources,
not a complete machine image: model preferences, account access and separately
installed plugins/tools need their own configuration.
