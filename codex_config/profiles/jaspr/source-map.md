# Jaspr source decisions

The collected files are reference material, not instructions to install every upstream
workflow. `source-manifest.json` records entrypoint hashes and individual decisions.
Source files remain unchanged. Runtime paths do not depend on the collected directory.

| Source | Treatment |
| --- | --- |
| `jaspr_main/skills` | Five focused Jaspr skills, rewritten for installed-version checks; HTML/CSS references retained. |
| `official_flutter_repo/jaspr/rules` | General component/DOM guidance adapted into Jaspr rules. |
| `official_flutter_repo/jaspr/skills/data-model` | `jaspr-content-models`; no assumed flutter.dev helpers, paths, or required doc comments. |
| `official_flutter_repo/jaspr/skills/extract-to-jaspr` | Merged into `jaspr-convert-html`; converter output may be fixed and behavior migration follows the task. |
| `generate-showcase-from-video` | Excluded: editorial site workflow and absent transcript script, not a general Jaspr development skill. |
| `Poorgramer-Zack…/jaspr` | Architecture topics inform rules, routing, and testing; stale pins and API examples are not copied. |
| `shadcn_jaspr-main` | `jaspr-shadcn-ui`, activated for that package only; use the consumer project's CSS pipeline. |
| BlocSignal plugin | `bloc-signals` with linked references and supplied license; available to Flutter and Jaspr. |
| Signals skills | Flutter receives Dart, Flutter, hooks, lint, migration, and Dart Preact skills; Jaspr reuses only Dart core and Dart Preact. |
| Kaisel | Flutter only; not a Jaspr router. |
| Duplicate Jaspr and `signals_hooks` | Excluded; one canonical skill per capability/name. |
| Coverage/docs/example/preact maintenance | Excluded: upstream repository-specific automation; existing Dart coverage skill is reused. |

Eight library skills were added to Flutter. Jaspr has nine own skills and explicitly
reuses twelve canonical skill directories from Flutter in `profile.json.include_skills`.
The generator validates those paths and enables them only for the declaring profile.
No new general rules or shared skills were introduced. Generated base/other-profile
files change only to keep the new skills explicitly disabled. The Dart/Flutter plugin
policy is unchanged: Flutter alone enables it.

OpenCode uses its native custom configuration directory with an explicit skill allowlist.
Its Jaspr skill search includes the Flutter directory, but permissions expose only the
selected Dart/state skills. Codex keeps one canonical managed path per skill. Do not
create duplicate copies under Codex Jaspr just to reuse a Flutter-owned Dart skill.

Three custom agents are declared: `jaspr-plan-architect`, `jaspr-ui-builder`, and
`jaspr-data-flow-architect`. The planner is read-only and cannot delegate. Models inherit
the selected configuration. Availability does not require automatic delegation.

## Documentation checked

- [Codex native profiles](https://learn.chatgpt.com/docs/config-file/config-advanced#profiles): separate `<profile>.config.toml` layers selected by `--profile`.
- [Codex local skill control](https://learn.chatgpt.com/docs/build-skills#enable-or-disable-local-codex-skills): canonical `SKILL.md` enable/disable entries.
- [OpenCode configuration](https://opencode.ai/docs/config/#custom-directory): `OPENCODE_CONFIG_DIR` adds a merged configuration directory.
- [OpenCode skills](https://opencode.ai/docs/skills/#configure-permissions): permission rules restrict discovered skills.
- [OpenCode agents](https://opencode.ai/docs/agents/): Markdown subagents with native permissions.
- [Jaspr components](https://docs.jaspr.site/concepts/components), [client rendering](https://docs.jaspr.site/dev/client), and [routing](https://docs.jaspr.site/concepts/routing): component, hydration, and browser-boundary guidance.

The two products' profile isolation covers managed resources. Independently configured
plugins, agents, project overrides, and skills still follow each product's precedence.
