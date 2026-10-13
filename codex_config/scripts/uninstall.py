#!/usr/bin/env python3
"""Remove only this installation's managed blocks and owned symlinks."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import tomllib

import install


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    record_path = install.ROOT / 'installation.json'
    if not record_path.exists():
        raise SystemExit('No installation record found.')
    record = json.loads(record_path.read_text(encoding='utf-8-sig'))
    home = Path(record['codex_home'])
    skills = Path(record['skills_dir'])
    bashrc = Path(record['bashrc'])
    replacements = {}
    for path, start, end in [
        (home / 'config.toml', install.START, install.END),
        (bashrc, install.SHELL_START, install.SHELL_END),
        (home / 'AGENTS.md', install.RULES_START, install.RULES_END),
    ]:
        if path.is_symlink():
            raise SystemExit(f'Refusing to rewrite symlinked user file: {path}')
        if path.exists():
            before = path.read_text(encoding='utf-8-sig')
            after = install.strip_managed(before, start, end)
            if path == home / 'config.toml':
                after = install.remove_shared_instructions(after)
            if before != after:
                replacements[path] = after
    if home / 'config.toml' in replacements:
        tomllib.loads(replacements[home / 'config.toml'])
    expected = {home / f'{p}.config.toml': install.profile_config_path(p) for p in install.PROFILES}
    expected.update({skills / f'ai-workflow-{group}-{path.name}': path for group, path in install.managed_skills()})
    links = [p for p, target in expected.items() if p.is_symlink() and p.resolve() == target.resolve()]
    print(json.dumps({'rewrite': [str(p) for p in replacements], 'remove_owned_links': [str(p) for p in links], 'apply': args.apply}, indent=2))
    if not args.apply:
        return
    backup = install.ROOT / 'backups' / ('uninstall-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, mode=0o700)
    for i, (path, text) in enumerate(replacements.items()):
        shutil.copy2(path, backup / f'{i}-{path.name}')
        path.write_text(text, encoding='utf-8', newline='\n')
    for link in links:
        link.unlink()
    print('Removed managed configuration and links. Open a new terminal.')


if __name__ == '__main__':
    main()
