"""Conservative inspection of executable metadata; never rewrite serialized IDs."""
import ast
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit
from lxml import etree

# These fields are documentation, not executed by Odoo as record references.
DESCRIPTIVE_FIELDS = {('ir_model_fields', 'help'), ('ir_module_module', 'description')}
MARKUP_FIELDS = {('ir_ui_view', 'arch_db'), ('mail_template', 'body_html')}


def inspect_metadata(value, table, field, markers, old_ids):
    """Return reviewable fragments, keeping numeric literals local to expressions."""
    if (table, field) in DESCRIPTIVE_FIELDS:
        return []
    if isinstance(value, str) and value.startswith('{'):
        try:
            decoded = json.loads(value)
        except ValueError:
            pass
        else:
            if isinstance(decoded, dict):
                value = decoded
    translations = value if isinstance(value, dict) else {'': value}
    marker = re.compile(r'(?<![\w.])(?:' + '|'.join(re.escape(x) for x in markers) + r')(?!\w)') if markers else None
    ids = {str(i) for i in old_ids}
    findings = []

    def check(expression, location, language, link=False, conservative=False):
        expression = str(expression)
        numbers = set(re.findall(r'(?<!\w)\d+(?!\w)', expression)) & ids
        if not numbers:
            return
        def reference_key(key):
            return (isinstance(key, str) and not key.startswith('search_default_group_')
                    and (key in ('id', 'res_id') or key.endswith(('_id', '_ids'))
                         or key in markers or key.removeprefix('default_') in markers))

        def numeric(node):
            return any(isinstance(n, ast.Constant) and not isinstance(n.value, bool)
                       and str(n.value) in ids for n in ast.walk(node))

        reference = bool(conservative and marker and marker.search(expression))
        try:
            tree = ast.parse(expression.strip(), mode='eval')
        except (SyntaxError, ValueError):
            if not link:
                # Unknown expression syntax remains conservative, never executed.
                reference = bool(marker and marker.search(expression)) or bool(re.search(
                    r"['\"](?:id|res_id|default_\w+_id|\w+_ids?)['\"]", expression))
        else:
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    reference |= any(isinstance(k, ast.Constant) and reference_key(k.value) and numeric(v)
                                     for k, v in zip(node.keys, node.values))
                elif isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 3:
                    key, op, val = node.elts
                    reference |= (isinstance(key, ast.Constant) and reference_key(key.value)
                                  and isinstance(op, ast.Constant) and isinstance(op.value, str) and numeric(val))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'browse':
                        reference |= any(numeric(arg) for arg in node.args)
                elif isinstance(node, ast.Compare):
                    operands = [node.left, *node.comparators]
                    reference |= (any(marker and marker.search(ast.unparse(x)) for x in operands)
                                  and any(numeric(x) for x in operands))
        if link:
            # Ignore unrelated query flags, styles, ports, and dynamic path IDs.
            try:
                url = urlsplit(expression)
                query = parse_qsl(url.query) + parse_qsl(url.fragment)
                reference |= any(reference_key(k) and v in ids for k, v in query)
                parts = url.path.strip('/').split('/')
                if parts[:2] in (['web', 'image'], ['web', 'content']):
                    record = parts[2:3] if len(parts) > 2 and parts[2].isdigit() else parts[3:4]
                    reference |= any(v.split('-')[0] in ids for v in record)
                elif parts[:1] == ['odoo']:
                    reference |= any(v in ids for v in parts[1:])
            except ValueError:
                reference = True  # malformed link needs review when IDs occur
        if reference:
            findings.append(dict(language=language, location=location, expression=expression,
                                 candidate_ids=sorted(map(int, numbers))))

    def attributes(attrs, location, language):
        for name, value in attrs:
            if value is None:
                continue
            if name in ('domain', 'domain_force', 'filter_domain', 'context', 'eval', 'invisible', 'readonly', 'required'):
                check(value, location + '/@' + name, language)
            elif name.startswith('t-') and name not in ('t-name', 't-set', 't-call', 't-call-assets'):
                if name.startswith('t-attf-'):
                    for expression in re.findall(r'{{(.*?)}}|#\{(.*?)\}', value, re.S):
                        check(''.join(expression), location + '/@' + name, language, link=True)
                    if name in ('t-attf-href', 't-attf-src'):
                        check(value, location + '/@' + name, language, link=True)
                else:
                    check(value, location + '/@' + name, language, link=True)
            elif name in ('href', 'src', 'action'):
                check(value, location + '/@' + name, language, link=True)
            # Inline template expressions may occur in otherwise ordinary attrs.
            for expression in re.findall(r'{{(.*?)}}|#\{(.*?)\}', value, re.S):
                check(''.join(expression), location + '/@' + name, language)

    if (table, field) not in MARKUP_FIELDS and field not in ('domain', 'domain_force', 'context'):
        check(json.dumps(value), field, '', conservative=True)
        return findings

    for language, text in translations.items():
        if not isinstance(text, str):
            check(json.dumps(text), field, language)
            continue
        if (table, field) not in MARKUP_FIELDS:
            check(text, field, language)
            continue
        if table == 'ir_ui_view':
            try:
                root = etree.fromstring(text.encode(), etree.XMLParser(resolve_entities=False, no_network=True))
            except etree.XMLSyntaxError:
                findings.append(dict(language=language, location=field, reason='Malformed XML; manual reference review required'))
                continue
            for node in root.iter():
                if not isinstance(node.tag, str):
                    continue
                location = node.getroottree().getpath(node)
                attributes(node.attrib.items(), location, language)
                # Action/view definitions can store expressions in field bodies.
                if node.tag == 'field' and node.get('name') in ('domain', 'context', 'domain_force'):
                    check(node.text or '', location, language)
        else:
            class TemplateParser(HTMLParser):
                def handle_starttag(self, tag, attrs):
                    attributes(attrs, tag, language)
                def handle_data(self, data):
                    for expression in re.findall(r'{{(.*?)}}|#\{(.*?)\}', data, re.S):
                        check(''.join(expression), 'text', language)
            parser = TemplateParser(convert_charrefs=True)
            parser.feed(text)
            parser.close()
    return findings
