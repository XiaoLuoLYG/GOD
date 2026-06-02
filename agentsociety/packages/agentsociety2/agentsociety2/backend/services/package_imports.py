"""Unified import-preview coordinator for GOD package archives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any
import uuid

from agentsociety2.backend.services import agent_packs, experiment_packs, map_packages, package_archives


@dataclass
class PackagePreview:
    token: str
    package_type: str
    resource_id: str
    display_name: str
    staging_root: Path
    package_path: Path
    validation: dict[str, Any]
    dependencies: list[dict[str, str]]
    conflict: bool
    install_path: str
    created_at: float


_PREVIEWS: dict[str, PackagePreview] = {}


def create_preview(
    zip_path: Path,
    *,
    agentsociety_root: Path,
    workspace_root: Path,
    original_filename: str | None = None,
) -> PackagePreview:
    staging = package_archives.temp_staging_dir("god-import-preview-")
    try:
        package_archives.safe_extract_zip(zip_path, staging)
        if _looks_like_replay_archive(staging):
            raise ValueError(
                "Replay archives are viewable replay data, not installable packages. "
                "Import an ExperimentPack zip to play a setup."
            )
        package_path = _find_package_path(staging)
        if package_path is None:
            raise ValueError("Could not identify package type from archive contents")
        package_type, resource_id, display_name, validation, dependencies, install_path = _describe_package(
            package_path,
            agentsociety_root=agentsociety_root,
            workspace_root=workspace_root,
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if package_type == "experiment" and resource_id.startswith("god-import-preview-"):
        resource_id = _resource_id_from_zip_name(Path(original_filename or zip_path.name))
        display_name = display_name if display_name != "experiment" else resource_id
        install_path = str(workspace_root / f"hypothesis_{resource_id}" / "experiment_1")
    token = uuid.uuid4().hex
    preview = PackagePreview(
        token=token,
        package_type=package_type,
        resource_id=resource_id,
        display_name=display_name,
        staging_root=staging,
        package_path=package_path,
        validation=validation,
        dependencies=dependencies,
        conflict=Path(install_path).exists(),
        install_path=install_path,
        created_at=time.time(),
    )
    _PREVIEWS[token] = preview
    return preview


def install_preview(
    *,
    preview_token: str,
    conflict_strategy: str,
    agentsociety_root: Path,
    workspace_root: Path,
    requested_id: str | None = None,
) -> dict[str, Any]:
    preview = _PREVIEWS.pop(preview_token, None)
    if preview is None:
        raise ValueError("Import preview token is invalid or expired")
    overwrite = conflict_strategy == "overwrite"
    staged_zip: Path | None = None
    try:
        staged_zip = _zip_staged_package(preview.package_path)
        if preview.package_type == "map":
            registry = map_packages.maps_root(agentsociety_root)
            map_id = requested_id or (
                package_archives.next_available_id(registry, preview.resource_id)
                if preview.conflict and not overwrite
                else preview.resource_id
            )
            package = map_packages.import_map_pack_zip(
                staged_zip,
                root=agentsociety_root,
                requested_map_id=map_id,
                overwrite=overwrite,
            )
            return {"package_type": "map", "resource_id": package.map_id, "install_path": str(package.package_path)}
        if preview.package_type == "agent":
            registry = agent_packs.agent_packs_root(agentsociety_root)
            pack_id = requested_id or (
                package_archives.next_available_id(registry, preview.resource_id)
                if preview.conflict and not overwrite
                else preview.resource_id
            )
            package = agent_packs.import_agent_pack_zip(
                staged_zip,
                root=agentsociety_root,
                requested_pack_id=pack_id,
                overwrite=overwrite,
            )
            return {"package_type": "agent", "resource_id": package.pack_id, "install_path": str(package.package_path)}
        if preview.package_type == "experiment":
            target_id = requested_id or preview.resource_id
            package = experiment_packs.import_experiment_pack_zip(
                staged_zip,
                workspace_root=workspace_root,
                agentsociety_root=agentsociety_root,
                requested_hypothesis_id=target_id,
                overwrite=overwrite,
            )
            return {
                "package_type": "experiment",
                "resource_id": package.hypothesis_id,
                "hypothesis_id": package.hypothesis_id,
                "experiment_id": package.experiment_id,
                "map_id": package.map_id,
                "display_name": package.display_name,
                "install_path": str(package.package_path),
            }
        raise ValueError(f"Unsupported package type: {preview.package_type}")
    finally:
        if staged_zip is not None:
            staged_zip.unlink(missing_ok=True)
        shutil.rmtree(preview.staging_root, ignore_errors=True)


def cancel_preview(preview_token: str) -> None:
    preview = _PREVIEWS.pop(preview_token, None)
    if preview is not None:
        shutil.rmtree(preview.staging_root, ignore_errors=True)


def preview_to_dict(preview: PackagePreview) -> dict[str, Any]:
    return {
        "preview_token": preview.token,
        "package_type": preview.package_type,
        "resource_id": preview.resource_id,
        "display_name": preview.display_name,
        "validation": preview.validation,
        "dependencies": preview.dependencies,
        "conflict": preview.conflict,
        "install_path": preview.install_path,
    }


def _find_package_path(staging: Path) -> Path | None:
    candidates = [staging] + [child for child in staging.iterdir() if child.is_dir()]
    for candidate in candidates:
        if map_packages._manifest_path_for_dir(candidate):
            return candidate
        if agent_packs._manifest_path_for_dir(candidate):
            return candidate
        if (candidate / "init" / "init_config.json").exists() and (candidate / "init" / "steps.yaml").exists():
            return candidate
    return None


def _looks_like_replay_archive(staging: Path) -> bool:
    candidates = [staging] + [child for child in staging.iterdir() if child.is_dir()]
    return any(
        (candidate / "timeline.json").exists()
        and (candidate / "steps").is_dir()
        and (candidate / "agents" / "profiles.json").exists()
        for candidate in candidates
    )


def _describe_package(
    package_path: Path,
    *,
    agentsociety_root: Path,
    workspace_root: Path,
) -> tuple[str, str, str, dict[str, Any], list[dict[str, str]], str]:
    map_manifest = map_packages._manifest_path_for_dir(package_path)
    if map_manifest is not None:
        package = map_packages.load_map_package_by_manifest(map_manifest)
        return (
            "map",
            package.map_id,
            package.display_name,
            package.validation.as_dict(),
            [],
            str(map_packages.maps_root(agentsociety_root) / package.map_id),
        )
    agent_manifest = agent_packs._manifest_path_for_dir(package_path)
    if agent_manifest is not None:
        package = agent_packs.load_agent_pack_by_manifest(agent_manifest)
        return (
            "agent",
            package.pack_id,
            package.display_name,
            package.validation.as_dict(),
            [],
            str(agent_packs.agent_packs_root(agentsociety_root) / package.pack_id),
        )
    preview = experiment_packs.preview_experiment_pack(package_path)
    dependencies = [{"type": "map", "id": preview.map_id}] if preview.map_id else []
    install_path = workspace_root / f"hypothesis_{preview.hypothesis_id}" / f"experiment_{preview.experiment_id}"
    return (
        "experiment",
        preview.hypothesis_id,
        preview.display_name,
        preview.validation.as_dict(),
        dependencies,
        str(install_path),
    )


def _zip_staged_package(package_path: Path) -> Path:
    target = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.zip"
    return package_archives.zip_directory(package_path, target)


def _resource_id_from_zip_name(zip_path: Path) -> str:
    name = zip_path.stem
    for suffix in ("-experiment-pack", "_experiment_pack", "-pack"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return package_archives.sanitize_id(name.lower(), "experiment")
