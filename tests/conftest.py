"""Lets the pure-logic tests run on machines without PyObjC (e.g. Linux CI)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

for name in ("AppKit", "Quartz"):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = MagicMock()
