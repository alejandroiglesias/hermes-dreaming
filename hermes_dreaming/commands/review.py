from __future__ import annotations

"""
/dreaming review — dry-run mode.

Identical to /dreaming run but dry_run=True, which:
  - disables dreaming_apply_memory_op mutations
  - flags the DREAMS.md entry as dry-run
"""

from ..orchestration import build


def handle(args: str = "") -> str:
    return build(dry_run=True)
