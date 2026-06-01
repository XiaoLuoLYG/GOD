"""GOD AgentPack APIs."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.services import agent_packs
from agentsociety2.backend.services import package_archives


router = APIRouter(prefix="/api/v1/god/agent-packs", tags=["god-agent-packs"])


class ExportAgentPackRequest(BaseModel):
    pack_id: str | None = None
    map_id: str | None = None
    display_name: str | None = None
    agents: list[dict] | None = None
    initial_locations: dict[str, str] | None = None


def _root() -> Path:
    return agent_packs.agentsociety_root()


@router.get("")
@router.get("/")
async def list_agent_packs(map_id: str | None = Query(default=None)) -> dict:
    packs = agent_packs.list_agent_packs(root=_root(), map_id=map_id)
    return {"agent_packs": [agent_packs.agent_pack_summary(pack) for pack in packs]}


@router.get("/{pack_id}")
async def get_agent_pack(pack_id: str, map_id: str | None = Query(default=None)) -> dict:
    try:
        pack = agent_packs.find_agent_pack(pack_id, root=_root(), map_id=map_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return agent_packs.agent_pack_summary(pack)


@router.get("/{pack_id}/assets/{asset_path:path}")
async def get_agent_pack_asset(
    pack_id: str,
    asset_path: str,
    map_id: str | None = Query(default=None),
) -> FileResponse:
    try:
        pack = agent_packs.find_agent_pack(pack_id, root=_root(), map_id=map_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        path = agent_packs.safe_resolve(pack.package_path, asset_path, pack.package_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"AgentPack asset not found: {asset_path}")
    return FileResponse(path)


@router.post("/import")
async def import_agent_pack(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "agent-pack.zip").suffix or ".zip"
    with tempfile.NamedTemporaryFile(prefix="god-agent-pack-", suffix=suffix, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(await file.read())
    try:
        pack = agent_packs.import_agent_pack_zip(temp_path, root=_root())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return agent_packs.agent_pack_summary(pack)


@router.post("/export")
async def export_agent_pack(request: ExportAgentPackRequest) -> FileResponse:
    try:
        if request.agents:
            with tempfile.TemporaryDirectory(prefix="god-agent-pack-export-") as temp:
                pack = agent_packs.save_agent_pack_from_agents(
                    root=Path(temp) / "agentsociety",
                    pack_id=request.pack_id or "selected-agents",
                    display_name=request.display_name or request.pack_id or "Selected Agents",
                    agents=request.agents,
                    initial_locations=request.initial_locations or {},
                )
                return _agent_pack_file_response(pack)
        else:
            if not request.pack_id:
                raise ValueError("pack_id is required when agents are not provided")
            pack = agent_packs.find_agent_pack(request.pack_id, root=_root(), map_id=request.map_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _agent_pack_file_response(pack)


def _agent_pack_file_response(pack: agent_packs.AgentPack) -> FileResponse:
    target = Path(tempfile.gettempdir()) / f"{pack.pack_id}-agent-pack.zip"
    agent_packs.export_agent_pack(pack, target)
    archive_target = package_archives.archive_copy_path(
        god_root=god_setup._god_root(),
        category="agent_packs",
        resource_id=pack.pack_id,
        suffix="agent-pack",
    )
    agent_packs.export_agent_pack(pack, archive_target)
    return FileResponse(target, filename=target.name, media_type="application/zip")
