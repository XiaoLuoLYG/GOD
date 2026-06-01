from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from agentsociety2.backend.services import package_archives


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "nope")

    with pytest.raises(ValueError, match="escapes extract root"):
        package_archives.safe_extract_zip(archive_path, tmp_path / "out")


def test_safe_extract_ignores_platform_metadata(tmp_path: Path) -> None:
    archive_path = tmp_path / "meta.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("__MACOSX/._map.yaml", "metadata")
        archive.writestr("map.yaml", "map_id: demo\n")

    extracted = package_archives.safe_extract_zip(archive_path, tmp_path / "out")

    assert (extracted / "map.yaml").exists()
    assert not (extracted / "__MACOSX").exists()


def test_next_available_id_uses_numeric_suffix(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    (root / "town").mkdir(parents=True)
    (root / "town_2").mkdir()

    assert package_archives.next_available_id(root, "town") == "town_3"


def test_archive_copy_path_creates_scoped_export_dir(tmp_path: Path) -> None:
    target = package_archives.archive_copy_path(
        god_root=tmp_path,
        category="maps",
        resource_id="town",
        suffix="map-pack",
    )

    assert target.parent == tmp_path / ".god" / "exports" / "maps"
    assert target.name.endswith("-map-pack.zip")
    assert "town" in target.name
