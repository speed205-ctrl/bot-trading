"""Pytest configuration to ensure project root is on sys.path."""
import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
