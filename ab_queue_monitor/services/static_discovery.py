"""Bounded AST discovery. No addon imports, eval, or source execution."""
import ast
import os
import tokenize
from pathlib import Path

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 20000
EXCLUDED = {'tests', 'demo', 'migrations', '__pycache__', '.git', 'node_modules', 'static', 'i18n'}
RECORD_WRAPPERS = {'sudo', 'with_user', 'with_context', 'with_company', 'browse', 'search', 'search_fetch', 'filtered', 'ensure_one'}


def inventory(root):
    root = Path(root).resolve()
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('.') and not Path(directory, d).is_symlink())
        for filename in sorted(files):
            path = Path(directory, filename)
            if filename.endswith('.py') and not path.is_symlink():
                result.append(str(path.relative_to(root)))
                if len(result) > MAX_FILES:
                    raise ValueError('file_limit')
    return result


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None


def scan_text(source, module, filename):
    tree = ast.parse(source, filename=filename)
    found = {}
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    scopes = classes + [tree]
    for scope in scopes:
        model = ''
        if isinstance(scope, ast.ClassDef):
            metadata = {t.id: literal(n.value) for n in scope.body if isinstance(n, ast.Assign)
                        for t in n.targets if isinstance(t, ast.Name)}
            model = metadata.get('_name') or metadata.get('_inherit') or ''
            if isinstance(model, list):
                model = model[0] if len(model) == 1 else ''
        nodes = list(ast.walk(scope)) if isinstance(scope, ast.ClassDef) else [node for top in tree.body if not isinstance(top, ast.ClassDef) for node in ast.walk(top)]
        functions = {n.name: n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        aliases = {'self': (model, False)}

        def resolve(node):
            if isinstance(node, ast.Name):
                return aliases.get(node.id, ('', False))
            if isinstance(node, ast.Subscript) and ((isinstance(node.value, ast.Attribute) and node.value.attr == 'env') or (isinstance(node.value, ast.Name) and node.value.id == 'env')):
                return literal(node.slice) or '', False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                base, delayed = resolve(node.func.value)
                if node.func.attr in {'with_delay', 'delayable'}:
                    return base, True
                if node.func.attr in RECORD_WRAPPERS or delayed:
                    return base, delayed
            return '', False

        def add(target_model, method, pattern, node=None, backend='queue'):
            if not method or not isinstance(method, str):
                return
            fn = functions.get(method)
            key = (target_model, method, backend)
            found[key] = {
                'module': module, 'model_name': target_model or '', 'method_name': method,
                'backend': backend, 'source_file': filename,
                'source_class': scope.name if isinstance(scope, ast.ClassDef) else '',
                'source_line': (fn or node).lineno if (fn or node) is not None else 0,
                'signature': pattern, 'documentation': (ast.get_docstring(fn) or '')[:1000] if fn else '',
                'static_found': True,
            }

        # Fixed passes resolve local aliases without executing their expressions.
        for _ in range(3):
            for node in nodes:
                if isinstance(node, ast.Assign):
                    value = resolve(node.value)
                    for target in node.targets:
                        if isinstance(target, ast.Name) and value[0]:
                            aliases[target.id] = value
                if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
                    value = resolve(node.iter)
                    if value[0]:
                        aliases[node.target.id] = value
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    dec = decorator.func if isinstance(decorator, ast.Call) else decorator
                    if (isinstance(dec, ast.Name) and dec.id == 'job') or (isinstance(dec, ast.Attribute) and dec.attr == 'job'):
                        add(model, node.name, '@job', node)
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                target_model, delayed = resolve(node.func.value)
                if delayed and node.func.attr not in {'with_delay', 'delayable', 'set', 'delay', 'on_done', 'split', 'group', 'chain'}:
                    add(target_model, node.func.attr, 'delayable call', node)
                if node.func.attr == '_patch_job_auto_delay' and node.args:
                    add(model, literal(node.args[0]), 'automatic delay patch', node)
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name == 'Thread':
                for kw in node.keywords:
                    if kw.arg == 'target':
                        method = getattr(kw.value, 'attr', None) or getattr(kw.value, 'id', None)
                        add(model, method, 'thread target', node, 'thread')
    return list(found.values())


def scan_file(root, filename, module):
    root = Path(root).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('file_limit')
    with tokenize.open(path) as stream:
        return scan_text(stream.read(), module, filename)


def difference(previous, current):
    previous, current = set(previous), set(current)
    return sorted(current - previous), sorted(previous - current), sorted(previous & current)
