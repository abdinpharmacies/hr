"""Bounded health JSON parsing from complete, ordered command-output chunks."""
import codecs
import json
import re

MAX_BYTES = 1024 * 1024
MAX_CHECKS = 500
STATUSES = ('healthy', 'warning', 'critical', 'unknown')
START = re.compile(r'__AB_DEPLOY_HEALTH_COMMAND_START__ ([1-9][0-9]*)\Z')
END = re.compile(r'__AB_DEPLOY_HEALTH_COMMAND_END__ ([1-9][0-9]*) ([0-9]{1,3})\Z')


def _lines(chunks):
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    pending = ''
    for chunk in chunks:
        pending += decoder.decode(chunk)
        while '\n' in pending:
            line, pending = pending.split('\n', 1)
            if len(line.encode()) > MAX_BYTES:
                raise ValueError('A command-output line exceeds the health report limit.')
            yield line.rstrip('\r')
        if len(pending.encode()) > MAX_BYTES:
            raise ValueError('A command-output line exceeds the health report limit.')
    pending += decoder.decode(b'', final=True)
    if pending:
        yield pending.rstrip('\r')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON keys are not allowed.')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Non-finite JSON numbers are not allowed.')


def _checks(text, command, index):
    value = json.loads(text, object_pairs_hook=_object, parse_constant=_reject_constant)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'checks'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Expected schema_version 1 and a checks array.')
    rows = value['checks']
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CHECKS:
        raise ValueError('Expected between 1 and 500 checks.')
    checks, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {'id', 'status', 'details', 'duration_ms'}:
            raise ValueError('Invalid check fields.')
        identifier = row.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', identifier) or identifier in seen:
            raise ValueError('Check identifiers must be valid and unique within each command.')
        if row.get('status') not in STATUSES or not isinstance(row.get('details'), str) or len(row['details']) > 4096:
            raise ValueError('Invalid check status or diagnostic details.')
        if 'duration_ms' in row and (type(row['duration_ms']) is not int or not 0 <= row['duration_ms'] <= 86400000):
            raise ValueError('Invalid check duration.')
        seen.add(identifier)
        checks.append(dict(row, id=f"{command['line_id']}:{identifier}", check_id=identifier,
                           command_line_id=command['line_id'], command_id=command['command_id'],
                           command_name=command['name']))
    return checks


def parse(chunks, commands, translate=None):
    """Never echo rejected input in errors; preserve other commands' valid results."""
    _ = translate or (lambda message, *args: message % args if args else message)
    checks, errors, blocks, completed = [], [], {}, {}
    current = None
    capturing = False
    captured_bytes = 0
    invalid = set()
    try:
        for line in _lines(chunks):
            start, end = START.fullmatch(line), END.fullmatch(line)
            if start:
                index = int(start[1])
                if current is not None or index > len(commands) or index in blocks:
                    raise ValueError('Invalid command output framing.')
                current, capturing = index, False
                blocks[index] = []
            elif end:
                index, rc = int(end[1]), int(end[2])
                if current != index or rc > 255:
                    raise ValueError('Invalid command completion framing.')
                if capturing:
                    invalid.add(index)
                completed[index] = rc
                current, capturing = None, False
            elif current is not None:
                if line == 'AB_DEPLOY_HEALTH_BEGIN':
                    if capturing or blocks[current]:
                        invalid.add(current)
                    capturing = True
                    blocks[current].append([])
                elif line == 'AB_DEPLOY_HEALTH_END':
                    if not capturing:
                        invalid.add(current)
                    capturing = False
                elif capturing:
                    captured_bytes += len(line.encode()) + 1
                    if captured_bytes > MAX_BYTES:
                        raise ValueError('Health JSON exceeds 1 MiB.')
                    blocks[current][-1].append(line)
    except (ValueError, UnicodeError):
        errors.append(_('Command output is invalid, oversized, or incomplete.'))
    for index, command in enumerate(commands, 1):
        command_blocks = blocks.get(index, [])
        error = None
        valid = []
        if index in invalid or len(command_blocks) != 1 or index not in completed:
            error = _('Expected one complete health JSON block and command completion.')
        else:
            try:
                valid = _checks('\n'.join(command_blocks[0]), command, index)
                if len(checks) + len(valid) > MAX_CHECKS:
                    valid = []
                    raise ValueError('Combined report exceeds 500 checks.')
            except (ValueError, TypeError, RecursionError):
                error = _('Health JSON does not match the required schema or limits.')
            if completed.get(index):
                error = _('Health command exited with a nonzero status.')
        checks.extend(valid)
        if error:
            errors.append(_('Command %s: %s', index, error))
            checks.append({'id': f"collection:{command['line_id']}", 'check_id': 'collection_error',
                           'command_line_id': command['line_id'], 'command_id': command['command_id'],
                           'command_name': command['name'], 'status': 'unknown', 'details': error})
    if errors and not any(row['status'] == 'unknown' for row in checks):
        checks.append({'id': 'collection_error', 'check_id': 'collection_error', 'status': 'unknown',
                       'details': errors[0]})
    # Synthetic collection errors are included in the same bounded result count.
    if len(checks) > MAX_CHECKS:
        priority = {'critical': 0, 'unknown': 1, 'warning': 2, 'healthy': 3}
        retained = sorted((row for row in checks if row['id'] != 'collection_error'), key=lambda row: priority[row['status']])
        checks = retained[:MAX_CHECKS - 1] + [{'id': 'collection_error', 'status': 'unknown',
                                          'details': _('Combined report exceeds 500 checks.')}]
        errors.append(_('Combined report exceeds 500 checks.'))
    return checks, errors


def overall(checks):
    statuses = {row['status'] for row in checks}
    return next((status for status in ('critical', 'unknown', 'warning') if status in statuses), 'healthy' if checks else 'unknown')
