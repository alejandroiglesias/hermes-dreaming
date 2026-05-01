from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path

from .paths import CONFIG_FILE


@dataclass
class DreamingConfig:
    enabled: bool = True
    schedule: str = "0 3 * * *"
    max_changes_per_run: int = 3
    max_adds_per_run: int = 1
    max_new_chars_per_run: int = 250
    recent_sessions_limit: int = 14


_config: DreamingConfig | None = None


def load() -> DreamingConfig:
    global _config
    if _config is not None:
        return _config

    if CONFIG_FILE.exists():
        try:
            raw = yaml.safe_load(CONFIG_FILE.read_text()) or {}
            dreaming_section = raw.get("dreaming", raw)
            _config = DreamingConfig(**{
                k: v for k, v in dreaming_section.items()
                if k in DreamingConfig.__dataclass_fields__
            })
        except Exception:
            _config = DreamingConfig()
    else:
        _config = DreamingConfig()

    return _config


def reload() -> DreamingConfig:
    global _config
    _config = None
    return load()
