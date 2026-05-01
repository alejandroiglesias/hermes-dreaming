from __future__ import annotations

"""
/dreaming run — full Dreaming cycle (live mode).

Returns the orchestration prompt that drives the agent through
Light → REM → Deep using the dreaming_* tools.
"""

from ..orchestration import build


def handle(args: str = "") -> str:
    return build(dry_run=False)
