# Codex workflow profiles

Five native Codex CLI profiles derived from the sibling `opencode_config` Git
checkout: Flutter, Jaspr, React, Node, and Python/Odoo. OpenCode has separate runtime
configuration and is not used by Codex at runtime. Use the root
[`setup.py`](../setup.py) for both CLIs and both sets of shell launchers.

## Launch

After installation, open a new Bash terminal or run `source ~/.bashrc`:
On native Windows use the PowerShell setup below instead of Bash.

```bash
cd /path/to/your/project
codex
codex-flutter
codex-jaspr
codex-react
codex-node
codex-odoo
```

Each function forwards all arguments unchanged:

```bash
codex-flutter --cd "/path/with spaces/project"
codex-react "Review this component"
codex-node exec "Explain the request flow"
```

The underlying commands are `codex --profile flutter`, `codex --profile jaspr`, `codex --profile react`,
`codex --profile node`, and `codex --profile odoo`. Exit the current session and
launch another profile to switch. Nothing rewrites a shared active-profile file;
different profiles can run concurrently. `/agent` switches agent threads, not
these configuration profiles. `resume` retains conversation history, so use a
fresh session when a clean separation of profile context is important.

## Native configuration format

Requires Codex >= 0.134.0; Jaspr integration verified against 0.160.1. Current Codex loads
`$CODEX_HOME/config.toml` (normally `~/.codex/config.toml`), then the selected
`$CODEX_HOME/<profile>.config.toml`. Legacy `[profiles.<name>]` tables are no
longer supported. This package follows the current native format.

```text
codex_config/
  config.toml                   Generated managed base fragment, no user secrets
  plugin-profiles.json           Plugin-to-profile ownership source
  shared/
    instructions/               Shared rule sources and Codex guidance
    skills/                     find-skills, git-commit, git-interactive-rebase
  profiles/
    flutter/
      profile.json              Build manifest, not a Codex config
      flutter.config.toml       Generated native profile layer
      instructions/             Nine Flutter rule sources
      skills/                   38 Flutter/Dart and optional library skills
      agents/                   Three specialist instruction/TOML pairs
    jaspr/
      profile.json              Includes selected canonical Flutter/Dart skills
      jaspr.config.toml         Generated native profile layer
      instructions/             Jaspr, web, and workflow rules
      skills/                   Nine Jaspr-specific skills
      agents/                   Planner, UI builder, data-flow architect
      source-map.md             Collected-source decisions and documentation
      source-manifest.json      Source hashes and classification
    react/
      profile.json
      react.config.toml
      instructions/             Six React rule sources
      skills/                   Three React skills and their references
      agents/                   react-ui-engineer
      optional/                 Four upstream packages, not activated
    node/
      profile.json
      node.config.toml
      instructions/
      skills/node-service-workflow/
      agents/                   node-service-engineer
    odoo/
      profile.json
      config.toml               Linked as ~/.codex/odoo.config.toml
      instructions/odoo-core.md Concise effective Odoo guidance
      instructions/source-map.md  Source classification, not injected
      instructions/content-coverage.json  Source ranges and preservation checks
      skills/                   Eight workflows with on-demand references
      instructions/odoo-review-rules.md  Four conditional review rule sections
  shell/launchers.bash
  scripts/install.py
  scripts/launch.py              Reads shared Markdown on every launch
  scripts/import_opencode.py
  scripts/uninstall.py
  tests/verify_profiles.py
  docs/
  backups/                      Local pre-change backups, not portable source
  installation.json             Local installation locations
```

The general `shared/skills/trello-workflow` skill preserves the repository's
board/card/checklist terminology and is discoverable for standalone Trello work.
Odoo historical snapshots and module UI session notes are retained in linked
skill references, not always-loaded rules. Validate source coverage with:

```bash
python3 tests/verify_odoo.py --source /opt/odoo19/custom-addons-ecommerce/AGENTS.md
```

## What loads

1. The shell source block defines `codex` and five profile launchers. They call
   `scripts/launch.py`, which reads `shared/instructions/*.md` in filename order
   on every invocation and passes their contents through a process-only
   `--config developer_instructions=...` argument to the native Codex executable.
   No configuration or instruction files are written during launch.
2. Shared rule contents are not stored in `~/.codex/config.toml` or generated
   profile/agent TOML files. Existing personal developer instructions and the
   selected profile's developer instructions are combined with the live shared
   rules. Project `AGENTS.md` discovery still works normally. Other configuration,
   model choices, authentication, arguments, and the current directory are preserved.
3. Native skill discovery follows symlinks under `~/.agents/skills`. Shared
   skills are enabled in the marked base-config block, including plain `codex`.
   Profile-specific managed skills remain disabled in the base config.
   A profile enables its own skills, explicitly reused skills from `include_skills`, and the five shared skills
   using `[[skills.config]]` with canonical `SKILL.md` paths. Skill metadata is
   discovered initially; full skill bodies load on demand. There is no per-launch
   file copying or link switching.
4. `[agents.<name>]` declarations exist only in the relevant profile. Their
   `config_file` paths point to native TOML role layers. Agent layers include the
   selected profile instructions for generated JSON/Markdown agent sources.
   Odoo uses conditional review instructions in the main session, with no custom
   role declarations. For other profiles, models and effort
   are inherited. The Flutter planner defaults to `read-only` and disables
   further subagents.
5. `plugin-profiles.json` assigns domain-specific plugins to profiles. The
   installer disables listed plugins in the base config and emits explicit
   enabled/disabled overrides in every generated profile. Dart/Flutter is
   enabled only in `flutter`; plain Codex, Jaspr, Odoo, React and Node disable it.
   Unlisted general-purpose plugins remain shared and keep their existing settings.

Edit shared rules only in `shared/instructions/`. Their latest contents are read
when you next run `codex` or any `codex-<profile>` launcher; no installer command
is needed after editing shared rules. `AGENTS.md` and `AGENTS.override.md` in that
source directory are excluded because they are legacy entry files.

Profile-specific rules remain generated from `profile.json` into native profile
TOML. Run `python3 ~/ai_workflow/codex_config/scripts/install.py --apply` after
editing those sources. Installation also removes previously generated shared
instruction blocks from configuration, while preserving personal text.

Open a new terminal or run `source ~/.bashrc` once after installing the launcher.
On PowerShell, reload your profile. Bash uses Python 3.11+ through `python3`;
PowerShell uses Python 3.11+ through `python`. The native Codex executable remains
on PATH: `command codex` in Bash and absolute executable paths bypass the wrapper,
as do IDE/app launches. Use the shell commands above for live shared instructions.
This wrapper passes instructions using a supported CLI override, not a native
folder-include setting. CLI instruction overrides take precedence over
project-level `developer_instructions`; project `AGENTS.md` is unaffected.

The old `--install-shared-rules` installer flag is accepted for compatibility.
The workflow-owned global `AGENTS.md` symlink is retired with its target recorded
in the backup manifest. Unrelated global instruction files remain untouched.
These are prose instructions, not command-approval `.rules` files. See the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).


There are no shared custom subagents in the current sources. Plain Codex receives
no custom subagents from this package; Flutter, Jaspr, React and Node specialists remain
profile-specific. Built-in agents and independently configured agents are separate.

The shared skills are `find-skills`, `git-commit`, `git-interactive-rebase`,
`trello-workflow`, and `writing-guidelines`. They are available in plain Codex and
all five profiles. Add general-purpose skills under `shared/skills/<name>/SKILL.md`,
then rerun the installer to refresh the managed paths. Start a fresh session
after changing the base skill configuration. This does not enable another
profile's specialist skills or change plugin isolation.

## Install, update, or relocate

The runtime installer requires Python 3.11+ and Codex; it uses only Python's
standard library. Review its plan, then apply:

```bash
python3 ~/ai_workflow/codex_config/scripts/install.py
python3 ~/ai_workflow/codex_config/scripts/install.py --apply
```

It preserves existing base settings, backs up changed files, checks name
collisions before writes, uses relative symlinks, and appends a marked source
block to `.bashrc`. It does not change OpenCode, credentials, model defaults,
standalone MCP servers or unrelated projects. It changes only the enabled flag
of plugins listed in `plugin-profiles.json`; installed plugin files and all
unlisted plugin settings are preserved. Generated absolute paths are derived from the
actual installation directory; no other user's home is hardcoded. Reinstall
after moving the package or editing rule/agent sources. Existing links pointing
to another installation are treated as conflicts; uninstall the old managed
installation first when moving it.

Existing skill overrides and developer instructions are preserved in the
generated profile layers at install time. Reinstall after changing those base
settings. Other base settings are inherited dynamically.

The optional `config_overrides` path in a profile manifest supplies additional
native TOML settings. Odoo uses it to preserve its existing `/opt` trust setting.
It cannot override the generated instructions, skills, agents or plugin policy.

### UI/UX Pro Max profile isolation

UI/UX Pro Max is stored once under
`profiles/flutter/skills/ui-ux-pro-max/`. React, Jaspr, and Odoo explicitly reuse
that canonical copy through `include_skills` in their `profile.json` manifests.
It stays disabled in plain Codex and Node; do not place it in `shared/skills` or
install a second unrestricted copy. The standard installer manages discovery,
canonical paths, and enablement, including the Node/base disabled entries.

The imported package includes its local search scripts, datasets, references,
MIT license, and `source-manifest.json`. It does not depend on a Downloads folder
or Claude plugin variables. Flutter and React have upstream stack datasets;
Jaspr and Odoo use general design/UX guidance together with their own profile
rules. No Jaspr/Odoo-specific upstream implementation support is implied.

After updating the canonical skill or includes, preview and apply using
`scripts/install.py`, then start a fresh profile session. Do not edit generated
profile TOML directly. Existing Jaspr model/effort and Odoo effort selections are
preserved in their `config-overrides.toml` sources when regenerating profiles.

### Plugin isolation

The current policy is `dart-flutter@dart-flutter: ["flutter"]`. The generated Odoo,
React and Node profile layers contain:

```toml
[plugins."dart-flutter@dart-flutter"]
enabled = false
```

Flutter has the same section with `enabled = true`; the user base config has
`enabled = false`. The plugin stays installed. Its bundled skills and MCP server
are enabled together only for Flutter. General browser, document, spreadsheet
and visualization plugins remain shared, as requested.

Edit `plugin-profiles.json` and rerun the installer to change ownership; do not
edit generated TOML. Start a fresh CLI session after changing policy. Trusted
project configuration and CLI overrides can still take precedence; this is
configuration selection, not an enforced security boundary. Workspace-managed
plugin states may not be overridden by this local setting. See the official
[plugin enabled setting](https://learn.chatgpt.com/docs/config-file/config-reference)
and [profile precedence](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles).

Uninstalling the workflow removes its runtime profile links but leaves the
requested base plugin state disabled; it does not uninstall the plugin or
silently enable it globally. Pre-change configuration is retained in backups.

The native Odoo profile is documented in [docs/ODOO.md](docs/ODOO.md).

`import_opencode.py` is a maintainer tool and additionally requires PyYAML.
It skips the native Odoo profile so re-importing cannot replace its source files.
Re-importing overwrites adapted upstream resources, so inspect the resulting
changes before reinstalling. It never writes to `opencode_config`.

### Native Windows / PowerShell

Use Python 3.11+, native Codex (standalone or npm shim) on PATH and Windows symbolic-link permission
(Developer Mode or an administrator-approved equivalent). In PowerShell:

```powershell
py -3 "$HOME/ai_workflow/codex_config/scripts/install.py" --powershell-profile "$PROFILE"
py -3 "$HOME/ai_workflow/codex_config/scripts/install.py" --powershell-profile "$PROFILE" --apply
. $PROFILE
codex-flutter
```

The installer sources `shell/launchers.ps1` from that PowerShell profile, preserves
existing content, writes UTF-8 and checks file/directory symlink support before
changing configuration. It does not change execution policy or install CLI tools.
PowerShell 7 is recommended. The uninstall command also handles this profile.
Do not reuse a Linux installation.json on Windows; regenerate the installation.
See the [workspace setup guide](../README.md) for automated native OpenCode launchers.
Linux-hosted tests cover this integration; Windows execution still needs a native
machine check. No WSL or Ubuntu is required for these commands.

## Limits and differences

- This is configuration isolation, not a separate account, OS sandbox, or
  session-history store. Existing user/system skills, plugins, MCP tools,
  agents, auth, and sessions remain shared unless covered by the explicit plugin
  policy. Project/CLI overrides and managed configuration can take precedence.
  New domain-specific plugins must be added to `plugin-profiles.json` to isolate
  them; this installer does not infer ownership from arbitrary plugin names.
- OpenCode wildcard skill permissions have no direct counterpart here. The
  installer enumerates exact managed skill paths; reinstall after adding skills.
- OpenCode prose `rules/*.md` become developer instructions. Codex `.rules`
  files govern command execution and are not the equivalent of coding guidance.
- `globs` and `alwaysApply` metadata are not executable Codex rule selectors.
  Scope remains explicit in the instruction prose.
- Custom role declarations use the supported config-reference mechanism.
  Agent availability does not force delegation. The original planner's granular
  OpenCode permission list is approximated by read-only defaults, no nested
  agents, and instructions. Read-only still permits read-only shell inspection;
  it is not a prohibition on every shell command. Live permission overrides can
  supersede a role's sandbox defaults.
- Imported Dart/Figma tool examples require corresponding installed tools or
  MCP connections. No new integration or credential was installed.
- Optional React packages remain outside discovery, matching the source's
  opt-in layout. They retain upstream environment-specific material and require
  review/adaptation before enabling in Codex.
- These launchers target the CLI; they do not switch an already open desktop or
  IDE conversation.
- Historical import limitations are recorded in `docs/AUDIT.md`; current
  OpenCode launchers live in `opencode_config/shell` and are installed by root setup.

## Verification and removal

```bash
python3 ~/ai_workflow/codex_config/tests/verify_profiles.py
python3 ~/ai_workflow/codex_config/tests/verify_plugin_profiles.py
python3 ~/ai_workflow/codex_config/scripts/uninstall.py
python3 ~/ai_workflow/codex_config/scripts/uninstall.py --apply
```

Verification uses an isolated temporary Codex home, native `debug prompt-input`,
and the app-server's strict configuration/skill readers. It sends no model
requests. Tests cover profile selection, skill/instruction isolation, agent
declarations, argument forwarding, paths with spaces, idempotence, and collision
refusal. They do not prove future model behavior or execute specialist work.

Uninstallation removes only this package's marked blocks and links pointing to
this installation. It preserves the source folders, backups, unrelated settings,
OpenCode, and credentials. Start a new shell afterward.

Official references checked on 2026-09-23:

- [Native profiles](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles)
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Skill discovery and enablement](https://learn.chatgpt.com/docs/build-skills)
- [Custom subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
