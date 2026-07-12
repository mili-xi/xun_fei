"""
Shared import bootstrap for backend scripts.

The current backend modules are designed to be run directly from the
``后端`` directory. Importing this module makes that directory available on
``sys.path`` so sibling modules such as ``config`` resolve consistently.
"""
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 确保工作目录也在 path 中（便携版从其他目录启动时）
ROOT_DIR = BACKEND_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
