"""Opt-in file actions; never modify database records."""
import os
from pathlib import Path
import shutil
import tempfile

from common import MigrationError, digest, safe_attachment_path, settings


def filestore_roots(args):
    roots = []
    for config, database in ((args.source_config, args.source_db), (args.target_config, args.target_db)):
        base = settings(config).get('data_dir')
        if not base:
            raise MigrationError('copy-filestore requires data_dir in both configs')
        roots.append((Path(base).expanduser() / 'filestore' / database).resolve())
    source, target = roots
    if source.is_relative_to(target) or target.is_relative_to(source) or not source.is_dir():
        raise MigrationError('Filestore roots overlap or source directory is absent')
    return source, target


def copy_filestore(args, completed, save):
    source, target = filestore_roots(args)
    result = dict(copied=0, reused=0)

    def inaccessible(error):
        raise MigrationError('Cannot read a source filestore directory') from None

    for root, directories, filenames in os.walk(source, followlinks=False, onerror=inaccessible):
        if any((Path(root) / name).is_symlink() for name in directories):
            raise MigrationError('Filestore contains a symlink directory')
        for name in sorted(filenames):
            src = Path(root) / name
            if src.is_symlink() or not src.is_file():
                raise MigrationError('Filestore contains a non-regular file')
            relative = src.relative_to(source).as_posix()
            dst = safe_attachment_path(target, relative)
            checksum = digest(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if not dst.is_file() or digest(dst) != checksum:
                    raise MigrationError('Target filestore content conflicts; no overwrite performed')
                result['reused'] += 1
            else:
                fd, temporary = tempfile.mkstemp(prefix='.csv-copy-', dir=dst.parent)
                try:
                    with os.fdopen(fd, 'wb') as out, src.open('rb') as inp:
                        shutil.copyfileobj(inp, out, length=1024 * 1024)
                        out.flush()
                        os.fsync(out.fileno())
                    if digest(temporary) != checksum:
                        raise MigrationError('Source file changed during filestore copy')
                    # Hard-link publication is atomic and never overwrites a race.
                    os.link(temporary, dst)
                    directory = os.open(dst.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                    result['copied'] += 1
                finally:
                    Path(temporary).unlink(missing_ok=True)
            # Existing identical files are themselves durable retry markers.
            # Keep bounded progress metadata, rather than rewriting a growing
            # dictionary of every filename after each file.
            completed.update(result)
            if (result['copied'] + result['reused']) % 100 == 0:
                save()
    completed.update(result)
    save()
    return result


ACTIONS = {'copy-filestore': copy_filestore}


def choose_actions(value, selected):
    if value == 'menu':
        print('Extra actions:\n0. No extra action\n1. Copy source filestore (requires ir_attachment=1)', flush=True)
        answer = input('Select [0]: ').strip() or '0'
        if answer not in ('0', '1'):
            raise MigrationError('Unknown extra action choice')
        value = 'copy-filestore' if answer == '1' else None
    if not value:
        return []
    if value not in ACTIONS or 'ir_attachment' not in selected:
        raise MigrationError('copy-filestore requires ir_attachment=1')
    return [value]
