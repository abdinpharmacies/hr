import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import install


def codex_command():
    """Return the command used to launch Codex.

    On Windows an npm-installed ``codex`` resolves to a ``.cmd`` shim, which is
    executed through cmd.exe and limited to about 8K characters. Profile
    instructions can exceed that, so prefer the package's Node entry point,
    which is launched directly by node.exe and has the larger Windows limit.
    """
    executable = shutil.which('codex')
    if not executable:
        raise SystemExit('Codex CLI not found on PATH.')
    path = Path(executable)
    if os.name == 'nt' and path.suffix.lower() in {'.cmd', '.bat'}:
        wrapper = path.parent / 'node_modules/@openai/codex/bin/codex.js'
        node = shutil.which('node')
        if wrapper.is_file() and node:
            return [node, str(wrapper)]
    return [executable]


def launch_arguments(arguments):
    profile = None
    explicit_guidance = None
    forwarded = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == '--':
            forwarded.extend(arguments[index:])
            break
        if argument in ('--profile', '-p') and index + 1 < len(arguments):
            profile = arguments[index + 1]
            forwarded.extend(arguments[index:index + 2])
            index += 2
            continue
        if argument.startswith('--profile='):
            profile = argument.split('=', 1)[1]
        elif argument.startswith('-p') and len(argument) > 2:
            profile = argument[2:]
        override = None
        count = 1
        if argument in ('--config', '-c') and index + 1 < len(arguments):
            override = arguments[index + 1]
            count = 2
        elif argument.startswith('--config='):
            override = argument.split('=', 1)[1]
        elif argument.startswith('-c') and len(argument) > 2:
            override = argument[2:]
        if override is not None and override.partition('=')[0].strip() == 'developer_instructions':
            value = override.partition('=')[2]
            try:
                explicit_guidance = tomllib.loads('value = ' + value)['value']
            except tomllib.TOMLDecodeError:
                explicit_guidance = value
            if not isinstance(explicit_guidance, str):
                raise ValueError('developer_instructions must be a string.')
        else:
            forwarded.extend(arguments[index:index + count])
        index += count
    if profile is not None and not re.fullmatch(r'[A-Za-z0-9_-]+', profile):
        raise ValueError('Invalid Codex profile name.')
    return profile, explicit_guidance, forwarded


def developer_instructions(arguments, codex_home):
    profile, explicit, forwarded = launch_arguments(arguments)
    guidance = ''
    configs = [codex_home / 'config.toml']
    if profile:
        configs.append(codex_home / f'{profile}.config.toml')
    for path in configs:
        if path.exists():
            config = tomllib.loads(path.read_text(encoding='utf-8-sig'))
            guidance = config.get('developer_instructions', guidance)
    if explicit is not None:
        guidance = explicit
    guidance = install.strip_managed(guidance, install.RULES_START, install.RULES_END).strip()
    sources = install.shared_instructions()
    if not sources:
        raise ValueError(f'No Markdown instruction files found in {install.ROOT / "shared/instructions"}.')
    shared = '\n\n'.join(path.read_text(encoding='utf-8-sig').strip() for path in sources)
    return '\n\n'.join(part for part in (shared, guidance) if part), forwarded


def main():
    command = codex_command()
    codex_home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()
    try:
        guidance, arguments = developer_instructions(sys.argv[1:], codex_home)
    except (OSError, ValueError) as error:
        raise SystemExit(f'Cannot load Codex instructions: {error}') from error
    override = 'developer_instructions=' + json.dumps(guidance, ensure_ascii=False)
    command = [*command, '--config', override, *arguments]
    if os.name == 'nt':
        # os.execv does not quote arguments containing spaces on Windows.
        raise SystemExit(subprocess.run(command).returncode)
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
