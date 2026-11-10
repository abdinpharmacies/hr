import csv
import io
import re

from .legacy_activation import normalize_legacy_phone


REFERENCE_COLUMNS = ('source_id', 'eplus_serial', 'code', 'id')
USED_COLUMNS = {*REFERENCE_COLUMNS, 'name', 'mobile_phone', 'active', 'default_store_id'}
MAX_RECORD_SIZE = 131072
MAX_RECORD_LINES = 32
MAX_ROWS = 600000
CORRECTED_CODES = {'header_normalized', 'delimiter_detected', 'trailing_empty_columns', 'trimmed', 'phone_normalized', 'name_fallback', 'name_shortened'}
INFO_CODES = {'unused_column', 'blank_row', 'inactive', 'existing_reference', 'existing_phone'}


def issue(column, code, value='', normalized=''):
    return {
        'column_name': str(column).replace('\x00', '\\x00')[:200],
        'issue_code': code,
        'original_value': str(value).replace('\x00', '\\x00')[:1000],
        'normalized_value': str(normalized).replace('\x00', '\\x00')[:1000],
    }


def quote_column(text, delimiter):
    column = 0
    state = 'start'
    index = 0
    while index < len(text):
        char = text[index]
        if state == 'quoted':
            if char == '"':
                if index + 1 < len(text) and text[index + 1] == '"':
                    index += 1
                else:
                    state = 'closed'
        elif char == delimiter:
            column += 1
            state = 'start'
        elif char in '\r\n':
            if state != 'quoted':
                state = 'start'
        elif state == 'start' and char == '"':
            state = 'quoted'
        elif state == 'closed':
            return column
        else:
            state = 'plain'
        index += 1
    return column


def parse_record(text, delimiter):
    return list(csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True))


def normalized_phone(value):
    value = value.strip().translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    if re.fullmatch(r'0?1[0125][0-9]{8}\.0+', value):
        value = value.split('.')[0]
    if re.fullmatch(r'1[0125][0-9]{8}', value):
        value = '0' + value
    return normalize_legacy_phone(value, strict=False) or ''


def record_anchor(rows, headers):
    if not headers or headers[0] not in REFERENCE_COLUMNS or len(rows) != 1 or len(rows[0]) != len(headers):
        return False
    values = dict(zip(headers, rows[0]))
    return bool(
        re.fullmatch(r'[A-Za-z0-9_-]{1,80}', rows[0][0].strip())
        and normalized_phone(values.get('mobile_phone', ''))
        and values.get('active', 't').strip().lower() in {'t', 'true', '1', 'yes', 'y', 'f', 'false', '0', 'no', 'n'}
    )


def csv_events(binary, encoding='auto', max_rows=MAX_ROWS):
    prefix = binary.read(4)
    binary.seek(0)
    codec = ('utf-16' if prefix.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig') if encoding == 'auto' else encoding
    source = io.TextIOWrapper(binary, encoding=codec, errors='replace', newline='')
    try:
        headers = originals = []
        for event in text_events(source, max_rows=max_rows):
            headers = event.get('columns', headers)
            originals = event.get('original_columns', originals)
            event['columns'] = headers
            event['original_columns'] = originals
            yield event
    finally:
        source.detach()


def text_events(source, max_rows=MAX_ROWS):
    first = source.readline(MAX_RECORD_SIZE + 1)
    if not first:
        yield {'number': 0, 'start': 1, 'end': 1, 'values': {}, 'issues': [issue('(file)', 'empty_file')], 'blocked': True}
        return
    choices = []
    for delimiter in (',', ';', '\t', '|'):
        try:
            rows = parse_record(first, delimiter)
        except csv.Error:
            continue
        if len(rows) == 1:
            headers = [value.strip().lower() for value in rows[0]]
            score = int('mobile_phone' in headers) + int(bool(set(headers).intersection(REFERENCE_COLUMNS)))
            choices.append((score, len(headers), delimiter, rows[0], headers))
    if not choices or len(first) > MAX_RECORD_SIZE:
        yield {'number': 0, 'start': 1, 'end': 1, 'values': {}, 'issues': [issue('(header)', 'invalid_header')], 'blocked': True}
        return
    _score, _size, delimiter, originals, headers = max(choices, key=lambda choice: choice[:2])
    problems = []
    blocked = False
    for original, header in zip(originals, headers):
        if not header or headers.count(header) > 1:
            problems.append(issue(header or '(header)', 'duplicate_header', original))
            blocked = True
        elif '\ufffd' in header or '\x00' in header:
            problems.append(issue('(header)', 'encoding', original))
            blocked = True
        elif header not in USED_COLUMNS:
            problems.append(issue(header, 'unused_column'))
        if original != header:
            problems.append(issue(header, 'header_normalized', original, header))
    if 'mobile_phone' not in headers:
        problems.append(issue('mobile_phone', 'missing_header'))
        blocked = True
    if not set(headers).intersection(REFERENCE_COLUMNS):
        problems.append(issue('source_id / eplus_serial / code / id', 'missing_header'))
        blocked = True
    if delimiter != ',':
        problems.append(issue('(file)', 'delimiter_detected', 'TAB' if delimiter == '\t' else delimiter))
    yield {'number': 0, 'start': 1, 'end': 1, 'values': {}, 'issues': problems, 'blocked': blocked, 'columns': headers, 'original_columns': originals, 'raw_record': first}
    number = 0
    line_number = 1
    pending = None
    recovering = False
    while True:
        if pending:
            line, start = pending
            pending = None
        else:
            line = source.readline(MAX_RECORD_SIZE + 1)
            if not line:
                break
            line_number += 1
            start = line_number
        number += 1
        if max_rows is not None and number > max_rows:
            yield {'number': number, 'start': start, 'end': start, 'values': {}, 'issues': [issue('(file)', 'row_limit')], 'blocked': True}
            return
        buffer = line
        end = start
        record_error = None
        while True:
            if len(buffer) > MAX_RECORD_SIZE or end - start >= MAX_RECORD_LINES:
                yield {'number': number, 'start': start, 'end': end, 'values': {}, 'issues': [issue('(record)', 'record_limit')], 'blocked': True, 'raw_record': buffer}
                return
            try:
                rows = parse_record(buffer, delimiter)
                break
            except csv.Error as error:
                if str(error) != 'unexpected end of data':
                    record_error = error
                    break
                following = source.readline(MAX_RECORD_SIZE + 1)
                if not following:
                    record_error = error
                    break
                line_number += 1
                try:
                    next_rows = parse_record(following, delimiter)
                except csv.Error:
                    next_rows = []
                if record_anchor(next_rows, headers):
                    pending = following, line_number
                    record_error = error
                    break
                buffer += following
                end = line_number
        if record_error:
            index = quote_column(buffer, delimiter)
            column = headers[index] if index < len(headers) else '(record)'
            parts = buffer.split(delimiter)
            value = parts[index] if index < len(parts) else buffer
            recovering = True
            prefix = next(csv.reader(io.StringIO(buffer), delimiter=delimiter), [])[:index]
            yield {'number': number, 'start': start, 'end': end, 'values': {}, 'issues': [issue(column, 'quoting', value)], 'blocked': headers[0] not in REFERENCE_COLUMNS, 'raw_record': buffer, 'identity_values': dict(zip(headers, prefix))}
            continue
        if recovering:
            if record_anchor(rows, headers):
                recovering = False
            else:
                yield {'number': number, 'start': start, 'end': end, 'values': {}, 'issues': [issue('(record)', 'record_boundary')], 'blocked': False, 'raw_record': buffer}
                continue
        problems = []
        values = rows[0] if len(rows) == 1 else []
        source_values = list(values)
        if not values and not buffer.strip():
            problems.append(issue('(record)', 'blank_row'))
        elif len(values) > len(headers) and all(not value for value in values[len(headers):]):
            problems.append(issue('(record)', 'trailing_empty_columns', len(values), len(headers)))
            values = values[:len(headers)]
        elif len(values) != len(headers):
            problems.append(issue('(record)', 'column_count', len(values), len(headers)))
            values = []
        yield {'number': number, 'start': start, 'end': end, 'values': dict(zip(headers, values)), 'issues': problems, 'blocked': False, 'source_values': source_values, 'raw_record': buffer if not values else '', 'identity_values': dict(zip(headers, source_values)) if not values else {}}


def customer_event(event, namespace):
    values = event['values']
    problems = list(event['issues'])
    result = {**event, 'issues': problems, 'customer': None, 'phone': '', 'source_key': '', 'inactive': False, 'reserved_phones': set()}
    if event['number'] and not values:
        raw = event.get('raw_record', '').translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
        tokens = re.findall(r'(?<![\w.])(?:\+?20|0020)?0?1[0125](?:[ ()-]*[0-9]){8}(?![\w.])', raw)
        result['reserved_phones'] = {normalized_phone(token) for token in tokens} - {''}
        identity = event.get('identity_values', {})
        identifier = next(((key, identity[key].strip()) for key in REFERENCE_COLUMNS if identity.get(key, '').strip() not in {'', '0', 'NULL', '\\N'}), None)
        if identifier and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier[1]):
            result['source_key'] = f'{namespace}:{identifier[0]}:{identifier[1]}'
    if not event['number'] or not values:
        return result
    for column, value in values.items():
        if '\ufffd' in value:
            problems.append(issue(column, 'encoding', value))
        if any(ord(char) < 32 and char not in '\r\n\t' for char in value):
            problems.append(issue(column, 'control_character', value))
        if len(value) > 4096:
            problems.append(issue(column, 'field_limit', value))
    active = values.get('active', 't').strip().lower()
    if active in {'f', 'false', '0', 'no', 'n'}:
        result['inactive'] = True
        problems.append(issue('active', 'inactive', values.get('active')))
    elif active not in {'t', 'true', '1', 'yes', 'y'}:
        problems.append(issue('active', 'invalid_active', values.get('active')))
    identifier = next(((key, values[key].strip()) for key in REFERENCE_COLUMNS if values.get(key, '').strip() not in {'', '0', 'NULL', '\\N'}), None)
    if not identifier:
        problems.append(issue('source_id / eplus_serial / code / id', 'missing_reference'))
    elif not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier[1]):
        problems.append(issue(identifier[0], 'invalid_reference', values[identifier[0]]))
    else:
        result['source_key'] = f'{namespace}:{identifier[0]}:{identifier[1]}'
        if values[identifier[0]] != identifier[1]:
            problems.append(issue(identifier[0], 'trimmed', values[identifier[0]], identifier[1]))
    raw_phone = values.get('mobile_phone', '')
    phone = normalized_phone(raw_phone)
    result['phone'] = phone or ''
    if not phone:
        code = 'missing_phone' if not raw_phone.strip() else 'scientific_phone' if re.fullmatch(r'[+0-9.]+[eE][+-]?[0-9]+', raw_phone.strip()) else 'invalid_phone'
        problems.append(issue('mobile_phone', code, raw_phone))
    elif phone != raw_phone and raw_phone != '0' + phone[3:]:
        problems.append(issue('mobile_phone', 'phone_normalized', raw_phone, phone))
    name = values.get('name', '').strip()
    if not name:
        name = identifier[1] if identifier else ''
        problems.append(issue('name', 'name_fallback', values.get('name', ''), name))
    elif len(name) > 200:
        problems.append(issue('name', 'name_shortened', name, name[:200]))
    elif name != values.get('name', ''):
        problems.append(issue('name', 'trimmed', values['name'], name))
    store = values.get('default_store_id', '').strip()
    if len(store) > 80:
        problems.append(issue('default_store_id', 'store_limit', store))
    if result['source_key'] and phone:
        result['customer'] = {'source_key': result['source_key'], 'phone': phone, 'name': name[:200], 'source_store': store}
    return result
