"""Shared helpers for GOD package zip import/export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


IGNORED_ARCHIVE_PREFIXES = ("__MACOSX/",)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_extract_zip(zip_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            name = member.filename
            if member.is_dir() or any(name.startswith(prefix) for prefix in IGNORED_ARCHIVE_PREFIXES):
                continue
            if Path(name).is_absolute():
                raise ValueError(f"Archive member is absolute: {name}")
            destination = (target_dir / name).resolve()
            if not is_within(destination, target_dir):
                raise ValueError(f"Archive member escapes extract root: {name}")
            if destination.name.startswith("."):
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
    return target_dir


def zip_directory(source_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            archive.write(path, path.relative_to(source_dir))
    return zip_path


def temp_staging_dir(prefix: str = "god-package-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def sanitize_id(value: str, fallback: str = "package") -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return safe or fallback


def next_available_id(registry_root: Path, resource_id: str) -> str:
    safe = sanitize_id(resource_id)
    if not (registry_root / safe).exists():
        return safe
    index = 2
    while (registry_root / f"{safe}_{index}").exists():
        index += 1
    return f"{safe}_{index}"


def archive_copy_path(
    *,
    god_root: Path,
    category: str,
    resource_id: str,
    suffix: str,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_id = sanitize_id(resource_id)
    filename = f"{safe_id}-{stamp}-{suffix}.zip"
    target = god_root / ".god" / "exports" / category / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
