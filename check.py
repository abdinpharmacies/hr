import os
import re
import ast
import sys
from pathlib import Path

SQL_PATTERNS = {
    "INSERT INTO": re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    "DELETE": re.compile(r"\bDELETE\b", re.IGNORECASE),
    "UPDATE": re.compile(r"\bUPDATE\b", re.IGNORECASE),
}


def read_file(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def print_issue(title, path, line_no, line):
    print(f"\n[{title}]")
    print(f"File: {path}")
    print(f"Line: {line_no}")
    print(f"Code: {line.strip()}")


def check_sql_keywords(path, line_no, line):
    for keyword, pattern in SQL_PATTERNS.items():
        if pattern.search(line):
            print_issue(f"CHECK SQL keyword: {keyword}", path, line_no, line)


def scan_python_file(path):
    content = read_file(path)
    lines = content.splitlines()

    for i, line in enumerate(lines, start=1):

        # _name must have at least one space before it
        # model name must contain dot
        if "_name" in line:
            name_match = re.search(r"\s+_name\s*=\s*['\"]([^'\"]+)['\"]", line)

            if not name_match:
                pass
                # print_issue(
                #     "CHECK _name pattern: must have space before _name",
                #     path,
                #     i,
                #     line,
                # )
            else:
                model_name = name_match.group(1)

                if "." in model_name:
                    print_issue(
                        "CHECK _name model name must not contain dot",
                        path,
                        i,
                        line,
                    )

        # _inherit review
        if re.search(r"\s+_inherit\s*=", line):
            print_issue("CHECK _inherit review old model changes", path, i, line)

        # _table review
        if re.search(r"\s+_table\s*=", line):
            print_issue("CHECK _table exists", path, i, line)

        # def init review
        if re.search(r"def\s+init\s*\(", line):
            print_issue("CHECK def init exists", path, i, line)

        # SQL operations
        check_sql_keywords(path, i, line)


def scan_manifest(path):
    content = read_file(path)

    try:
        manifest = ast.literal_eval(content)

        for key in ["pre_init_hook", "post_init_hook", "uninstall_hook", "post_load"]:
            if key in manifest:
                print(f"\n[CHECK Manifest Hook]")
                print(f"File: {path}")
                print(f"Hook: {key} = {manifest.get(key)}")

    except Exception:
        for i, line in enumerate(content.splitlines(), start=1):
            if "hook" in line.lower():
                print_issue("CHECK possible hook in manifest", path, i, line)


def scan_text_file_for_sql(path):
    content = read_file(path)

    for i, line in enumerate(content.splitlines(), start=1):
        check_sql_keywords(path, i, line)


def scan_module(module_path):
    module_path = Path(module_path)

    if not module_path.exists():
        print(f"Module not found: {module_path}")
        return

    print(f"Scanning module: {module_path.resolve()}")

    for root, dirs, files in os.walk(module_path):
        ignored_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "node_modules",
        }

        dirs[:] = [d for d in dirs if d not in ignored_dirs]

        for file in files:
            path = Path(root) / file

            if file.endswith(".py"):
                scan_python_file(path)

            if file in ["__manifest__.py", "__openerp__.py"]:
                scan_manifest(path)

            if file.endswith((".xml", ".csv", ".sql")):
                scan_text_file_for_sql(path)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("python check.py module_name")
        sys.exit(1)

    scan_module(sys.argv[1])
