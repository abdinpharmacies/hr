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

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.model = ''
            self.class_name = ''
            self.aliases = {}
            self.functions = {}

        def resolve(self, node):
            if isinstance(node, ast.Name):
                return self.aliases.get(node.id, ('', False))
            if isinstance(node, ast.Subscript) and (
                isinstance(node.value, ast.Attribute) and node.value.attr == 'env'
                or isinstance(node.value, ast.Name) and node.value.id == 'env'
            ):
                value = literal(node.slice)
                return (value if isinstance(value, str) else ''), False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                model, delayed = self.resolve(node.func.value)
                if node.func.attr in {'with_delay', 'delayable'}:
                    return model, True
                if node.func.attr in RECORD_WRAPPERS or delayed:
                    return model, delayed
            return '', False

        def add(self, model, method, pattern, node, backend='queue'):
            if not isinstance(method, str) or not method:
                return
            function = self.functions.get(method) if model == self.model else None
            found[(model, method, backend)] = {
                'module': module, 'model_name': model, 'method_name': method,
                'backend': backend, 'source_file': filename, 'source_class': self.class_name,
                'source_line': (function or node).lineno, 'signature': pattern,
                'documentation': (ast.get_docstring(function) or '')[:1000] if function else '',
                'static_found': True,
            }

        def visit_ClassDef(self, node):
            previous = self.model, self.class_name, self.aliases, self.functions
            metadata = {target.id: literal(statement.value) for statement in node.body
                        if isinstance(statement, ast.Assign) for target in statement.targets
                        if isinstance(target, ast.Name)}
            model = metadata.get('_name') or metadata.get('_inherit') or ''
            if isinstance(model, list):
                model = model[0] if len(model) == 1 else ''
            self.model = model if isinstance(model, str) else ''
            self.class_name = node.name
            self.aliases = {'self': (self.model, False)}
            self.functions = {child.name: child for child in node.body
                              if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for child in node.body:
                self.visit(child)
            self.model, self.class_name, self.aliases, self.functions = previous

        def visit_FunctionDef(self, node):
            for decorator in node.decorator_list:
                name = decorator.func if isinstance(decorator, ast.Call) else decorator
                if (isinstance(name, ast.Name) and name.id == 'job') or (
                        isinstance(name, ast.Attribute) and name.attr == 'job'):
                    self.add(self.model, node.name, '@job', node)
            previous = self.aliases, self.functions
            self.aliases = dict(self.aliases)
            arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
            for argument in arguments:
                self.aliases[argument.arg] = (self.model, False) if argument.arg == 'self' else ('', False)
            self.functions = dict(self.functions)
            self.functions.update({child.name: child for child in node.body
                                   if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))})
            for child in node.body:
                self.visit(child)
            self.aliases, self.functions = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def assign(self, target, value):
            if isinstance(target, ast.Name):
                self.aliases[target.id] = value
            elif isinstance(target, (ast.Tuple, ast.List)):
                for child in target.elts:
                    self.assign(child, ('', False))

        def visit_Assign(self, node):
            self.visit(node.value)
            value = self.resolve(node.value)
            for target in node.targets:
                self.assign(target, value)

        def visit_AnnAssign(self, node):
            if node.value:
                self.visit(node.value)
            self.assign(node.target, self.resolve(node.value))

        def visit_For(self, node):
            self.visit(node.iter)
            previous = dict(self.aliases)
            self.assign(node.target, self.resolve(node.iter))
            for child in node.body:
                self.visit(child)
            self.aliases = {key: value for key, value in previous.items() if self.aliases.get(key) == value}
            for child in node.orelse:
                self.visit(child)

        visit_AsyncFor = visit_For

        def visit_If(self, node):
            self.visit(node.test)
            previous = dict(self.aliases)
            for child in node.body:
                self.visit(child)
            positive = self.aliases
            self.aliases = previous
            for child in node.orelse:
                self.visit(child)
            self.aliases = {key: value for key, value in positive.items() if self.aliases.get(key) == value}

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                model, delayed = self.resolve(node.func.value)
                if delayed and node.func.attr not in {'with_delay', 'delayable', 'set', 'delay', 'on_done', 'split', 'group', 'chain'}:
                    self.add(model, node.func.attr, 'delayable call', node)
                if node.func.attr == '_patch_job_auto_delay' and node.args:
                    self.add(self.model, literal(node.args[0]), 'automatic delay patch', node)
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name == 'Thread':
                for keyword in node.keywords:
                    if keyword.arg == 'target':
                        method = getattr(keyword.value, 'attr', None) or getattr(keyword.value, 'id', None)
                        model = self.resolve(keyword.value.value)[0] if isinstance(keyword.value, ast.Attribute) else self.model
                        self.add(model, method, 'thread target', node, 'thread')
            self.generic_visit(node)

    Visitor().visit(tree)
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
