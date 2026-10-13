#!/usr/bin/env python3
"""Import reference resources; never edit the OpenCode checkout."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'opencode_config'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def split_frontmatter(text):
    match = re.match(r'\A---\s*\n(.*?)\n-{3,}\s*\n', text, re.S)
    if match:
        try:
            metadata = yaml.safe_load(match[1]) or {}
        except yaml.YAMLError:
            metadata = dict(re.findall(r'^(name|description):\s*(.*)$', match[1], re.M))
        return metadata, text[match.end():].lstrip()
    if text.startswith('name:'):
        header, body = text.split('\n\n', 1)
        return yaml.safe_load(header), body
    return {}, text


def adapt(text):
    text = text.replace('compatibility: opencode', 'compatibility: codex')
    text = text.replace('~/.config/opencode/skills/git-commit/SKILL.md', '../git-commit/SKILL.md')
    text = text.replace("`AGENTS.md`, `CLAUDE.md`, `.opencode/` rules/skills", "`AGENTS.md`, `.codex/` configuration, `.agents/skills/`, and the active profile instructions")
    text = text.replace('OpenCode loads Skills on demand', 'Codex loads skills on demand')
    text = text.replace('Official OpenCode Skills documentation', 'Official Codex skills documentation')
    text = text.replace('OpenCode Skills: https://opencode.ai/docs/skills', 'Codex skills: https://learn.chatgpt.com/docs/build-skills')
    text = text.replace('OpenCode — Agent Skills: https://opencode.ai/docs/skills', 'Codex — Agent Skills: https://learn.chatgpt.com/docs/build-skills')
    text = text.replace('Use AskQuestion (or ask conversationally)', 'Use an available user-input tool (or ask conversationally)')
    return text


def import_skill(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True)
    meta, body = split_frontmatter((src / 'SKILL.md').read_text())
    if not meta.get('name') or not meta.get('description'):
        raise ValueError(f'Missing skill metadata: {src}')
    meta['name'] = dst.name
    if meta.get('compatibility') == 'opencode':
        meta['compatibility'] = 'Codex; required project SDKs and tools must be available.'
    if 'compatibility' in meta:
        meta.setdefault('metadata', {})['compatibility'] = meta.pop('compatibility')
    meta['description'] = meta['description'].replace('<ViewTransition>', 'ViewTransition')
    if isinstance(meta.get('metadata'), dict):
        meta['metadata'].pop('model', None)
        meta['metadata'] = {k: str(v) for k, v in meta['metadata'].items()}
    if re.search(r'MCP|launch_app|get_runtime_errors|hot_reload', body):
        body = ('## Codex tool availability\n\nUse the actual tools exposed in this session. '
                'MCP names in this guide are capability examples, not guaranteed Codex tools. '
                'If unavailable, use the installed Dart/Flutter CLI for equivalent checks; '
                'report any live inspection that could not be performed. Do not invent tool calls.\n\n' + body)
    write(dst / 'SKILL.md', '---\n' + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + '---\n\n' + adapt(body))


def main():
    records = []
    for original, profile in [('flutter', 'flutter'), ('react', 'react'), ('node', 'node'), ('python', 'odoo')]:
        if profile == 'odoo':
            continue
        config = json.loads((SOURCE / 'profiles' / original / 'opencode.jsonc').read_text())
        rule_paths = []
        for ref in config['instructions']:
            src = (SOURCE / 'profiles' / original / ref).resolve()
            relative = Path('shared/instructions' if '/global/' in str(src) else f'profiles/{profile}/instructions') / src.name
            _, body = split_frontmatter(src.read_text())
            write(ROOT / relative, body)
            rule_paths.append(str(relative))
        manifest = {'name': profile, 'source_profile': original, 'instructions': rule_paths, 'agents': []}
        for src in sorted((SOURCE / 'profiles' / original / 'skills').glob('*')):
            if not (src / 'SKILL.md').is_file():
                continue
            if src.name == 'flutter-intl-localization':
                continue
            name = 'flutter-intl-localization' if src.name == 'flutter-setup-localization' else src.name
            if src.name == 'flutter-debugging-skill':
                name = 'flutter-debugging'
            dst = ROOT / 'profiles' / profile / 'skills' / name
            import_skill(src, dst)
            records.append({'source': str(src.relative_to(SOURCE)), 'target': str(dst.relative_to(ROOT))})
        write(ROOT / 'profiles' / profile / 'profile.json', json.dumps(manifest, indent=2) + '\n')
    for src in sorted((SOURCE / 'skills').iterdir()):
        dst = ROOT / 'shared' / 'skills' / src.name
        import_skill(src, dst)
        records.append({'source': str(src.relative_to(SOURCE)), 'target': str(dst.relative_to(ROOT))})
    # Optional deployment resources remain opt-in and are never installed automatically.
    shutil.copytree(SOURCE / 'profiles/react/optional', ROOT / 'profiles/react/optional', dirs_exist_ok=True)
    for file in (ROOT / 'profiles/react/optional').rglob('*.md'):
        text = file.read_text().replace('~/.claude/skills/deploy-to-vercel/resources/deploy.sh', '<this-skill-directory>/resources/deploy.sh')
        write(file, text)
    for src in sorted((SOURCE / 'profiles/flutter/agents').glob('*.md')):
        text = src.read_text()
        if src.stem == 'figma-ui-builder':
            body = text[text.index('You are a Flutter'):]
            description = 'Implement Flutter presentation widgets from Figma using available design tools; keep domain/data work separate.'
            body = body.replace('convert `-` to `` in node IDs', 'normalize node IDs as required by the installed Figma tool')
            body = body.replace('before calling check descriptors in the MCP folder', 'from the tools actually available in this session')
            body = body.replace('For write actions in Figma (code-design), load **figma-use** before every `use_figma` call.', 'For authorized Figma write actions, follow the installed Figma tool or skill instructions if available.')
            body = body.replace('For full-page Figma builds, also load **figma-generate-design**.', 'Use any available Figma design skill when relevant; do not assume a named skill is installed.')
        else:
            meta, body = split_frontmatter(text)
            description = meta.get('description', src.stem)
        body = body.replace('Package imports: `package:cursor_course/...`.', "Derive package imports from the current project's pubspec.yaml; do not assume a package name.")
        body = body.replace('1. Current repository implementation\n2. Explicit user requirements', '1. Explicit user requirements\n2. Current repository implementation')
        body = body.replace('# Important architecture rules for this task family', '# Conditional examples for the original onboarding task\n\nThe following named classes, defaults, and workout examples apply only when the current user requests that same architecture and the repository confirms it. Never impose them on unrelated projects.')
        body = ('# Codex adaptation\n\nFollow the active profile and current project instructions. '
                'Explicit user choices override these reusable defaults. Use only tools available '
                'in this session. Treat named project tokens, Cubit conventions, assets, and '
                'localization helpers below as examples unless the current repository confirms them. '
                'Ask only for missing choices; do not ask again when already answered.\n\n' + body)
        write(ROOT / 'profiles/flutter/agents' / (src.stem + '.md'), body)
        agent = {'name': src.stem, 'description': description, 'instructions': f'profiles/flutter/agents/{src.stem}.md', 'read_only': src.stem == 'flutter-plan-architect'}
        write(ROOT / 'profiles/flutter/agents' / (src.stem + '.json'), json.dumps(agent, indent=2) + '\n')
    commit = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    write(ROOT / 'docs/import-manifest.json', json.dumps({'repository': 'https://github.com/Mo7amed-fawzy/my_ai_workflow.git', 'commit': commit, 'skills': records, 'changes': ['Merged two malformed overlapping localization skills into flutter-intl-localization using flutter-setup-localization as the canonical source.', 'Normalized skill frontmatter and folder/name matches.', 'Removed non-Codex model hints from skill metadata.', 'Adapted OpenCode paths and tool assumptions.', 'Converted Flutter agent behavior and removed universal assumptions about the original onboarding project.']}, indent=2) + '\n')
    for manifest_path in (ROOT / 'profiles').glob('*/profile.json'):
        if manifest_path.parent.name == 'odoo':
            continue
        manifest = json.loads(manifest_path.read_text())
        manifest['agents'] = [str(path.relative_to(ROOT)) for path in sorted((manifest_path.parent / 'agents').glob('*.json'))]
        write(manifest_path, json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
