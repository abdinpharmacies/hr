# Verification checkpoint

Completed 2026-09-23 with Codex CLI 0.156.1.

- Native --profile and debug prompt-input: all four profiles load only their own
  managed instructions and the expected managed skills (Flutter 33, React 6,
  Node 4, Odoo 4). These totals include three shared skills.
- Base session: zero managed skills enabled by default.
- Native app-server --strict-config plus config/read and skills/list: all four
  generated profile layers accepted; no imported skill parse errors. Role
  declarations: Flutter 3, React 1, Node 1, Odoo 1.
- All 38 active skill sources pass the skill-creator metadata validator.
- Launcher argument forwarding, paths containing spaces, repeat installation,
  collision refusal, and uninstall preservation tests passed.
- Final installed launchers tested from fresh Bash shells using the real
  ~/.bashrc: all four returned success with the correct profile and skill set.
- All 3432 existing files under ~/.config/opencode were hashed before/after
  installation and remained unchanged. The reference Git clone is clean.
- Existing Codex base settings and Bash startup content were preserved.
- All managed profile and skill symlinks resolve successfully.
- A fresh installer dry-run reports no writes or new links.

Checks used local configuration/prompt readers; no model completion, delegated
specialist task, deployment, or external integration was invoked. Optional React
packages remain inactive. Existing unrelated global plugins/skills remain shared.

Original OpenCode launchers were not found in the available shell files. Their
exact behavior remains unverified; see AUDIT.md. No application code in the video
 downloader project was changed during this profile-system task.
