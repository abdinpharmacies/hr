import sys
import os

# Add external_libs to path - Prepend to ensure priority
libs_path = os.path.join(os.path.dirname(__file__), 'external_libs')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

from . import models
from . import wizard
