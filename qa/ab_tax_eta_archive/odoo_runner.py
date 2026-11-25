"""Run Odoo with the existing dependencies when its Windows venv launcher is stale.

Usage: python odoo_runner.py <odoo-source> <normal odoo-bin arguments...>
This helper does not modify the source installation or its virtual environment.
"""
import os
import runpy
import site
import sys
from pathlib import Path

source = Path(sys.argv.pop(1)).resolve()
packages = source / '.venv/Lib/site-packages'
site.addsitedir(str(packages))
sys.path.insert(0, str(packages))
sys.path.insert(0, str(source))
handle = os.add_dll_directory(str(packages / 'pywin32_system32')) if os.name == 'nt' else None
sys.argv[0] = str(source / 'odoo-bin')
runpy.run_path(sys.argv[0], run_name='__main__')
