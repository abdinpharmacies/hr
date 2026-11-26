import argparse
import ast
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    artifacts = []
    for module in ['ab_crm_sales_workspace', 'ab_crm_website', 'crm_messaging_gateway']:
        source = root / module
        if module != 'crm_messaging_gateway':
            manifest = ast.literal_eval((source / '__manifest__.py').read_text())
            if not manifest.get('author') or not manifest.get('developer'):
                raise ValueError('Missing addon author or developer metadata')
        members = []
        for path in sorted(source.rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(source)
            if any(part in {'tests', '__pycache__', 'migrations', '.pytest_cache'} for part in relative.parts):
                continue
            if path.suffix in {'.pyc', '.pyo'} or path.name in {'requirements-dev.txt', 'benchmark.py'}:
                continue
            if module == 'crm_messaging_gateway' and (
                relative.parts[0] not in {'app', 'deploy', 'changelog.d'}
                and relative.name not in {'requirements.lock', 'README.md'}):
                continue
            if path.suffix == '.py':
                ast.parse(path.read_text(), filename=str(relative))
            members.append((relative, path.read_bytes()))
        checksum = '\n'.join(hashlib.sha256(data).hexdigest() + '  ' + str(relative)
                             for relative, data in members) + '\n'
        destination = arguments.output / (module + '.zip')
        with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
            for relative, data in members:
                archive.writestr(str(Path(module) / relative), data)
            archive.writestr(module + '/SHA256SUMS', checksum)
        with ZipFile(destination) as archive:
            if archive.testzip() is not None:
                raise ValueError('Invalid runtime archive')
            for relative, data in members:
                if archive.read(str(Path(module) / relative)) != data:
                    raise ValueError('Runtime archive differs from source')
        artifacts.append({'artifact': destination.name, 'files': len(members),
                          'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    (arguments.output / 'artifacts.json').write_text(json.dumps(artifacts, indent=2) + '\n')
    print(json.dumps(artifacts, indent=2))


if __name__ == '__main__':
    main()
