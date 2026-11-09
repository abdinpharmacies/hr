# Agent metadata

`GUIDE.md` is the provider-neutral source of truth for this skill. The files in this directory are optional host integrations, not separate implementations of the workflow.

## Codex

[`openai.yaml`](openai.yaml) supplies Codex UI metadata such as the display name, default prompt, and implicit invocation policy. Codex creates and understands this file; it is not a general agent configuration format.

## Other agents

Do not add invented `anthropic.yaml`, `opencode.yaml`, or `deepseek.yaml` files. Those hosts do not share the `agents/openai.yaml` schema. Use the host's documented project entrypoint instead:

- Claude Code: [`CLAUDE.md`](../CLAUDE.md) and, when installing as a Claude skill, the host's `.claude/skills/software-diagrams/GUIDE.md` location.
- OpenCode and DeepSeek Harness: [`AGENTS.md`](../AGENTS.md), or explicitly load [`GUIDE.md`](../GUIDE.md) through the host's skill or system-instruction mechanism.

This keeps one maintained workflow instead of copying it into provider-specific files that can drift.
