import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hermes_dreaming import register  # noqa: E402

__all__ = ["register"]
