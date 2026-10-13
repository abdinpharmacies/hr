#!/usr/bin/env python3
"""Install native Codex profile layers without changing OpenCode or credentials."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('flutter', 'jaspr', 'react', 'node', 'odoo')
START = '# BEGIN ai_workflow managed skills'
END = '# END ai_workflow managed skills'
SHELL_START = '# BEGIN ai_workflow Codex launchers'
SHELL_END = '# END ai_workflow Codex launchers'
RULES_START = '<!-- BEGIN ai_workflow shared instructions -->'
RULES_END = '<!-- END ai_workflow shared instructions -->'


def shell_block(shell):
    launcher = ROOT / 'shell' / ('launchers.ps1' if shell == 'powershell' else 'launchers.bash')
    try:
        relative = launcher.relative_to(Path.home())
    except ValueError:
        relative = None
    if shell == 'powershell':
        quoted = "'" + str(relative or launcher).replace("'", "''") + "'"
        expression = '(Join-Path $HOME ' + quoted + ')' if relative else quoted
        return f'if (Test-Path -LiteralPath {expression}) {{\n    . {expression}\n}}\n'
    value = str(relative or launcher).replace("'", "'\\''")
    expression = ('"$HOME"/' if relative else '') + "'" + value + "'"
    return f'if [ -f {expression} ]; then\n    . {expression}\nfi\n'


def check_link_support(parent):
    while not parent.exists():
        parent = parent.parent
    try:
        with tempfile.TemporaryDirectory(prefix='codex-link-check-', dir=parent) as temp:
            root = Path(temp)
            (root / 'file').write_text('probe', encoding='utf-8')
            (root / 'directory').mkdir()
            (root / 'file-link').symlink_to('file')
            (root / 'directory-link').symlink_to('directory', target_is_directory=True)
    except OSError as error:
        raise SystemExit('Symbolic links are unavailable. On Windows, enable Developer Mode '
                         'or obtain link-creation permission before installing; no config was changed.') from error


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def link_target(target, parent):
    try:
        return os.path.relpath(target, parent)
    except ValueError:
        # Windows cannot express a relative path between different drives.
        return str(target.resolve())


def block(value):
    return "'''\n" + value.rstrip() + "\n'''" if "'''" not in value else quote(value)


def strip_managed(text, start, end):
    if text.count(start) != text.count(end) or text.count(start) > 1:
        raise ValueError(f'Invalid managed markers: {start}')
    return re.sub(r'(?m)^' + re.escape(start) + r'\n.*?^' + re.escape(end) + r'\n?', '', text, flags=re.S)


def managed_skills():
    result = []
    for group in ('shared', *PROFILES):
        directory = ROOT / ('shared' if group == 'shared' else f'profiles/{group}') / 'skills'
        for skill in sorted(directory.glob('*/SKILL.md')):
            result.append((group, skill.parent.resolve()))
    return result


def included_skills(manifest):
    available = {path for _, path in managed_skills()}
    result = set()
    for relative in manifest.get('include_skills', []):
        path = (ROOT / relative).resolve()
        if path not in available:
            raise ValueError(f'Unknown managed skill in include_skills: {relative}')
        result.add(path)
    return result


def skill_entries(entries):
    return ''.join('\n[[skills.config]]\npath = ' + quote(e['path']) + '\nenabled = ' + str(e['enabled']).lower() + '\n' for e in entries)


def plugin_policy():
    policy = json.loads((ROOT / 'plugin-profiles.json').read_text(encoding='utf-8-sig'))
    if not isinstance(policy, dict):
        raise ValueError('plugin-profiles.json must map plugin IDs to profile-name lists.')
    for plugin, profiles in policy.items():
        if (not re.fullmatch(r'[A-Za-z0-9_-]+@[A-Za-z0-9_-]+', plugin)
                or not isinstance(profiles, list) or not profiles
                or any(profile not in PROFILES for profile in profiles)):
            raise ValueError(f'Invalid plugin profile assignment: {plugin}')
    return policy


def plugin_entries(policy, profile=None):
    return ''.join('\n[plugins.' + quote(plugin) + ']\nenabled = '
                   + str(profile in profiles).lower() + '\n'
                   for plugin, profiles in policy.items())


def set_plugin_enabled(text, plugin, enabled):
    """Patch one explicit table without reformatting unrelated user configuration."""
    before = tomllib.loads(text)
    settings = before.get('plugins', {}).get(plugin, {})
    if settings.get('enabled') is enabled:
        return text
    expected = copy.deepcopy(before)
    expected.setdefault('plugins', {}).setdefault(plugin, {})['enabled'] = enabled
    assignment = 'enabled = ' + str(enabled).lower() + '\n'
    if plugin not in before.get('plugins', {}):
        result = text.rstrip() + '\n\n[plugins.' + quote(plugin) + ']\n' + assignment
    else:
        result = None
        headers = list(re.finditer(r'(?m)^[ \t]*\[[^\n]+\][ \t]*(?:#[^\n]*)?$', text))
        for index, header in enumerate(headers):
            try:
                parsed = tomllib.loads(header.group() + '\n__probe__ = true\n')
            except tomllib.TOMLDecodeError:
                continue
            if parsed != {'plugins': {plugin: {'__probe__': True}}}:
                continue
            end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
            body = text[header.end():end]
            pattern = r'(?m)^([ \t]*enabled[ \t]*=[ \t]*)(?:true|false)([ \t]*(?:#[^\n]*)?)$'
            if 'enabled' in settings:
                body, count = re.subn(pattern, lambda m: m[1] + str(enabled).lower() + m[2], body)
                if count != 1:
                    continue
            else:
                body = '\n' + assignment + body.lstrip('\n')
            result = text[:header.end()] + body + text[end:]
            break
    if result is None or tomllib.loads(result) != expected:
        raise ValueError(f'Cannot safely update {plugin}. Use an explicit [plugins.{quote(plugin)}] '
                         'table with a plain enabled boolean; no files were changed.')
    return result


def shared_instructions():
    return sorted(path for path in (ROOT / 'shared/instructions').glob('*.md')
                  if path.name not in {'AGENTS.md', 'AGENTS.override.md'})


def set_developer_instructions(text, guidance):
    before = tomllib.loads(text)
    if before.get('developer_instructions') == guidance:
        return text
    expected = copy.deepcopy(before)
    expected.pop('developer_instructions', None)
    if guidance is not None:
        expected['developer_instructions'] = guidance
    encoded = quote(guidance) if guidance is not None else ''
    if guidance and guidance.endswith('\n') and not guidance.startswith('\n'):
        encoded = block(guidance)
    assignment = '' if guidance is None else 'developer_instructions = ' + encoded + '\n'
    if 'developer_instructions' not in before:
        result = assignment + text
        if tomllib.loads(result) == expected:
            return result
    else:
        pattern = r'(?m)^[ \t]*(?:developer_instructions|"developer_instructions"|\'developer_instructions\')[ \t]*='
        for match in re.finditer(pattern, text):
            for end in [m.end() for m in re.finditer(r'\n|$', text[match.end():])]:
                candidate = text[:match.start()] + assignment + text[match.end() + end:]
                try:
                    if tomllib.loads(candidate) == expected:
                        return candidate
                except tomllib.TOMLDecodeError:
                    pass
    raise ValueError('Cannot safely update developer_instructions; no files were changed.')


def remove_shared_instructions(text):
    current = tomllib.loads(text).get('developer_instructions', '')
    if RULES_START not in current and RULES_END not in current:
        return text
    personal = strip_managed(current, RULES_START, RULES_END).rstrip()
    return set_developer_instructions(text, personal or None)


def legacy_shared_instructions(codex_home):
    path = codex_home / 'AGENTS.md'
    if path.is_symlink() or not path.exists():
        return {}
    before = path.read_text(encoding='utf-8-sig')
    after = strip_managed(before, RULES_START, RULES_END)
    return {path: after} if before != after else {}


def retired_instruction_links(codex_home):
    path = codex_home / 'AGENTS.md'
    source = ROOT / 'shared/instructions/AGENTS.md'
    return [path] if path.is_symlink() and path.resolve() == source.resolve() else []


def instructions(profile):
    manifest = json.loads((ROOT / f'profiles/{profile}/profile.json').read_text(encoding='utf-8-sig'))
    pieces = [f'# Active workflow profile: {profile}']
    shared = {p.resolve() for p in shared_instructions()}
    for relative in manifest['instructions']:
        path = ROOT / relative
        if path.resolve() not in shared:
            pieces.append(path.read_text(encoding='utf-8-sig'))
    return '\n\n'.join(pieces), manifest


def render(base_config):
    base = tomllib.loads(remove_shared_instructions(base_config))
    inherited_skills = base.get('skills', {}).get('config', [])
    all_skills = managed_skills()
    policy = plugin_policy()
    files = {}
    for profile in PROFILES:
        guidance, manifest = instructions(profile)
        included = included_skills(manifest)
        inherited_guidance = base.get('developer_instructions', '')
        if inherited_guidance:
            guidance = inherited_guidance + '\n\n' + guidance
        text = '# Generated by codex_config/scripts/install.py; edit source instructions, then reinstall.\n'
        text += 'developer_instructions = ' + block(guidance) + '\n'
        overrides = list(inherited_skills) + [{'path': str(path / 'SKILL.md'), 'enabled': group in ('shared', profile) or path in included} for group, path in all_skills]
        text += skill_entries(overrides)
        text += plugin_entries(policy, profile)
        for relative in manifest['agents']:
            if isinstance(relative, dict):
                agent_path = ROOT / relative['config_file']
                tomllib.loads(agent_path.read_text(encoding='utf-8-sig'))
                text += '\n[agents.' + quote(relative['name']) + ']\ndescription = ' + quote(relative['description']) + '\nconfig_file = ' + quote(agent_path) + '\n'
                continue
            spec = json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))
            agent_path = (ROOT / relative).with_suffix('.toml')
            agent_guidance = guidance + '\n\n' + (ROOT / spec['instructions']).read_text(encoding='utf-8-sig')
            agent_text = 'developer_instructions = ' + block(agent_guidance) + '\n'
            if spec['read_only']:
                agent_text += 'sandbox_mode = "read-only"\n\n[agents]\nenabled = false\n'
            files[agent_path] = agent_text
            text += '\n[agents.' + quote(spec['name']) + ']\ndescription = ' + quote(spec['description']) + '\nconfig_file = ' + quote(agent_path) + '\n'
        if manifest.get('config_overrides'):
            extra = (ROOT / manifest['config_overrides']).read_text(encoding='utf-8-sig')
            if set(tomllib.loads(extra)) & {'developer_instructions', 'skills', 'agents', 'plugins'}:
                raise ValueError('Profile config_overrides must not replace generated instructions, skills, agents or plugins.')
            header = re.search(r'(?m)^[ \t]*\[', extra)
            boundary = header.start() if header else len(extra)
            expected = {**tomllib.loads(text), **tomllib.loads(extra)}
            text = extra[:boundary] + '\n' + text + (('\n' + extra[boundary:]) if extra[boundary:] else '')
            if tomllib.loads(text) != expected:
                raise ValueError('Cannot safely merge profile config_overrides; no files were changed.')
        files[profile_config_path(profile)] = text
    for text in files.values():
        tomllib.loads(text)
    return files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def profile_config_path(profile):
    manifest = json.loads((ROOT / f'profiles/{profile}/profile.json').read_text(encoding='utf-8-sig'))
    filename = manifest.get('config_filename', f'{profile}.config.toml')
    if Path(filename).name != filename:
        raise ValueError(f'Invalid profile config filename: {filename}')
    return ROOT / 'profiles' / profile / filename


def plan(codex_home, skills_dir, bashrc, shell='bash', install_shared_rules=True):
    base_path = codex_home / 'config.toml'
    base_text = base_path.read_text(encoding='utf-8-sig') if base_path.exists() else ''
    unmanaged = strip_managed(base_text, START, END)
    policy = plugin_policy()
    for plugin in policy:
        unmanaged = set_plugin_enabled(unmanaged, plugin, False)
    unmanaged = remove_shared_instructions(unmanaged)
    base = tomllib.loads(unmanaged)
    for profile in PROFILES:
        if profile in base.get('profiles', {}):
            raise ValueError(f'Existing legacy profile {profile}; resolve the name conflict before installing.')
    managed = [{'path': str(path / 'SKILL.md'), 'enabled': group == 'shared'}
               for group, path in managed_skills()]
    updated_config = unmanaged.rstrip() + '\n\n' + START + '\n' + skill_entries(managed) + END + '\n'
    tomllib.loads(updated_config)
    files = render(unmanaged)
    files[ROOT / 'config.toml'] = '# Generated native base fragment; installer merges this into the existing user config.\n' + skill_entries(managed) + plugin_entries(policy)
    files[base_path] = updated_config
    files.update(legacy_shared_instructions(codex_home))
    shell_text = bashrc.read_text(encoding='utf-8-sig') if bashrc.exists() else ''
    unmanaged_shell = strip_managed(shell_text, SHELL_START, SHELL_END)
    collision = (r'(?im)^\s*function\s+(?:global:)?codex(?:-(?:flutter|jaspr|react|node|odoo))?\b|'
                 r'^\s*(?:Set|New)-Alias\s+(?:-Name\s+)?[\'\"]?codex(?:-(?:flutter|jaspr|react|node|odoo))?\b'
                 if shell == 'powershell' else
                 r'(?m)^\s*(?:function\s+)?codex(?:-(?:flutter|jaspr|react|node|odoo))?\s*\(|^\s*alias\s+codex(?:-(?:flutter|jaspr|react|node|odoo))?=')
    if re.search(collision, unmanaged_shell):
        raise ValueError('Existing Codex launcher name collision outside the managed block.')
    files[bashrc] = unmanaged_shell.rstrip() + '\n\n' + SHELL_START + '\n' + shell_block(shell) + SHELL_END + '\n'
    links = {codex_home / f'{p}.config.toml': profile_config_path(p) for p in PROFILES}
    links.update({skills_dir / f'ai-workflow-{group}-{path.name}': path for group, path in managed_skills()})
    for link, target in links.items():
        if link.exists() or link.is_symlink():
            legacy_odoo = ROOT / 'profiles/odoo/odoo.config.toml'
            owned_old_profile = (link == codex_home / 'odoo.config.toml'
                                 and link.is_symlink() and link.resolve() == legacy_odoo)
            if not owned_old_profile and (not link.is_symlink() or link.resolve() != target.resolve()):
                raise ValueError(f'Refusing to replace existing unrelated path: {link}')
    for path in (base_path, bashrc):
        if path.is_symlink():
            raise ValueError(f'Refusing to replace a symlinked user file: {path}')
    return files, links


def retired_skill_links(skills_dir):
    manifest = json.loads((ROOT / 'profiles/odoo/profile.json').read_text(encoding='utf-8-sig'))
    result = []
    for name in manifest.get('retired_skills', []):
        if Path(name).name != name:
            raise ValueError(f'Invalid retired skill name: {name}')
        link = skills_dir / f'ai-workflow-odoo-{name}'
        target = ROOT / 'profiles/odoo/skills' / name
        if link.is_symlink() and link.resolve() == target:
            result.append(link)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply after preflight; default prints a reviewable plan.')
    parser.add_argument('--install-shared-rules', action='store_true',
                        help='Compatibility flag; shared instructions are loaded by the shell launcher.')
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents/skills')
    shell_options = parser.add_mutually_exclusive_group()
    shell_options.add_argument('--bashrc', type=Path)
    shell_options.add_argument('--powershell-profile', type=Path,
                               help='Native PowerShell profile path; pass "$PROFILE" from that shell.')
    args = parser.parse_args()
    if os.name == 'nt' and args.powershell_profile is None:
        parser.error('On Windows, pass --powershell-profile "$PROFILE" from PowerShell.')
    shell = 'powershell' if args.powershell_profile is not None else 'bash'
    args.bashrc = args.powershell_profile or args.bashrc or Path.home() / '.bashrc'
    args.codex_home = args.codex_home.expanduser().resolve()
    args.skills_dir = args.skills_dir.expanduser().resolve()
    args.bashrc = args.bashrc.expanduser().absolute()
    executable = shutil.which('codex')
    if not executable:
        raise SystemExit('Codex CLI not found on PATH. Install the native CLI or official npm package.')
    version_text = subprocess.check_output([executable, '--version'], text=True, stderr=subprocess.DEVNULL)
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_text)
    if not match or tuple(map(int, match.groups())) < (0, 134, 0):
        raise SystemExit('Codex >= 0.134.0 is required for native *.config.toml profiles.')
    files, links = plan(args.codex_home, args.skills_dir, args.bashrc, shell=shell,
                        install_shared_rules=args.install_shared_rules)
    changed = {p: text for p, text in files.items() if not p.exists() or p.read_text(encoding='utf-8-sig') != text}
    changed_links = {p: t for p, t in links.items() if not p.is_symlink() or p.resolve() != t.resolve()}
    retired = retired_skill_links(args.skills_dir) + retired_instruction_links(args.codex_home)
    print(json.dumps({'write': [str(p) for p in changed], 'symlink': {str(p): str(t) for p, t in changed_links.items()}, 'remove_owned_links': [str(p) for p in retired], 'apply': args.apply}, indent=2))
    if not args.apply or not (changed or changed_links or retired):
        return
    if changed_links:
        for parent in {args.codex_home.parent, args.skills_dir.parent}:
            check_link_support(parent)
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = ROOT / 'backups' / timestamp
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    before = {}
    for index, path in enumerate(changed):
        before[str(path)] = {'existed': path.exists(), 'sha256': sha(path)}
        if path.exists():
            dest = backup / f'{index}-{path.name}'
            shutil.copy2(path, dest)
            before[str(path)]['backup'] = str(dest)
    for path, text in changed.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
        temporary = path.with_name(path.name + '.ai-workflow-tmp')
        with temporary.open('x', encoding='utf-8', newline='\n') as file:
            file.write(text)
        temporary.chmod(mode)
        temporary.replace(path)
    for link in [*changed_links, *retired]:
        if link.is_symlink():
            before[str(link)] = {'symlink': os.readlink(link)}
    for link, target in changed_links.items():
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(link_target(target, link.parent), target_is_directory=target.is_dir())
    for link in retired:
        link.unlink()
    (backup / 'manifest.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'installation.json').write_text(json.dumps({'codex_version': version_text.strip(), 'codex_home': str(args.codex_home), 'skills_dir': str(args.skills_dir), 'bashrc': str(args.bashrc), 'shell': shell, 'backup': str(backup), 'profiles': list(PROFILES)}, indent=2) + '\n', encoding='utf-8')
    print('Installed. Open a new PowerShell terminal or run . $PROFILE.' if shell == 'powershell'
          else 'Installed. Open a new Bash terminal or source ~/.bashrc.')


if __name__ == '__main__':
    main()
