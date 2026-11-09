#!/usr/bin/env python3
"""Install Codex/OpenCode and this checkout's workflow profiles for the current user."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parent
OPENCODE_START = '# BEGIN ai_workflow OpenCode launchers'
OPENCODE_END = '# END ai_workflow OpenCode launchers'
PATH_START = '# BEGIN ai_workflow CLI PATH'
PATH_END = '# END ai_workflow CLI PATH'


def system_info():
    system = platform.system()
    if system not in ('Linux', 'Darwin', 'Windows'):
        raise ValueError(f'Unsupported operating system: {system}')
    machine = platform.machine().lower()
    if machine not in ('x86_64', 'amd64', 'arm64', 'aarch64'):
        raise ValueError(f'Unsupported architecture: {machine}; use x64 or ARM64.')
    distro = {}
    if system == 'Linux':
        try:
            distro = platform.freedesktop_os_release()
        except OSError:
            pass
    return {'os': system, 'architecture': machine,
            'distribution': distro.get('PRETTY_NAME', system),
            'wsl': system == 'Linux' and 'microsoft' in platform.release().lower()}


def load_installer():
    spec = importlib.util.spec_from_file_location('workflow_installer', ROOT / 'codex_config/scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def managed_shared_skills(installer):
    return [path.name for group, path in installer.managed_skills() if group == 'shared']


def shared_skill_inventory(installer):
    return {
        path.name: {
            'source': str(path.relative_to(installer.ROOT)),
            'entrypoint': str((path / 'SKILL.md').relative_to(installer.ROOT)),
            'asset_count': sum(file.is_file() for file in (path / 'assets').rglob('*')),
            'assets': sorted(str(file.relative_to(path)) for file in
                             (path / 'assets').rglob('*') if file.is_file()),
            'references': sorted(str(file.relative_to(path)) for file in
                                 (path / 'references').rglob('*.md')),
            'scripts': sorted(str(file.relative_to(path)) for file in
                              (path / 'scripts').rglob('*')
                              if file.is_file() and '__pycache__' not in file.parts
                              and file.suffix not in ('.pyc', '.pyo')),
            'flow_modes': sorted(file.stem for file in
                                 (path / 'references/flows').glob('*.md')),
            'artifact_modes': sorted(file.stem for file in
                                     (path / 'references/artifacts').glob('*.md')),
            'files': sum(file.is_file() for file in path.rglob('*')),
        }
        for group, path in installer.managed_skills() if group == 'shared'
    }


def managed_profile_skills(installer):
    result = {profile: [] for profile in installer.PROFILES}
    for group, path in installer.managed_skills():
        if group != 'shared':
            result[group].append(path.name)
    return result


def profile_retired_skill_inventory(installer):
    return {profile: names for profile in installer.PROFILES
            if (names := installer.retired_skills(profile))}


def skill_evaluation_cases(directory):
    result = {}
    for path in sorted((directory / 'evals').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        cases = data.get('scenarios') if isinstance(data, dict) else data
        if not isinstance(cases, list):
            raise ValueError(f'{path} must contain a case list or a scenarios list')
        names = [case.get('name') if isinstance(case, dict) else None for case in cases]
        if (any(not isinstance(name, str) or not name.strip() for name in names)
                or len(set(names)) != len(names)):
            raise ValueError(f'{path} must give each evaluation case a unique nonempty name')
        result[str(path.relative_to(directory))] = names
    return result


def profile_skill_inventory(installer):
    enabled = enabled_profile_skills(installer)
    result = {profile: {} for profile in installer.PROFILES}
    for group, path in installer.managed_skills():
        if group != 'shared':
            result[group][path.name] = {
                'source': str(path.relative_to(installer.ROOT)),
                'enabled_profiles': [profile for profile, names in enabled.items() if path.name in names],
            'entrypoint': str((path / 'SKILL.md').relative_to(installer.ROOT)),
            'references': sorted(str(file.relative_to(path)) for file in
                                 (path / 'references').glob('**/*') if file.is_file()),
                'reference_links': sorted(set(re.findall(
                    r'\]\((references/[^\s)]+)\)',
                    (path / 'SKILL.md').read_text(encoding='utf-8-sig')))),
                'evaluations': sorted(str(file.relative_to(path)) for file in
                                      (path / 'evals').rglob('*.json')),
                'evaluation_cases': skill_evaluation_cases(path),
                'scripts': sorted(str(file.relative_to(path)) for file in
                                  (path / 'scripts').rglob('*')
                                  if file.is_file() and '__pycache__' not in file.parts
                                  and file.suffix not in ('.pyc', '.pyo')),
                'reference_count': sum(file.is_file() for file in (path / 'references').rglob('*')),
                'files': sum(file.is_file() for file in path.rglob('*')),
            }
    return result


def profile_mcp_inventory(installer):
    result = {}
    for profile in installer.PROFILES:
        manifest = json.loads((installer.ROOT / f'profiles/{profile}/profile.json').read_text(encoding='utf-8-sig'))
        path = manifest.get('config_overrides')
        config = tomllib.loads((installer.ROOT / path).read_text(encoding='utf-8-sig')) if path else {}
        result[profile] = {name: {'command': server.get('command'), 'enabled': server.get('enabled', True)}
                           for name, server in config.get('mcp_servers', {}).items()}
    return result


def opencode_profile_mcp_inventory():
    result = {}
    for path in sorted((ROOT / 'opencode_config/profiles').glob('*/opencode.jsonc')):
        config = json.loads(path.read_text(encoding='utf-8-sig'))
        result[path.parent.name] = {
            name: {'type': server.get('type'), 'enabled': server.get('enabled', True)}
            for name, server in config.get('mcp', {}).items() if isinstance(server, dict)
        }
    return result


def profile_agent_inventory(installer):
    result = {}
    for profile in installer.PROFILES:
        manifest = json.loads((installer.ROOT / f'profiles/{profile}/profile.json').read_text(encoding='utf-8-sig'))
        agents = {}
        for entry in manifest['agents']:
            if isinstance(entry, dict):
                spec = entry
                config_file = spec['config_file']
            else:
                spec = json.loads((installer.ROOT / entry).read_text(encoding='utf-8-sig'))
                config_file = str(Path(entry).with_suffix('.toml'))
            agents[spec['name']] = {
                'description': spec['description'],
                'instructions': spec.get('instructions'),
                'config_file': config_file,
            }
        result[profile] = agents
    return result


def enabled_profile_skills(installer):
    managed = installer.managed_skills()
    result = {}
    for profile in installer.PROFILES:
        manifest = json.loads((installer.ROOT / f'profiles/{profile}/profile.json').read_text(encoding='utf-8-sig'))
        included = installer.included_skills(manifest)
        result[profile] = [path.name for group, path in managed
                           if group in ('shared', profile) or path in included]
    return result


def validate_managed_skill_entrypoints(installer):
    for _, directory in installer.managed_skills():
        entrypoint = directory / 'SKILL.md'
        text = entrypoint.read_text(encoding='utf-8-sig')
        frontmatter = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.DOTALL)
        name = (re.search(r'(?m)^name:\s*["\']?([^"\'\s]+)["\']?\s*$', frontmatter.group(1))
                if frontmatter else None)
        if not name or name.group(1) != directory.name:
            relative = entrypoint.relative_to(installer.ROOT)
            found = name.group(1) if name else '<missing>'
            raise ValueError(f'{relative} must declare name: {directory.name}; found: {found}')
        for target in re.findall(r'\]\((references/[^\s)]+)\)', text):
            reference = directory / target.split('#', 1)[0]
            if not reference.is_file():
                relative = entrypoint.relative_to(installer.ROOT)
                raise ValueError(f'{relative} references a missing file: {target}')


def validate_opencode_shared_skill_permissions(installer):
    shared = set(managed_shared_skills(installer))
    policies = [ROOT / 'opencode_config/opencode.jsonc',
                *sorted((ROOT / 'opencode_config/profiles').glob('*/opencode.jsonc'))]
    for path in policies:
        config = json.loads(path.read_text(encoding='utf-8-sig'))
        skill_policy = config.get('permission', {}).get('skill', {})
        missing = sorted(name for name in shared if skill_policy.get(name) != 'allow')
        if missing:
            relative = path.relative_to(ROOT)
            raise ValueError(f'{relative} must allow every shared skill; missing: {", ".join(missing)}')


def changed_profiles(installer, codex_home):
    managed_profiles = set()
    missing_generated = set()
    for profile in installer.PROFILES:
        link = codex_home / f'{profile}.config.toml'
        target = installer.profile_config_path(profile)
        if link.is_symlink() and link.resolve() == target.resolve():
            managed_profiles.add(profile)
            if not target.is_file():
                missing_generated.add(profile)
    if not managed_profiles:
        return list(installer.PROFILES), 'fresh-install'
    commands = [
        ['git', 'diff', '--name-only', '-z', 'HEAD', '--'],
        ['git', 'ls-files', '--others', '--exclude-standard', '-z'],
    ]
    paths = set()
    try:
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30, check=True)
            paths.update(value for value in result.stdout.split('\0') if value)
    except (OSError, subprocess.SubprocessError):
        return list(installer.PROFILES), 'git-unavailable'
    generated = {str(installer.profile_config_path(profile).relative_to(ROOT))
                 for profile in installer.PROFILES}
    changed = set()
    for value in paths:
        normalized = value.replace('\\', '/')
        if normalized.endswith(('/cli.json', '/service.json')):
            continue
        if normalized in generated:
            continue
        parts = normalized.split('/')
        if len(parts) >= 4 and parts[:2] == ['codex_config', 'profiles']:
            profile = parts[2]
            if profile in installer.PROFILES and not (parts[3] == 'agents' and normalized.endswith('.toml')):
                changed.add(profile)
    selected = changed | missing_generated
    if missing_generated:
        reason = 'git-changes-and-missing-generated-configs' if changed else 'missing-generated-configs'
    else:
        reason = 'git-changes'
    return [profile for profile in installer.PROFILES if profile in selected], reason


def selected_profiles(values, installer, codex_home):
    requested = values or ['auto']
    if 'auto' in requested or 'all' in requested:
        if len(requested) != 1:
            raise ValueError('--profile auto and --profile all cannot be combined with another profile.')
        if requested[0] == 'all':
            return list(installer.PROFILES), 'explicit-all'
        return changed_profiles(installer, codex_home)
    chosen = set(requested)
    return [profile for profile in installer.PROFILES if profile in chosen], 'explicit'


def version(executable):
    result = subprocess.run([executable, '--version'], capture_output=True, text=True,
                            timeout=30, check=True)
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
    if not match:
        raise ValueError(f'Cannot read version from {executable}: {result.stdout.strip()}')
    return tuple(map(int, match.groups()))


def validate_cli(name, executable):
    found = version(executable)
    if name == 'codex' and found < (0, 134, 0):
        raise ValueError('Codex >= 0.134.0 is required. Rerun with --upgrade.')
    if name == 'opencode' and found[0] not in (1, 2):
        raise ValueError('These profiles support OpenCode 1.x and 2.x.')
    return '.'.join(map(str, found))


def package_version(value):
    if not re.fullmatch(r'(?:latest|\d+(?:\.\d+){0,2}(?:-[A-Za-z0-9.-]+)?)', value):
        raise argparse.ArgumentTypeError('Use latest, a major version, or a numeric release version.')
    return value


def opencode_package_version(value):
    if value == 'auto':
        return value
    parsed = package_version(value)
    if not re.fullmatch(r'[12](?:\.\d+){0,2}(?:-[A-Za-z0-9.-]+)?', parsed):
        raise argparse.ArgumentTypeError('Use auto or an OpenCode 1.x/2.x release.')
    return parsed


def prerequisite_hint(system):
    if system == 'Windows':
        return 'Install Node.js LTS: winget install --id OpenJS.NodeJS.LTS --source winget. Then reopen PowerShell.'
    if system == 'Darwin':
        return 'Install Node.js LTS from nodejs.org, or use: brew install node'
    return 'Install Node.js LTS (22+) and npm for your distribution or Node version manager, then rerun.'


def shell_update(text, installer, rc, system, cli_bin):
    if rc.is_symlink():
        raise ValueError(f'Refusing to rewrite symlinked shell configuration: {rc}')
    for start, end in [(OPENCODE_START, OPENCODE_END), (PATH_START, PATH_END),
                       (installer.SHELL_START, installer.SHELL_END)]:
        text = installer.strip_managed(text, start, end)
    names = r'(?:opencode-(?:flutter|jaspr|react|node|python|odoo|wordpress|offensive)|Invoke-AiWorkflowOpenCode)'
    collision = (r'(?im)^\s*function\s+(?:global:)?' + names + r'\b|'
                 r'^\s*(?:Set|New)-Alias\s+(?:-Name\s+)?[\'\"]?' + names + r'\b'
                 if system == 'Windows' else
                 r'(?m)^\s*(?:function\s+)?' + names + r'\s*\(|^\s*alias\s+' + names + '=')
    if re.search(collision, text):
        raise ValueError(f'Existing OpenCode launcher outside the managed block in {rc}; reconcile it first.')
    if system == 'Windows':
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        launcher = ROOT / 'opencode_config/shell/launchers.ps1'
        path_block = (f"$aiWorkflowCliBin = {quote(cli_bin)}\n"
                      "if (($env:PATH -split ';') -notcontains $aiWorkflowCliBin) {\n"
                      '    $env:PATH = "$aiWorkflowCliBin;$env:PATH"\n}\n')
        source = f'if (Test-Path -LiteralPath {quote(launcher)}) {{\n    . {quote(launcher)}\n}}\n'
    else:
        launcher = ROOT / 'opencode_config/shell/launchers.bash'
        quoted_bin = shlex.quote(str(cli_bin))
        path_block = (f'case ":$PATH:" in\n    *:{quoted_bin}:*) ;;\n'
                      f'    *) export PATH={quoted_bin}:"$PATH" ;;\nesac\n')
        source = f'if [ -f {shlex.quote(str(launcher))} ]; then\n    . {shlex.quote(str(launcher))}\nfi\n'
    codex_block = (installer.SHELL_START + '\n'
                   + installer.shell_block('powershell' if system == 'Windows' else 'bash')
                   + installer.SHELL_END + '\n\n')
    return (text.rstrip() + '\n\n' + codex_block + PATH_START + '\n' + path_block + PATH_END + '\n\n'
            + OPENCODE_START + '\n' + source + OPENCODE_END + '\n')


def opencode_plan(installer):
    validate_opencode_shared_skill_permissions(installer)
    directory = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'opencode'
    path = directory / ('opencode.jsonc' if (directory / 'opencode.jsonc').exists() else 'opencode.json')
    if path.is_symlink():
        raise ValueError(f'Refusing to rewrite symlinked OpenCode configuration: {path}')
    try:
        config = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    except json.JSONDecodeError as error:
        raise ValueError(f'{path} contains JSONC comments/trailing commas. Convert it to strict JSON before automatic merging.') from error
    if not isinstance(config, dict):
        raise ValueError(f'Expected a JSON object in {path}')
    config.setdefault('$schema', 'https://opencode.ai/config.json')
    permission = config.setdefault('permission', {})
    if isinstance(permission, str):
        permission = config['permission'] = {'*': permission}
    if not isinstance(permission, dict):
        raise ValueError(f'Expected an object or action for permission in {path}')
    policy = json.loads((ROOT / 'opencode_config/opencode.jsonc').read_text(encoding='utf-8'))
    permission['skill'] = policy['permission']['skill']
    skills = config.setdefault('skills', {})
    if not isinstance(skills, dict) or not isinstance(skills.get('paths', []), list):
        raise ValueError(f'Expected skills.paths in {path}')
    shared = str(ROOT / 'opencode_config/skills')
    skills['paths'] = list(dict.fromkeys([*skills.get('paths', []), shared]))
    content = json.dumps(config, ensure_ascii=False, indent=2) + '\n'
    return {path: content}


def write_backed_up_file(rc, content, backup_root):
    if rc.exists() and rc.read_text(encoding='utf-8-sig') == content:
        return
    backup = backup_root / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    if rc.exists():
        shutil.copy2(rc, backup / rc.name)
    (backup / 'manifest.json').write_text(json.dumps({'path': str(rc), 'existed': rc.exists()}, indent=2) + '\n')
    rc.parent.mkdir(parents=True, exist_ok=True)
    temporary = rc.with_name(rc.name + '.ai-workflow-setup-tmp')
    with temporary.open('x', encoding='utf-8', newline='\n') as file:
        file.write(content)
    temporary.chmod(rc.stat().st_mode & 0o777 if rc.exists() else 0o600)
    temporary.replace(rc)


def main(argv=None):
    if sys.version_info < (3, 11):
        raise SystemExit('Python 3.11+ is required. Install it, then rerun this script.')
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='Install missing CLIs and apply configuration; default is preview.')
    mode.add_argument('--dry-run', action='store_true', help='Preview only (the default); no writes or downloads.')
    parser.add_argument('--skip-cli-install', action='store_true', help='Require existing CLIs; only configure the workflow.')
    parser.add_argument('--upgrade', action='store_true', help='Install requested CLI versions even when already present.')
    parser.add_argument('--codex-version', type=package_version, default='latest')
    parser.add_argument('--opencode-version', type=opencode_package_version, default='auto')
    parser.add_argument('--profile', action='append',
                        choices=('auto', 'all', 'flutter', 'jaspr', 'react', 'node', 'odoo'),
                        help='Update changed profiles automatically, or select one explicitly. Defaults to auto.')
    parser.add_argument('--install-shared-rules', action='store_true', help='Compatibility flag; shared instructions are read by the Codex launcher on every run.')
    parser.add_argument('--opencode-only', action='store_true',
                        help='Only merge OpenCode general-skill policy; no CLI installs or Codex changes.')
    shell = parser.add_mutually_exclusive_group()
    shell.add_argument('--bashrc', type=Path, help='Bash startup file: ~/.bashrc on Linux, ~/.bash_profile on macOS.')
    shell.add_argument('--powershell-profile', type=Path, help='On Windows pass --powershell-profile "$PROFILE".')
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents/skills')
    args = parser.parse_args(argv)
    if args.upgrade and args.skip_cli_install:
        parser.error('--upgrade and --skip-cli-install cannot be combined.')
    requested_opencode = '2' if args.opencode_version == 'auto' else args.opencode_version
    info = system_info()
    installer = load_installer()
    validate_managed_skill_entrypoints(installer)
    shared_skills = managed_shared_skills(installer)
    shared_inventory = shared_skill_inventory(installer)
    profile_inventory = profile_skill_inventory(installer)
    retired_skill_inventory = profile_retired_skill_inventory(installer)
    enabled_skills = enabled_profile_skills(installer)
    opencode_files = opencode_plan(installer)
    if args.opencode_only:
        if args.upgrade:
            parser.error('--opencode-only does not install or upgrade CLIs.')
        executable = shutil.which('opencode')
        existing = {}
        if executable:
            detected = validate_cli('opencode', executable)
            existing = {'path': executable, 'version': detected,
                        'compatibility': detected.split('.', 1)[0] + '.x'}
        changed = [str(p) for p, text in opencode_files.items()
                   if not p.exists() or p.read_text(encoding='utf-8-sig') != text]
        print(json.dumps({'existing_cli': {'opencode': existing} if existing else {},
                          'opencode_compatibility': existing.get('compatibility'),
                          'managed_shared_skills': shared_skills,
                          'shared_skill_inventory': shared_inventory,
                          'profile_skill_inventory': profile_inventory,
                          'profile_retired_skills': retired_skill_inventory,
                          'profile_mcp_inventory': profile_mcp_inventory(installer),
                          'opencode_profile_mcp_inventory': opencode_profile_mcp_inventory(),
                          'enabled_profile_skills': enabled_skills,
                          'write': changed, 'apply': args.apply}, indent=2))
        if args.apply:
            for path, text in opencode_files.items():
                write_backed_up_file(path, text, ROOT / 'setup-backups')
        return
    system = info['os']
    if system == 'Windows' and not args.powershell_profile:
        parser.error('On Windows pass --powershell-profile "$PROFILE" from PowerShell 7.')
    if system != 'Windows' and args.powershell_profile:
        parser.error('Use --bashrc on Linux/macOS; run the Windows route in native PowerShell.')
    rc = (args.powershell_profile or args.bashrc or
          Path.home() / ('.bash_profile' if system == 'Darwin' else '.bashrc')).expanduser().absolute()
    codex_home = args.codex_home.expanduser().resolve()
    skills_dir = args.skills_dir.expanduser().resolve()
    prefix = Path.home() / '.local/share/ai-workflow/npm'
    cli_bin = prefix if system == 'Windows' else prefix / 'bin'
    os.environ['PATH'] = str(cli_bin) + os.pathsep + os.environ.get('PATH', '')
    try:
        profiles, profile_selection = selected_profiles(args.profile, installer, codex_home)
    except ValueError as error:
        parser.error(str(error))
    profile_skills = managed_profile_skills(installer)
    files, links = installer.plan(codex_home, skills_dir, rc,
                                  shell='powershell' if system == 'Windows' else 'bash',
                                  install_shared_rules=args.install_shared_rules, profiles=profiles)
    final_shell = shell_update(files[rc], installer, rc, system, cli_bin)
    files[rc] = final_shell
    codex_files = set(files) - {rc}
    files.update(opencode_files)
    changed = [str(p) for p, content in files.items()
               if not p.exists() or p.read_text(encoding='utf-8-sig') != content]
    changed_links = {str(p): str(t) for p, t in links.items()
                     if not p.is_symlink() or p.resolve() != t.resolve()}
    packages = []
    existing = {}
    opencode_package = '@opencode/cli' if requested_opencode.startswith('2') else 'opencode-ai'
    for name, package, requested in [('codex', '@openai/codex', args.codex_version),
                                     ('opencode', opencode_package, requested_opencode)]:
        executable = shutil.which(name)
        if args.upgrade or not executable:
            if args.skip_cli_install:
                raise ValueError(f'{name} is missing from PATH; omit --skip-cli-install to install it.')
            packages.append(f'{package}@{requested}')
        else:
            detected = validate_cli(name, executable)
            existing[name] = {'path': executable, 'version': detected}
            if name == 'opencode':
                existing[name]['compatibility'] = detected.split('.', 1)[0] + '.x'
    npm = shutil.which('npm')
    node = shutil.which('node')
    if packages and (not npm or not node or version(node) < (22, 0, 0)):
        raise ValueError(prerequisite_hint(system))
    retired = installer.retired_skill_links(skills_dir, profiles) + installer.retired_instruction_links(codex_home) + installer.retired_profile_links(codex_home, profiles)
    print(json.dumps({'system': info, 'root': str(ROOT), 'existing_cli': existing,
                      'npm_install': packages, 'npm_prefix': str(prefix), 'write': changed,
                      'symlink': changed_links, 'remove_owned_links': [str(p) for p in retired],
                      'profile_selection': profile_selection, 'selected_profiles': profiles,
                      'opencode_compatibility': existing.get('opencode', {}).get(
                          'compatibility', requested_opencode.split('.', 1)[0] + '.x'),
                      'managed_shared_skills': shared_skills,
                      'shared_skill_inventory': shared_inventory,
                      'managed_profile_skills': profile_skills,
                      'profile_skill_inventory': profile_inventory,
                      'profile_retired_skills': retired_skill_inventory,
                          'profile_mcp_inventory': profile_mcp_inventory(installer),
                          'opencode_profile_mcp_inventory': opencode_profile_mcp_inventory(),
                      'profile_agent_inventory': profile_agent_inventory(installer),
                      'enabled_profile_skills': enabled_skills,
                      'shared_instructions': 'read from shared/instructions at launch',
                      'global_agents': 'workflow-owned entry link retired; personal guidance preserved',
                      'apply': args.apply}, indent=2), flush=True)
    if not args.apply:
        return
    if changed_links:
        for parent in (codex_home.parent, skills_dir.parent):
            installer.check_link_support(parent)
    if packages:
        subprocess.run([npm, 'install', '--global', '--prefix', str(prefix), *packages], check=True)
    for name in ('codex', 'opencode'):
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f'{name} was not found after installation; inspect {cli_bin}.')
        print(f'{name}: {validate_cli(name, executable)}', flush=True)
    command = [sys.executable, '-B', str(ROOT / 'codex_config/scripts/install.py'), '--apply',
               '--codex-home', str(codex_home), '--skills-dir', str(skills_dir),
               '--powershell-profile' if system == 'Windows' else '--bashrc', str(rc)]
    if profiles:
        for profile in profiles:
            command.extend(['--profile', profile])
    else:
        command.append('--no-profiles')
    if args.install_shared_rules:
        command.append('--install-shared-rules')
    # The native installer owns Codex backups and links; merge OpenCode after it finishes.
    if any(Path(path) in codex_files for path in changed) or changed_links or retired:
        subprocess.run(command, check=True)
    write_backed_up_file(rc, final_shell, ROOT / 'setup-backups')
    for path, text in opencode_files.items():
        write_backed_up_file(path, text, ROOT / 'setup-backups')
    reload_path = "'" + str(rc).replace("'", "''") + "'" if system == 'Windows' else shlex.quote(str(rc))
    print(f'Setup complete. Reload: {". " if system == "Windows" else "source "}{reload_path}')
    print('Authenticate separately: codex login; opencode auth login. Then launch codex-odoo or opencode-odoo.')


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f'Setup failed: {error}') from error
