from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .schema import BACKUP_DIR_NAME


def rotate_existing_artifact(output_path: Path) -> None:
    """Move a pre-existing artifact into the timestamped backup folder."""
    if not output_path.exists():
        return
    backup_dir = output_path.parent / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{output_path.stem}_{stamp}{output_path.suffix}"
    output_path.rename(backup_dir / backup_name)


def prepare_output_path(base_dir: Path, filename: str) -> Path:
    """Rotate any existing artifact before returning the active output path."""
    output_path = base_dir / filename
    rotate_existing_artifact(output_path)
    return output_path
