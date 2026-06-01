"""Validation, import, and export helpers for GOD ExperimentPacks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

import yaml

from agentsociety2.backend.services import agent_packs, map_packages, package_archives
from agentsociety2.society.models import InitConfig, StepsConfig

_PRIVATE_INIT_CONFIG_KEYS = {"session_id", "trusted_dirs"}


@dataclass(frozen=True)
class ExperimentPackValidation:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings)}


@dataclass(frozen=True)
class ExperimentPackPreview:
    hypothesis_id: str
    experiment_id: str
    package_path: Path
    validation: ExperimentPackValidation
    map_id: str | None = None
    display_name: str = ""

    @property
    def ok(self) -> bool:
        return self.validation.ok


def preview_experiment_pack(package_path: Path) -> ExperimentPackPreview:
    package_path = package_path.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    init_path = package_path / "init" / "init_config.json"
    steps_path = package_path / "init" / "steps.yaml"
    init_config: dict[str, Any] = {}
    if not init_path.exists():
        errors.append(f"missing init_config.json: {init_path}")
    else:
        try:
            init_config = json.loads(init_path.read_text(encoding="utf-8"))
            InitConfig.model_validate(init_config)
        except Exception as exc:
            errors.append(f"invalid init_config.json: {exc}")
    if not steps_path.exists():
        errors.append(f"missing steps.yaml: {steps_path}")
    else:
        try:
            StepsConfig.model_validate(yaml.safe_load(steps_path.read_text(encoding="utf-8")) or {})
        except Exception as exc:
            errors.append(f"invalid steps.yaml: {exc}")
    if _has_runtime_state(package_path):
        warnings.append("ignored run content during ExperimentPack import")
    context = _load_context(package_path)
    map_id = _map_id_from_init_or_context(init_config, context)
    hypothesis_id = _infer_hypothesis_id(package_path)
    experiment_id = package_path.name.removeprefix("experiment_") if package_path.name.startswith("experiment_") else "1"
    display_name = str(context.get("title") or hypothesis_id)
    return ExperimentPackPreview(
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        package_path=package_path,
        validation=ExperimentPackValidation(not errors, tuple(errors), tuple(warnings)),
        map_id=map_id,
        display_name=display_name,
    )


def export_experiment_pack(
    experiment_path: Path,
    zip_path: Path,
    *,
    include_legacy_run_artifacts: bool = False,
    agentsociety_root: Path | None = None,
) -> Path:
    with tempfile.TemporaryDirectory(prefix="god-experiment-pack-") as temp:
        staging = Path(temp) / experiment_path.name
        ignore = None if include_legacy_run_artifacts else _experiment_pack_ignore()
        shutil.copytree(experiment_path, staging, ignore=ignore)
        if not include_legacy_run_artifacts:
            _remove_runtime_state(staging)
        if agentsociety_root is not None:
            _stage_dependencies(staging, agentsociety_root=agentsociety_root)
        _sanitize_experiment_pack_files(staging)
        return package_archives.zip_directory(staging, zip_path)


def import_experiment_pack_zip(
    zip_path: Path,
    *,
    workspace_root: Path,
    agentsociety_root: Path | None = None,
    requested_hypothesis_id: str | None = None,
    requested_experiment_id: str | None = None,
    overwrite: bool = False,
) -> ExperimentPackPreview:
    with tempfile.TemporaryDirectory(prefix="god-experiment-import-") as temp:
        extracted = package_archives.safe_extract_zip(zip_path, Path(temp))
        package_path = _find_experiment_root(extracted)
        if package_path is None:
            raise ValueError("ExperimentPack archive must contain init/init_config.json and init/steps.yaml")
        preview = preview_experiment_pack(package_path)
        if not preview.ok:
            raise ValueError(f"Imported ExperimentPack is invalid: {preview.validation.errors}")
        hypothesis_id = package_archives.sanitize_id(requested_hypothesis_id or preview.hypothesis_id, "experiment")
        experiment_id = package_archives.sanitize_id(requested_experiment_id or preview.experiment_id, "1")
        target = workspace_root / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"
        if target.exists():
            if not overwrite:
                raise FileExistsError(f"ExperimentPack already exists: {hypothesis_id}/{experiment_id}")
            shutil.rmtree(target)
        if agentsociety_root is not None:
            _install_dependencies(package_path, agentsociety_root=agentsociety_root)
        _copy_experiment_without_run(package_path, target)
    installed = preview_experiment_pack(target)
    warnings = tuple(dict.fromkeys([*preview.validation.warnings, *installed.validation.warnings]))
    return ExperimentPackPreview(
        hypothesis_id=installed.hypothesis_id,
        experiment_id=installed.experiment_id,
        package_path=installed.package_path,
        validation=ExperimentPackValidation(installed.validation.ok, installed.validation.errors, warnings),
        map_id=installed.map_id,
        display_name=installed.display_name,
    )


def _stage_dependencies(package_path: Path, *, agentsociety_root: Path) -> None:
    init_config = _load_init_config(package_path)
    map_id = _map_id_from_init_or_context(init_config, _load_context(package_path))
    dependencies_root = package_path / "dependencies"
    if map_id:
        try:
            map_package = map_packages.load_map_package(map_id, agentsociety_root)
            shutil.copytree(map_package.package_path, dependencies_root / "maps" / map_package.map_id)
        except Exception:
            pass
    agents = init_config.get("agents")
    if isinstance(agents, list) and agents:
        initial_locations: dict[str, str] = {}
        for module in init_config.get("env_modules", []) or []:
            kwargs = module.get("kwargs") if isinstance(module, dict) else {}
            raw_locations = kwargs.get("initial_locations") if isinstance(kwargs, dict) else {}
            if isinstance(raw_locations, dict):
                initial_locations = {str(key): str(value) for key, value in raw_locations.items()}
                break
        with tempfile.TemporaryDirectory(prefix="god-experiment-agent-pack-") as temp:
            temp_root = Path(temp) / "agentsociety"
            pack = agent_packs.save_agent_pack_from_agents(
                root=temp_root,
                pack_id=f"{_infer_hypothesis_id(package_path)}-{package_path.name}-agents",
                display_name=f"{_infer_hypothesis_id(package_path)} {package_path.name} Agents",
                agents=[item for item in agents if isinstance(item, dict)],
                initial_locations=initial_locations,
            )
            shutil.copytree(pack.package_path, dependencies_root / "agent_packs" / pack.pack_id)


def _install_dependencies(package_path: Path, *, agentsociety_root: Path) -> None:
    for maps_dir in (package_path / "dependencies" / "maps", package_path / "maps"):
        if not maps_dir.exists():
            continue
        for candidate in sorted(path for path in maps_dir.iterdir() if path.is_dir()):
            manifest = map_packages._manifest_path_for_dir(candidate)
            if manifest is None:
                continue
            package = map_packages.load_map_package_by_manifest(manifest)
            target = map_packages.maps_root(agentsociety_root) / package.map_id
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(package.package_path, target)
    for packs_dir in (package_path / "dependencies" / "agent_packs", package_path / "agent_packs"):
        if not packs_dir.exists():
            continue
        for candidate in sorted(path for path in packs_dir.iterdir() if path.is_dir()):
            manifest = agent_packs._manifest_path_for_dir(candidate)
            if manifest is None:
                continue
            package = agent_packs.load_agent_pack_by_manifest(manifest)
            target = agent_packs.agent_packs_root(agentsociety_root) / package.pack_id
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(package.package_path, target)


def _load_init_config(package_path: Path) -> dict[str, Any]:
    init_path = package_path / "init" / "init_config.json"
    if not init_path.exists():
        return {}
    try:
        value = json.loads(init_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _find_experiment_root(root: Path) -> Path | None:
    candidates = [root] + [child for child in root.iterdir() if child.is_dir()]
    for candidate in candidates:
        if (candidate / "init" / "init_config.json").exists() and (candidate / "init" / "steps.yaml").exists():
            return candidate
    return None


def _copy_experiment_without_run(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=_experiment_pack_ignore())
    _remove_runtime_state(target)
    _sanitize_experiment_pack_files(target)


def sanitize_experiment_pack_config(
    config: dict[str, Any],
    *,
    map_id: str | None = None,
) -> dict[str, Any]:
    """Return an ExperimentPack-safe init config without local run identity."""

    sanitized = _strip_private_init_config_fields(config)
    if isinstance(sanitized, dict):
        _sanitize_env_module_paths(sanitized, map_id=map_id)
        return sanitized
    return {}


def _sanitize_experiment_pack_files(package_path: Path, *, map_id: str | None = None) -> None:
    init_path = package_path / "init" / "init_config.json"
    if not init_path.exists():
        return
    try:
        raw_config = json.loads(init_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(raw_config, dict):
        return
    sanitized = sanitize_experiment_pack_config(raw_config, map_id=map_id)
    if sanitized != raw_config:
        init_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _strip_private_init_config_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_private_init_config_fields(item)
            for key, item in value.items()
            if key not in _PRIVATE_INIT_CONFIG_KEYS
        }
    if isinstance(value, list):
        return [_strip_private_init_config_fields(item) for item in value]
    return value


def _sanitize_env_module_paths(config: dict[str, Any], *, map_id: str | None = None) -> None:
    env_modules = config.get("env_modules")
    if not isinstance(env_modules, list):
        return
    for module in env_modules:
        if not isinstance(module, dict):
            continue
        kwargs = module.get("kwargs")
        if not isinstance(kwargs, dict):
            continue
        if map_id and module.get("module_type") == "PixelTownSocialEnv":
            kwargs.setdefault("map_id", map_id)
        manifest_path = kwargs.get("map_manifest_path")
        if manifest_path and Path(str(manifest_path)).expanduser().is_absolute():
            kwargs.pop("map_manifest_path", None)


def _experiment_pack_ignore() -> Any:
    return shutil.ignore_patterns(
        "run",
        "run_*",
        "run_failed*",
        "run_stuck*",
        ".env",
        "*.db",
        "*.sqlite",
        "*.sqlite3",
        "*.log",
        ".runtime",
    )


def _remove_runtime_state(experiment_path: Path) -> None:
    for run_dir in _runtime_state_paths(experiment_path):
        shutil.rmtree(run_dir)
    for runtime_dir in experiment_path.rglob(".runtime"):
        if runtime_dir.exists() and runtime_dir.is_dir():
            shutil.rmtree(runtime_dir)


def _runtime_state_paths(experiment_path: Path) -> tuple[Path, ...]:
    if not experiment_path.exists():
        return ()
    return tuple(
        path
        for path in experiment_path.iterdir()
        if path.is_dir()
        and (
            path.name == "run"
            or path.name.startswith("run_")
            or path.name.startswith("run_failed")
            or path.name.startswith("run_stuck")
        )
    )


def _has_runtime_state(experiment_path: Path) -> bool:
    return any(_runtime_state_paths(experiment_path)) or any(
        path.is_dir()
        or path.name in {"sqlite.db", "thread_messages.jsonl", "agent_state_snapshot.json"}
        or path.suffix == ".log"
        for path in experiment_path.rglob("*")
        if ".runtime" in path.parts
        or path.name in {"sqlite.db", "thread_messages.jsonl", "agent_state_snapshot.json"}
        or path.suffix == ".log"
    )


def _load_context(package_path: Path) -> dict[str, Any]:
    for context_path in (
        package_path / "init" / "experiment_context.json",
        package_path / "experiment_context.json",
    ):
        if not context_path.exists():
            continue
        try:
            value = json.loads(context_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
    return {}


def _map_id_from_init_or_context(init_config: dict[str, Any], context: dict[str, Any]) -> str | None:
    for module in init_config.get("env_modules", []) or []:
        kwargs = module.get("kwargs") if isinstance(module, dict) else {}
        if isinstance(kwargs, dict) and kwargs.get("map_id"):
            return str(kwargs["map_id"])
    if context.get("map_id"):
        return str(context["map_id"])
    return None


def _infer_hypothesis_id(package_path: Path) -> str:
    parent_name = package_path.parent.name
    if parent_name.startswith("hypothesis_"):
        return parent_name.removeprefix("hypothesis_")
    context = _load_context(package_path)
    if context.get("hypothesis_id"):
        return package_archives.sanitize_id(str(context["hypothesis_id"]), "experiment")
    if context.get("title"):
        return package_archives.sanitize_id(str(context["title"]).lower(), "experiment")
    if package_path.name.startswith("experiment_"):
        return package_archives.sanitize_id(package_path.parent.name, "experiment")
    return package_archives.sanitize_id(package_path.name, "experiment")
