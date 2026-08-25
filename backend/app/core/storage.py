from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from .config import (
    get_data_dir,
    get_kvitteringer_data_dir,
    get_storebox_source_dir,
)


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def ensure_runtime_dirs() -> None:
    for path in [
        get_data_dir() / "backups",
        get_data_dir() / "transactions",
        get_kvitteringer_data_dir(),
        get_storebox_source_dir(),
    ]:
        path.mkdir(parents=True, exist_ok=True)


def prune_backups(prefix: str, max_keep: int = 5) -> list[Path]:
    """Keep only the latest `max_keep` backup snapshots matching `prefix`."""
    backup_dir = get_data_dir() / "backups"
    if not backup_dir.exists():
        return []

    pattern = f"{prefix}*.bak" if not prefix.endswith(".bak") else prefix
    matching = sorted(
        backup_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    pruned: list[Path] = []
    if len(matching) > max_keep:
        for f in matching[max_keep:]:
            try:
                f.unlink(missing_ok=True)
                pruned.append(f)
            except OSError:
                pass
    return pruned


def create_backup(path: Path, max_keep: int = 5) -> Path | None:
    if not path.exists() or not path.is_file():
        return None
    backup_dir = get_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.{_timestamp()}.bak"
    shutil.copy2(path, backup_path)
    prune_backups(path.name, max_keep=max_keep)
    return backup_path
