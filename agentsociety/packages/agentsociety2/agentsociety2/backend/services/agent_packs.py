"""Discovery, validation, import, and export helpers for GOD AgentPacks."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import yaml

from agentsociety2.backend.services.map_packages import (
    agentsociety_root,
    generated_maps_root,
    is_within,
    maps_root,
    safe_resolve,
)


AGENT_PACK_MANIFESTS = ("agent_pack.yaml", "agent_pack.yml", "agent_pack.json")
DRAFT_AGENT_PACK_DIR = "_drafts"


@dataclass(frozen=True)
class AgentPackValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings)}


@dataclass(frozen=True)
class AgentPack:
    pack_id: str
    display_name: str
    package_path: Path
    manifest_path: Path
    manifest: dict[str, Any]
    agents: list[dict[str, Any]]
    validation: AgentPackValidation
    scope: str = "global"
    map_id: str | None = None


def agent_packs_root(root: Path | None = None) -> Path:
    return (root or agentsociety_root()) / "custom" / "agent_packs"


def draft_character_root(root: Path | None = None) -> Path:
    path = agent_packs_root(root) / DRAFT_AGENT_PACK_DIR / "characters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def map_agent_packs_roots(root: Path | None = None, map_id: str | None = None) -> tuple[tuple[Path, str], ...]:
    root = root or agentsociety_root()
    found: list[tuple[Path, str]] = []
    if map_id:
        for base in (maps_root(root), generated_maps_root(root)):
            found.append((base / map_id / "agent_packs", map_id))
        return tuple(found)

    for base in (maps_root(root), generated_maps_root(root)):
        if not base.exists():
            continue
        for package_dir in sorted(base.iterdir()):
            if package_dir.is_dir() and not package_dir.name.startswith(("_", ".")):
                found.append((package_dir / "agent_packs", package_dir.name))
    return tuple(found)


def validate_agent_pack_path(manifest_path: Path) -> AgentPackValidation:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = manifest_path.resolve()
    package_root = manifest_path.parent

    try:
        manifest = _load_structured(manifest_path)
    except Exception as exc:
        return AgentPackValidation(False, (f"manifest could not be read: {exc}",), ())

    for key in ("schema_version", "pack_id", "display_name", "agents"):
        if manifest.get(key) in (None, "", []):
            errors.append(f"missing required field: {key}")

    agents = manifest.get("agents")
    if not isinstance(agents, list) or not agents:
        errors.append("agents must be a non-empty list")
        agents = []

    seen_ids: set[str] = set()
    for index, item in enumerate(agents):
        if not isinstance(item, dict):
            errors.append(f"agent[{index}] must be an object")
            continue
        agent_id = str(item.get("id") or "").strip()
        if not agent_id:
            errors.append(f"agent[{index}] missing id")
        elif agent_id in seen_ids:
            errors.append(f"duplicate agent id: {agent_id}")
        seen_ids.add(agent_id)
        if not str(item.get("name") or "").strip():
            warnings.append(f"agent {agent_id or index} missing name")

        profile_path = str(item.get("profile_path") or "").strip()
        if not profile_path:
            errors.append(f"agent {agent_id or index} missing profile_path")
        else:
            profile = _safe_existing_file(
                package_root,
                profile_path,
                errors,
                label=f"agent {agent_id or index} profile_path",
            )
            if profile is not None:
                try:
                    profile_data = json.loads(profile.read_text(encoding="utf-8"))
                    if not isinstance(profile_data, dict):
                        errors.append(f"agent {agent_id or index} profile_path must contain a JSON object")
                except Exception as exc:
                    errors.append(f"agent {agent_id or index} profile_path could not be read: {exc}")

        runtime_path = str(item.get("runtime_path") or "").strip()
        if runtime_path:
            _safe_existing_file(
                package_root,
                runtime_path,
                errors,
                label=f"agent {agent_id or index} runtime_path",
            )

        sprite = item.get("sprite")
        if sprite is not None:
            if not isinstance(sprite, dict):
                errors.append(f"agent {agent_id or index} sprite must be an object")
            else:
                sprite_path = str(sprite.get("path") or "").strip()
                if sprite_path:
                    _safe_existing_file(
                        package_root,
                        sprite_path,
                        errors,
                        label=f"agent {agent_id or index} sprite path",
                    )
                for key in ("frame_width", "frame_height"):
                    raw = sprite.get(key)
                    if raw is None:
                        continue
                    try:
                        if int(raw) <= 0:
                            raise ValueError
                    except Exception:
                        errors.append(f"agent {agent_id or index} sprite {key} must be a positive integer")

    return AgentPackValidation(not errors, tuple(errors), tuple(warnings))


def load_agent_pack_by_manifest(
    manifest_path: Path,
    *,
    scope: str = "global",
    map_id: str | None = None,
) -> AgentPack:
    manifest_path = manifest_path.resolve()
    manifest = _load_structured(manifest_path)
    package_path = manifest_path.parent
    return AgentPack(
        pack_id=str(manifest.get("pack_id") or package_path.name),
        display_name=str(manifest.get("display_name") or manifest.get("pack_id") or package_path.name),
        package_path=package_path,
        manifest_path=manifest_path,
        manifest=manifest,
        agents=_load_agents(package_path, manifest),
        validation=validate_agent_pack_path(manifest_path),
        scope=scope,
        map_id=map_id,
    )


def list_agent_packs(root: Path | None = None, map_id: str | None = None) -> list[AgentPack]:
    root = root or agentsociety_root()
    found: list[AgentPack] = []
    seen: set[tuple[str, str | None, str]] = set()

    for manifest in _iter_pack_manifests(agent_packs_root(root)):
        pack = load_agent_pack_by_manifest(manifest, scope="global")
        key = (pack.scope, pack.map_id, pack.pack_id)
        if key not in seen:
            seen.add(key)
            found.append(pack)

    for packs_root, local_map_id in map_agent_packs_roots(root, map_id):
        for manifest in _iter_pack_manifests(packs_root):
            pack = load_agent_pack_by_manifest(manifest, scope="map", map_id=local_map_id)
            key = (pack.scope, pack.map_id, pack.pack_id)
            if key not in seen:
                seen.add(key)
                found.append(pack)
    return found


def find_agent_pack(pack_id: str, *, root: Path | None = None, map_id: str | None = None) -> AgentPack:
    packs = list_agent_packs(root=root, map_id=map_id)
    if map_id:
        for pack in packs:
            if pack.pack_id == pack_id and pack.scope == "map" and pack.map_id == map_id:
                return pack
    for pack in packs:
        if pack.pack_id == pack_id:
            return pack
    raise FileNotFoundError(f"AgentPack not found: {pack_id}")


def agent_pack_summary(pack: AgentPack) -> dict[str, Any]:
    return {
        "schema_version": int(pack.manifest.get("schema_version") or 1),
        "pack_id": pack.pack_id,
        "display_name": pack.display_name,
        "scope": pack.scope,
        "map_id": pack.map_id,
        "agent_count": len(pack.agents),
        "agents": pack.agents,
        "validation_status": pack.validation.as_dict(),
    }


def export_agent_pack(pack: AgentPack, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    _zip_directory(pack.package_path, zip_path)


def import_agent_pack_zip(
    zip_path: Path,
    *,
    root: Path | None = None,
    overwrite: bool = False,
) -> AgentPack:
    root = root or agentsociety_root()
    with tempfile.TemporaryDirectory(prefix="god-agent-pack-") as temp:
        temp_root = Path(temp)
        _safe_extract_zip(zip_path, temp_root)
        manifest_path = _find_manifest_in_extracted_root(temp_root)
        if manifest_path is None:
            raise ValueError("AgentPack archive must contain agent_pack.yaml")
        manifest = _load_structured(manifest_path)
        pack_id = _sanitize_pack_id(str(manifest.get("pack_id") or manifest_path.parent.name))
        target = agent_packs_root(root) / pack_id
        if target.exists():
            if not overwrite:
                raise FileExistsError(f"AgentPack already exists: {pack_id}")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(manifest_path.parent, target)
    pack = load_agent_pack_by_manifest(_manifest_path_for_dir(target) or target / "agent_pack.yaml")
    if not pack.validation.ok:
        shutil.rmtree(target, ignore_errors=True)
        raise ValueError(f"Imported AgentPack is invalid: {pack.validation.errors}")
    return pack


def save_agent_pack_from_agent(
    *,
    root: Path | None,
    pack_id: str,
    display_name: str,
    agent: dict[str, Any],
    initial_location: str | None = None,
) -> AgentPack:
    root = root or agentsociety_root()
    safe_pack_id = _sanitize_pack_id(pack_id or display_name or "agent-pack")
    package = agent_packs_root(root) / safe_pack_id
    if package.exists():
        shutil.rmtree(package)
    agents_dir = package / "agents"
    characters_dir = package / "characters"
    characters_dir.mkdir(parents=True)

    kwargs = agent.get("kwargs") if isinstance(agent.get("kwargs"), dict) else {}
    raw_profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
    profile = _strip_preview_data(raw_profile)
    agent_id = str(agent.get("agent_id") or kwargs.get("id") or "1")
    agent_name = str(kwargs.get("name") or profile.get("name") or f"Agent {agent_id}")
    if initial_location:
        routine = profile.get("routine") if isinstance(profile.get("routine"), dict) else {}
        routine = {**routine, "initial_location": initial_location}
        profile["routine"] = routine

    agent_dir = agents_dir / agent_id
    agent_dir.mkdir(parents=True)
    asset = _profile_character_asset(raw_profile)
    sprite_entry: dict[str, Any] | None = None
    if asset is not None:
        filename = Path(str(asset.get("filename") or f"{asset.get('sprite_name') or agent_id}.png")).name
        target = characters_dir / filename
        sprite_bytes = _sprite_bytes_from_asset(asset)
        if sprite_bytes:
            target.write_bytes(sprite_bytes)
        else:
            staged = _find_staged_character(filename, root=root)
            if staged is not None:
                shutil.copy2(staged, target)
        if target.exists():
            sprite_name = str(asset.get("sprite_name") or target.stem)
            appearance = profile.get("appearance") if isinstance(profile.get("appearance"), dict) else {}
            appearance = {**appearance}
            stored_asset = {
                key: value
                for key, value in _strip_preview_data(asset).items()
                if key not in {"preview_data_url"}
            }
            stored_asset["filename"] = filename
            stored_asset["sprite_name"] = sprite_name
            stored_asset["image_url"] = f"/api/v1/god/agent-packs/{safe_pack_id}/assets/characters/{filename}"
            appearance["character_asset"] = stored_asset
            appearance["character_sprite"] = sprite_name
            appearance["character_sprite_filename"] = filename
            profile["appearance"] = appearance
            sprite_entry = {
                "path": f"characters/{filename}",
                "frame_width": int(asset.get("frame_width") or 32),
                "frame_height": int(asset.get("frame_height") or 32),
            }

    (agent_dir / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    runtime = {
        "agent_type": str(agent.get("agent_type") or "JiuwenClawAgent"),
        "kwargs": {
            key: _strip_preview_data(value)
            for key, value in kwargs.items()
            if key not in {"profile", "id", "name"}
        },
    }
    (agent_dir / "runtime.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_agent: dict[str, Any] = {
        "id": agent_id,
        "name": agent_name,
        "profile_path": f"agents/{agent_id}/profile.json",
        "runtime_path": f"agents/{agent_id}/runtime.json",
    }
    if sprite_entry is not None:
        manifest_agent["sprite"] = sprite_entry
    manifest = {
        "schema_version": 1,
        "pack_id": safe_pack_id,
        "display_name": display_name or agent_name,
        "agents": [manifest_agent],
    }
    (package / "agent_pack.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return load_agent_pack_by_manifest(package / "agent_pack.yaml")


def _load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object in AgentPack manifest: {path}")
    return data


def _manifest_path_for_dir(path: Path) -> Path | None:
    for filename in AGENT_PACK_MANIFESTS:
        candidate = path / filename
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _iter_pack_manifests(root: Path) -> list[Path]:
    if not root.exists():
        return []
    manifests: list[Path] = []
    for package_dir in sorted(root.iterdir()):
        if not package_dir.is_dir() or package_dir.name.startswith(("_", ".")):
            continue
        manifest = _manifest_path_for_dir(package_dir)
        if manifest is not None:
            manifests.append(manifest)
    return manifests


def _safe_existing_file(
    package_root: Path,
    raw: str,
    errors: list[str],
    *,
    label: str,
) -> Path | None:
    try:
        path = safe_resolve(package_root, raw, package_root)
    except ValueError as exc:
        errors.append(f"{label} {exc}")
        return None
    if not path.exists() or not path.is_file():
        errors.append(f"{label} missing: {path}")
        return None
    return path


def _load_agents(package_path: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in manifest.get("agents", []) or []:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        profile_path = str(item.get("profile_path") or "").strip()
        if profile_path:
            try:
                profile_file = safe_resolve(package_path, profile_path, package_path)
                entry["profile"] = json.loads(profile_file.read_text(encoding="utf-8"))
            except Exception:
                entry["profile"] = {}
        runtime_path = str(item.get("runtime_path") or "").strip()
        if runtime_path:
            try:
                runtime_file = safe_resolve(package_path, runtime_path, package_path)
                entry["runtime"] = json.loads(runtime_file.read_text(encoding="utf-8"))
            except Exception:
                entry["runtime"] = {}
        sprite = entry.get("sprite")
        if isinstance(sprite, dict) and sprite.get("path"):
            entry["sprite"] = {
                **sprite,
                "image_url": str(sprite["path"]),
                "name": Path(str(sprite["path"])).stem,
            }
        loaded.append(entry)
    return loaded


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.name.startswith(".") or path.is_dir():
                continue
            archive.write(path, path.relative_to(source_dir))


def _safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            destination = (target_dir / member.filename).resolve()
            if not is_within(destination, target_dir):
                raise ValueError(f"Archive member escapes extract root: {member.filename}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)


def _find_manifest_in_extracted_root(root: Path) -> Path | None:
    direct = _manifest_path_for_dir(root)
    if direct is not None:
        return direct
    candidates = [
        manifest
        for child in root.iterdir()
        if child.is_dir()
        for manifest in [_manifest_path_for_dir(child)]
        if manifest is not None
    ]
    return candidates[0] if len(candidates) == 1 else None


def _sanitize_pack_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return safe or "agent-pack"


def _strip_preview_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_preview_data(child)
            for key, child in value.items()
            if key != "preview_data_url"
        }
    if isinstance(value, list):
        return [_strip_preview_data(item) for item in value]
    return value


def _profile_character_asset(profile: dict[str, Any]) -> dict[str, Any] | None:
    appearance = profile.get("appearance") if isinstance(profile.get("appearance"), dict) else {}
    asset = appearance.get("character_asset")
    if isinstance(asset, dict):
        return asset
    studio = profile.get("agent_studio") if isinstance(profile.get("agent_studio"), dict) else {}
    asset = studio.get("character_asset")
    return asset if isinstance(asset, dict) else None


def _sprite_bytes_from_asset(asset: dict[str, Any]) -> bytes | None:
    data_url = str(asset.get("preview_data_url") or "")
    prefix = "data:image/png;base64,"
    if data_url.startswith(prefix):
        return base64.b64decode(data_url[len(prefix) :])
    return None


def _find_staged_character(filename: str, *, root: Path) -> Path | None:
    candidate = draft_character_root(root) / Path(filename).name
    return candidate if candidate.exists() and candidate.is_file() else None
