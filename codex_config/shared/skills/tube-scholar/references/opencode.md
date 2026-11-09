# OpenCode execution

Ask to use `tube-scholar`; the agent loads it through its native skill capability.
No custom slash command is installed. Resolve resources relative to the loaded
`SKILL.md`. The workflow registers a canonical `tube-scholar` directory through
`opencode_config/skills/tube-scholar`; this matters for OpenCode 2's path-based IDs.
Codex UI metadata does not configure OpenCode.

The general policy and every profile allow this skill. OpenCode 1 uses
`permission.skill`; OpenCode 2 represents effective permissions as ordered
`skill` rules. Loading a skill does not grant shell or subagent execution rights.
Use the selected agent's effective permissions and tools. Delegate the fact-check
only when that agent exposes and permits a suitable reviewer; otherwise disclose
a same-session review. Do not assume a particular reviewer role or change agents
just to bypass a permission.

Use the available shell, web and image-reading tools for the shared workflow.
Deliver local output paths by default. Publishing requires an authorized target
and an available tool. Keep one portable source across plain OpenCode and all
profiles; do not copy instructions into each agent prompt.
