"""Model-aware inspection and bounded literal action-default relocation."""
import ast
from seed_metadata import inspect_metadata


def action_references(value, column, model, schema, moves, before='old_id', after='temp_id'):
    """Return (replacement, blockers). Parse expressions without executing them."""
    mapping = {(m['model'], m[before]): m[after] for m in moves}
    all_ids = {old for related, old in mapping}
    markers = set(schema) | {name for meta in schema.values() for name in meta['fields']}
    findings = []

    def fail(expression, related=None):
        findings.append(dict(location=column, expression=expression, related_model=related,
                             reason='Unsupported or affected action reference; needs reviewed adapter'))

    def relation(path):
        current = model
        for part in path.split('.'):
            if current not in schema:
                return '?'  # unknown metadata must not silently clear a blocker
            if part == 'id':
                return current
            field = schema[current]['fields'].get(part)
            if field is None:
                return '?'
            current = field.get('relation')
            if not current:
                return None  # known non-relational value
        return current

    def numbers(node):
        return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
                and type(n.value) is int}

    def fallback(expression):
        findings.extend(inspect_metadata(expression, 'ir_act_window', column, markers, all_ids))

    try:
        tree = ast.parse((value or '').strip(), mode='eval')
    except (SyntaxError, ValueError):
        fallback(value or '')
        return value, findings

    if column == 'context' and isinstance(tree.body, ast.Dict):
        changed = False
        residual_keys, residual_values = [], []
        keys = [k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else None for k in tree.body.keys]
        for key, node, name in zip(tree.body.keys, tree.body.values, keys):
            if name and name.startswith('default_'):
                related = relation(name[len('default_'):])
                candidate_ids = numbers(node)
                if related == '?':
                    if candidate_ids & all_ids:
                        fail(ast.unparse(node), related)
                elif related:
                    affected = {i for i in candidate_ids if (related, i) in mapping}
                    if affected:
                        field = schema.get(model, {}).get('fields', {}).get(name[len('default_'):], {})
                        if (field.get('type') == 'many2one' and isinstance(node, ast.Constant)
                                and type(node.value) is int and keys.count(name) == 1):
                            node.value = mapping[related, node.value]
                            changed = True
                        else:
                            fail(ast.unparse(node), related)
                # Dynamic expressions can explicitly browse other models.
                if not isinstance(node, ast.Constant):
                    fallback(ast.unparse(node))
            else:
                residual_keys.append(key)
                residual_values.append(node)
        fallback(ast.unparse(ast.Dict(keys=residual_keys, values=residual_values)))
        return (ast.unparse(tree) if changed and not findings else value), findings

    if column == 'domain':
        # Only literal domain structure is classified. Dynamic expressions retain
        # conservative inspection instead of being evaluated or guessed.
        try:
            domain = ast.literal_eval(tree)
        except (ValueError, TypeError, SyntaxError):
            fallback(value)
            return value, findings
        if isinstance(domain, (list, tuple)):
            for leaf in domain:
                if isinstance(leaf, str) and leaf in ('&', '|', '!'):
                    continue
                if not (isinstance(leaf, (list, tuple)) and len(leaf) == 3 and isinstance(leaf[0], str)):
                    fallback(value)
                    break
                related = relation(leaf[0])
                ids = numbers(ast.parse(repr(leaf[2]), mode='eval'))
                if related == '?' and ids & all_ids:
                    fail(repr(leaf), related)
                elif related and any((related, i) in mapping for i in ids):
                    fail(repr(leaf), related)
            return value, findings
    fallback(value)
    return value, findings
