"""Standalone remote log follower. Standard library only; never imports Odoo."""
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time

HEADER = re.compile(rb'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[,\.]\d+\s+\d+\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s')


class EntryFilter:
    """Stream records and multiline tracebacks without buffering huge lines."""
    def __init__(self, output):
        self.output = output
        self.prefix = b''
        self.line_start = True
        self.keep = False
        self.end_time = None
        self.start_time = None

    def feed(self, data):
        for part in data.splitlines(keepends=True):
            if self.line_start:
                self.prefix += part
                if not self.prefix.endswith(b'\n') and len(self.prefix) < 512:
                    continue
                part, self.prefix = self.prefix, b''
                match = HEADER.match(part)
                if match:
                    self.keep = match[1] in (b'WARNING', b'ERROR', b'CRITICAL')
                    # Standard Odoo logs use UTC. Bound by the remote clock.
                    stamp = part[:23].replace(b',', b'.')
                    if self.start_time and stamp < self.start_time:
                        self.keep = False
                    if self.end_time and stamp > self.end_time:
                        self.keep = False
                self.line_start = False
            if self.keep:
                self.output.write(part)
            if part.endswith(b'\n'):
                self.line_start = True

    def finish(self):
        if self.prefix:
            self.feed(b'\n')


def clock():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


class Collector:
    def __init__(self, path, directory):
        self.path = Path(path)
        self.directory = Path(directory)
        self.source = None
        self.identity = None
        self.anchor = b''
        self.warnings = []
        self.meta = {'state': 'collecting', 'started_at': '', 'finished_at': '', 'warnings': [], 'size': 0}
        self.output = open(self.directory / 'odoo_warnings.log', 'wb', buffering=0)
        self.filter = EntryFilter(self.output)

    def warn(self, message):
        if message not in self.warnings and len(self.warnings) < 10:
            self.warnings.append(message)

    def publish(self, state=None):
        if state:
            self.meta['state'] = state
        self.meta.update(warnings=self.warnings, size=self.output.tell())
        temporary = self.directory / 'odoo_capture.json.tmp'
        temporary.write_text(json.dumps(self.meta))
        temporary.replace(self.directory / 'odoo_capture.json')

    def open_source(self, initial=False):
        try:
            self.source = open(self.path, 'rb', buffering=0)
            stat = os.fstat(self.source.fileno())
            self.identity = (stat.st_dev, stat.st_ino)
            if initial:
                self.source.seek(0, 2)
            self.anchor = b''
        except OSError:
            self.source = None
            self.warn('Odoo log is missing or unreadable; some entries may be unavailable.')

    def drain(self):
        if not self.source:
            return
        position = self.source.tell()
        size = os.fstat(self.source.fileno()).st_size
        if size < position or (self.anchor and os.pread(self.source.fileno(), len(self.anchor), position - len(self.anchor)) != self.anchor):
            self.warn('Log truncation detected; entries between polls may be missing.')
            self.source.seek(0)
            self.filter.finish()
            self.filter.keep = False
        # Snapshot EOF: never chase an actively growing file indefinitely.
        remaining = max(0, os.fstat(self.source.fileno()).st_size - self.source.tell())
        while remaining:
            chunk = self.source.read(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            self.filter.feed(chunk)
        position = self.source.tell()
        self.anchor = os.pread(self.source.fileno(), min(position, 32), max(0, position - 32))

    def poll(self):
        try:
            self.drain()
            try:
                stat = self.path.stat()
                identity = (stat.st_dev, stat.st_ino)
            except OSError:
                self.warn('Odoo log path disappeared or became unreadable during capture.')
                return
            if self.source is None:
                self.open_source()
                self.drain()
            elif identity != self.identity:
                self.warn('Log rotation detected; entries written to older files after rotation may be missing.')
                self.source.close()
                self.filter.finish()
                self.filter.keep = False
                self.open_source()
                self.drain()
        except OSError:
            self.warn('Log reading failed; capture may be incomplete.')
        self.publish()

    def run(self, parent_pid):
        self.open_source(initial=True)
        self.publish()
        (self.directory / 'odoo_capture.ready').touch()
        try:
            if (self.directory / 'odoo_capture.skip').exists():
                self.warn('Capture did not start before command execution.')
                return
            while not (self.directory / 'started_at').exists():
                if (self.directory / 'finished_at').exists() or (self.directory / 'odoo_capture.skip').exists():
                    self.warn('Capture did not start before command execution.')
                    return
                if not parent_alive(parent_pid):
                    self.warn('Execution wrapper exited before log capture started.')
                    return
                time.sleep(.05)
            start = (self.directory / 'started_at').read_text().strip()
            self.meta['started_at'] = start
            self.filter.start_time = start.replace('T', ' ').rstrip('Z').encode()
            while True:
                finish = self.directory / 'finished_at'
                if finish.exists():
                    self.meta['finished_at'] = finish.read_text().strip()
                    self.filter.end_time = self.meta['finished_at'].replace('T', ' ').rstrip('Z').encode()
                    self.poll()
                    break
                if not parent_alive(parent_pid):
                    self.meta['finished_at'] = clock()
                    self.warn('Execution wrapper disappeared; exact end boundary is unavailable.')
                    self.poll()
                    break
                self.poll()
                time.sleep(.1)
        finally:
            self.filter.finish()
            self.publish('warning' if self.warnings else 'done')
            if self.source:
                self.source.close()
            self.output.close()


def parent_alive(pid):
    try:
        os.kill(pid, 0)  # Existence check only; never sends a terminating signal.
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


if __name__ == '__main__':
    directory = Path(sys.argv[2])
    try:
        Collector(sys.argv[1], directory).run(int(sys.argv[3]))
    except Exception:
        # Never affect the Bash script or expose arbitrary exception content.
        temp = directory / 'odoo_capture.json.tmp'
        temp.write_text(json.dumps({'state': 'error', 'warnings': ['Odoo log collector failed.'], 'size': (directory / 'odoo_warnings.log').stat().st_size if (directory / 'odoo_warnings.log').exists() else 0}))
        temp.replace(directory / 'odoo_capture.json')
        (directory / 'odoo_capture.ready').touch()
