# Codex execution

Invoke as `$tube-scholar` or let the task description select it. The workflow's
user discovery link is `~/.agents/skills/ai-workflow-shared-tube-scholar`; resolve
supporting files relative to the loaded `SKILL.md`, including when symlinked.
`agents/openai.yaml` supplies the display name and starter prompt. Automatic
selection remains enabled.

Use the tools exposed in the session for shell execution, browsing and image
inspection. If an independent review is permitted and a subagent tool exists,
ask a fresh reviewer to follow `fact-check-brief.md`; inherit the selected model.
Otherwise disclose a same-session review. Return local file links to the HTML,
PDF and supporting files that actually exist. Respect the current write roots
and use the host's approval mechanism for required external writes or installs.

Do not create another copy in each profile or change model settings. This shared
skill is intended for plain Codex and every workflow profile.
