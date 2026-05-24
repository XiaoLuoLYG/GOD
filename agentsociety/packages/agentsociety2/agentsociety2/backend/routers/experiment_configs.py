"""Experiment init configuration editing APIs."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agentsociety2.backend.services.map_packages import load_map_package
from agentsociety2.society.models import InitConfig

router = APIRouter(prefix="/api/v1/experiment-configs", tags=["experiment-configs"])


ImportFormat = Literal["csv", "json", "auto"]
ApplyMode = Literal["append", "replace"]


class InitConfigResponse(BaseModel):
    config: dict[str, Any]
    path: str
    experiment_context: dict[str, Any] | None = None
    map_id: str | None = None
    map_locations: list[dict[str, Any]] = Field(default_factory=list)


class ImportPreviewRequest(BaseModel):
    content: str = Field(..., min_length=1)
    format: ImportFormat = "auto"


class ApplyAgentsRequest(BaseModel):
    agents: list[dict[str, Any]]
    mode: ApplyMode = "append"
    sync_agent_id_name_pairs: bool = True


class ImportPreviewRow(BaseModel):
    row_index: int
    valid: bool
    errors: list[str] = Field(default_factory=list)
    agent: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class ImportPreviewResponse(BaseModel):
    rows: list[ImportPreviewRow]
    valid_count: int
    invalid_count: int


class ApplyAgentsResponse(BaseModel):
    config: dict[str, Any]
    path: str
    agent_count: int
    warnings: list[str] = Field(default_factory=list)


def _experiment_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    workspace = Path(workspace_path).expanduser().resolve()
    return workspace / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"


def _init_config_path(workspace_path: str, hypothesis_id: str, experiment_id: str) -> Path:
    return _experiment_path(workspace_path, hypothesis_id, experiment_id) / "init" / "init_config.json"


def _load_init_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"init_config.json not found: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid init_config.json: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="init_config.json must contain a JSON object")
    return data


def _load_experiment_context(config_path: Path, config: dict[str, Any]) -> dict[str, Any] | None:
    context_path = config_path.parent / "experiment_context.json"
    if context_path.exists():
        try:
            context = json.loads(context_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            context = None
        if isinstance(context, dict):
            return context

    for agent in config.get("agents", []) or []:
        if not isinstance(agent, dict):
            continue
        kwargs = agent.get("kwargs")
        if not isinstance(kwargs, dict):
            continue
        context = kwargs.get("experiment_context")
        if isinstance(context, dict):
            return context
        profile = kwargs.get("profile")
        if isinstance(profile, dict) and profile.get("scenario"):
            return {"background": str(profile["scenario"])}
    return None


def _map_id_from_config(config: dict[str, Any], context: dict[str, Any] | None) -> str | None:
    for module in config.get("env_modules", []) or []:
        if not isinstance(module, dict):
            continue
        kwargs = module.get("kwargs")
        if isinstance(kwargs, dict) and kwargs.get("map_id"):
            return str(kwargs["map_id"])
    if isinstance(context, dict) and context.get("map_id"):
        return str(context["map_id"])
    return None


def _map_locations_for_config(map_id: str | None) -> list[dict[str, Any]]:
    if not map_id:
        return []
    try:
        return load_map_package(map_id).locations
    except Exception:
        return []


def _validate_init_config(config: dict[str, Any]) -> dict[str, Any]:
    try:
        return InitConfig.model_validate(config).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid init config: {exc}") from exc


def _parse_json_object(raw: str, field_name: str, errors: list[str]) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{field_name} is not valid JSON: {exc.msg}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be a JSON object")
        return {}
    return value


def _coerce_scalar(value: str) -> Any:
    text = value.strip()
    if text == "":
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _set_dotted(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = [part for part in dotted_key.split(".") if part]
    if not parts:
        return
    cursor = target
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = value


def _agent_name(agent: dict[str, Any]) -> str:
    kwargs = agent.get("kwargs")
    if isinstance(kwargs, dict):
        name = kwargs.get("name")
        if name is not None and str(name).strip():
            return str(name)
        profile = kwargs.get("profile")
        if isinstance(profile, dict) and profile.get("name") is not None:
            return str(profile["name"])
    return f"Agent_{agent.get('agent_id')}"


def _validate_agent_payload(agent: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    agent_id = agent.get("agent_id")
    try:
        agent["agent_id"] = int(agent_id)
    except (TypeError, ValueError):
        errors.append("agent_id must be an integer")

    if not str(agent.get("agent_type", "")).strip():
        errors.append("agent_type is required")

    kwargs = agent.get("kwargs")
    if not isinstance(kwargs, dict):
        errors.append("kwargs must be an object")
        return errors

    if "id" not in kwargs:
        errors.append("kwargs.id is required")
    else:
        try:
            kwargs["id"] = int(kwargs["id"])
        except (TypeError, ValueError):
            errors.append("kwargs.id must be an integer")

    if (
        isinstance(agent.get("agent_id"), int)
        and isinstance(kwargs.get("id"), int)
        and agent["agent_id"] != kwargs["id"]
    ):
        errors.append("agent_id must match kwargs.id")

    return errors


def _build_agent_from_csv_row(row: dict[str, Any], row_index: int) -> ImportPreviewRow:
    errors: list[str] = []

    agent_id_raw = str(row.get("agent_id", "")).strip()
    agent_type = str(row.get("agent_type", "")).strip()
    name = str(row.get("name", "")).strip()

    if not agent_id_raw:
        errors.append("agent_id is required")
    if not agent_type:
        errors.append("agent_type is required")
    if not name:
        errors.append("name is required")

    try:
        agent_id = int(agent_id_raw)
    except ValueError:
        agent_id = 0
        if agent_id_raw:
            errors.append("agent_id must be an integer")

    profile: dict[str, Any] = {}
    kwargs: dict[str, Any] = {}

    for key, raw_value in row.items():
        value_text = "" if raw_value is None else str(raw_value)
        if value_text.strip() == "":
            continue
        if key.startswith("profile."):
            _set_dotted(profile, key.removeprefix("profile."), _coerce_scalar(value_text))
        elif key.startswith("kwargs."):
            _set_dotted(kwargs, key.removeprefix("kwargs."), _coerce_scalar(value_text))

    profile.update(_parse_json_object(str(row.get("profile_json", "") or ""), "profile_json", errors))
    kwargs.update(_parse_json_object(str(row.get("kwargs_json", "") or ""), "kwargs_json", errors))

    profile.setdefault("name", name)
    if "id" not in kwargs:
        kwargs["id"] = agent_id
    kwargs.setdefault("name", name)
    kwargs["profile"] = profile

    agent = {"agent_id": agent_id, "agent_type": agent_type, "kwargs": kwargs}
    errors.extend(_validate_agent_payload(agent))
    return ImportPreviewRow(
        row_index=row_index,
        valid=not errors,
        errors=errors,
        agent=agent if not errors else None,
        raw={key: value for key, value in row.items()},
    )


def _parse_csv_import(content: str) -> list[ImportPreviewRow]:
    reader = csv.DictReader(StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include a header row")
    missing = {"agent_id", "agent_type", "name"} - set(reader.fieldnames)
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {sorted(missing)}")
    return [_build_agent_from_csv_row(row, index) for index, row in enumerate(reader, start=1)]


def _parse_json_import(content: str) -> list[ImportPreviewRow]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON import payload: {exc}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("agents"), list):
        items = payload["agents"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise HTTPException(status_code=400, detail="JSON import must be a list or an object with an agents list")

    rows: list[ImportPreviewRow] = []
    for index, item in enumerate(items, start=1):
        errors: list[str] = []
        if not isinstance(item, dict):
            errors.append("row must be an object")
            rows.append(ImportPreviewRow(row_index=index, valid=False, errors=errors, raw={"value": item}))
            continue

        agent = json.loads(json.dumps(item))
        if "kwargs" not in agent:
            profile = agent.get("profile")
            if not isinstance(profile, dict):
                profile = {"name": agent.get("name") or f"Agent_{agent.get('agent_id')}"}
            else:
                profile = dict(profile)
            name = str(agent.get("name") or profile.get("name") or f"Agent_{agent.get('agent_id')}")
            agent = {
                "agent_id": agent.get("agent_id"),
                "agent_type": agent.get("agent_type"),
                "kwargs": {
                    "id": agent.get("agent_id"),
                    "name": name,
                    "profile": profile,
                    **(agent.get("extra_kwargs") if isinstance(agent.get("extra_kwargs"), dict) else {}),
                },
            }

        errors.extend(_validate_agent_payload(agent))
        rows.append(
            ImportPreviewRow(
                row_index=index,
                valid=not errors,
                errors=errors,
                agent=agent if not errors else None,
                raw=item,
            )
        )
    return rows


def _detect_import_format(content: str, requested_format: ImportFormat) -> Literal["csv", "json"]:
    if requested_format in ("csv", "json"):
        return requested_format
    stripped = content.lstrip()
    return "json" if stripped.startswith("[") or stripped.startswith("{") else "csv"


def _mark_duplicate_ids(rows: list[ImportPreviewRow]) -> None:
    seen: dict[int, int] = {}
    for row in rows:
        if not row.agent:
            continue
        agent_id = row.agent.get("agent_id")
        if not isinstance(agent_id, int):
            continue
        if agent_id in seen:
            row.errors.append(f"duplicate agent_id also used by row {seen[agent_id]}")
            row.valid = False
            row.agent = None
        else:
            seen[agent_id] = row.row_index


def _preview_agents(content: str, import_format: ImportFormat) -> ImportPreviewResponse:
    resolved_format = _detect_import_format(content, import_format)
    rows = _parse_json_import(content) if resolved_format == "json" else _parse_csv_import(content)
    _mark_duplicate_ids(rows)
    valid_count = sum(1 for row in rows if row.valid)
    return ImportPreviewResponse(
        rows=rows,
        valid_count=valid_count,
        invalid_count=len(rows) - valid_count,
    )


def _sync_agent_id_name_pairs(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    pairs = [[agent["agent_id"], _agent_name(agent)] for agent in config.get("agents", [])]
    synced = False
    for module in config.get("env_modules", []):
        kwargs = module.get("kwargs")
        if isinstance(kwargs, dict) and "agent_id_name_pairs" in kwargs:
            kwargs["agent_id_name_pairs"] = pairs
            synced = True
    if not synced:
        warnings.append("No env module with kwargs.agent_id_name_pairs was found; agent names were not synced to env modules.")
    return warnings


@router.get("/{hypothesis_id}/{experiment_id}/init", response_model=InitConfigResponse)
async def get_init_config(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> InitConfigResponse:
    config_path = _init_config_path(workspace_path, hypothesis_id, experiment_id)
    config = _load_init_config(config_path)
    context = _load_experiment_context(config_path, config)
    map_id = _map_id_from_config(config, context)
    return InitConfigResponse(
        config=config,
        path=str(config_path),
        experiment_context=context,
        map_id=map_id,
        map_locations=_map_locations_for_config(map_id),
    )


@router.put("/{hypothesis_id}/{experiment_id}/init", response_model=InitConfigResponse)
async def put_init_config(
    hypothesis_id: str,
    experiment_id: str,
    config: dict[str, Any],
    workspace_path: str = Query(..., description="Workspace root path"),
) -> InitConfigResponse:
    config_path = _init_config_path(workspace_path, hypothesis_id, experiment_id)
    validated = _validate_init_config(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return InitConfigResponse(config=validated, path=str(config_path))


@router.post("/{hypothesis_id}/{experiment_id}/agents/import-preview", response_model=ImportPreviewResponse)
async def import_agents_preview(
    hypothesis_id: str,
    experiment_id: str,
    request: ImportPreviewRequest,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ImportPreviewResponse:
    _ = _init_config_path(workspace_path, hypothesis_id, experiment_id)
    return _preview_agents(request.content, request.format)


@router.post("/{hypothesis_id}/{experiment_id}/agents/apply", response_model=ApplyAgentsResponse)
async def apply_agents(
    hypothesis_id: str,
    experiment_id: str,
    request: ApplyAgentsRequest,
    workspace_path: str = Query(..., description="Workspace root path"),
) -> ApplyAgentsResponse:
    config_path = _init_config_path(workspace_path, hypothesis_id, experiment_id)
    config = _load_init_config(config_path)

    incoming = [json.loads(json.dumps(agent)) for agent in request.agents]
    errors: list[str] = []
    for index, agent in enumerate(incoming, start=1):
        agent_errors = _validate_agent_payload(agent)
        if agent_errors:
            errors.append(f"agent {index}: {'; '.join(agent_errors)}")
    if errors:
        raise HTTPException(status_code=400, detail=errors)

    if request.mode == "replace":
        config["agents"] = incoming
    else:
        existing = list(config.get("agents", []))
        existing_ids = {agent.get("agent_id") for agent in existing if isinstance(agent, dict)}
        duplicate_ids = [agent["agent_id"] for agent in incoming if agent["agent_id"] in existing_ids]
        if duplicate_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate agent_id already exists: {duplicate_ids}")
        config["agents"] = existing + incoming

    all_ids = [agent.get("agent_id") for agent in config.get("agents", []) if isinstance(agent, dict)]
    if len(all_ids) != len(set(all_ids)):
        raise HTTPException(status_code=400, detail="Duplicate agent_id values are not allowed")

    warnings = _sync_agent_id_name_pairs(config) if request.sync_agent_id_name_pairs else []
    validated = _validate_init_config(config)
    config_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ApplyAgentsResponse(
        config=validated,
        path=str(config_path),
        agent_count=len(validated["agents"]),
        warnings=warnings,
    )
