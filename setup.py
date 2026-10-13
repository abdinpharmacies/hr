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
    if name == 'opencode' and found[0] != 1:
        raise ValueError('These profiles target OpenCode 1.x; OpenCode 2 needs a separate migration.')
    return '.'.join(map(str, found))


def package_version(value):
    if not re.fullmatch(r'(?:latest|\d+(?:\.\d+){0,2}(?:-[A-Za-z0-9.-]+)?)', value):
        raise argparse.ArgumentTypeError('Use latest, a major version, or a numeric release version.')
    return value


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
    names = r'(?:opencode-(?:flutter|jaspr|react|node|python|odoo)|Invoke-AiWorkflowOpenCode)'
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


def opencode_plan():
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
    parser.add_argument('--opencode-version', type=package_version, default='1')
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
    if args.opencode_version == 'latest' or not args.opencode_version.startswith(('1.', '1-')) and args.opencode_version != '1':
        parser.error('--opencode-version must select the supported 1.x release family.')
    info = system_info()
    opencode_files = opencode_plan()
    if args.opencode_only:
        if args.upgrade:
            parser.error('--opencode-only does not install or upgrade CLIs.')
        changed = [str(p) for p, text in opencode_files.items()
                   if not p.exists() or p.read_text(encoding='utf-8-sig') != text]
        print(json.dumps({'write': changed, 'apply': args.apply}, indent=2))
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
    installer = load_installer()
    files, links = installer.plan(codex_home, skills_dir, rc,
                                  shell='powershell' if system == 'Windows' else 'bash',
                                  install_shared_rules=args.install_shared_rules)
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
    for name, package, requested in [('codex', '@openai/codex', args.codex_version),
                                     ('opencode', 'opencode-ai', args.opencode_version)]:
        executable = shutil.which(name)
        if args.upgrade or not executable:
            if args.skip_cli_install:
                raise ValueError(f'{name} is missing from PATH; omit --skip-cli-install to install it.')
            packages.append(f'{package}@{requested}')
        else:
            existing[name] = {'path': executable, 'version': validate_cli(name, executable)}
    npm = shutil.which('npm')
    node = shutil.which('node')
    if packages and (not npm or not node or version(node) < (22, 0, 0)):
        raise ValueError(prerequisite_hint(system))
    retired = installer.retired_skill_links(skills_dir) + installer.retired_instruction_links(codex_home)
    print(json.dumps({'system': info, 'root': str(ROOT), 'existing_cli': existing,
                      'npm_install': packages, 'npm_prefix': str(prefix), 'write': changed,
                      'symlink': changed_links, 'remove_owned_links': [str(p) for p in retired],
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
