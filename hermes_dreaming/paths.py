from pathlib import Path

# Hermes built-in memory files
HERMES_MEMORIES_DIR = Path.home() / ".hermes" / "memories"
MEMORY_MD = HERMES_MEMORIES_DIR / "MEMORY.md"
USER_MD = HERMES_MEMORIES_DIR / "USER.md"

MEMORY_MD_LIMIT = 2200  # characters
USER_MD_LIMIT = 1375    # characters

# Dreaming state directory
DREAMING_DIR = Path.home() / ".hermes" / "dreaming"

DREAMS_MD = DREAMING_DIR / "DREAMS.md"
STATE_JSON = DREAMING_DIR / "state.json"
CANDIDATES_JSONL = DREAMING_DIR / "candidates.jsonl"
DECISIONS_JSONL = DREAMING_DIR / "decisions.jsonl"
PROMOTIONS_JSONL = DREAMING_DIR / "promotions.jsonl"
MEMORY_HINTS_JSONL = DREAMING_DIR / "memory_hints.jsonl"
RUNS_DIR = DREAMING_DIR / "runs"
BACKUPS_DIR = DREAMING_DIR / "backups"
CONFIG_FILE = DREAMING_DIR / "config.yaml"


def ensure_dirs() -> None:
    for d in (DREAMING_DIR, RUNS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)
