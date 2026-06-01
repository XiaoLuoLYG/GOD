"""GOD MapPack APIs."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.services import map_generation, map_packages, package_archives


router = APIRouter(prefix="/api/v1/god/map-packs", tags=["god-map-packs"])


class ExportMapPackRequest(BaseModel):
    map_id: str | None = None
    draft_id: str | None = None


@router.post("/export")
async def export_map_pack(request: ExportMapPackRequest) -> FileResponse:
    agentsociety_root = (god_setup._god_root() / "agentsociety").resolve()
    if request.draft_id:
        try:
            draft_path = map_generation.draft_package_path(agentsociety_root, request.draft_id)
            package = map_packages.load_map_package_by_manifest(draft_path / "map.yaml")
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        if not request.map_id:
            raise HTTPException(status_code=400, detail="map_id or draft_id is required")
        try:
            package = map_packages.load_map_package(request.map_id, agentsociety_root)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    temp_target = Path(tempfile.gettempdir()) / f"{package.map_id}-map-pack.zip"
    map_packages.export_map_pack(package, temp_target)
    archive_target = package_archives.archive_copy_path(
        god_root=god_setup._god_root(),
        category="maps",
        resource_id=package.map_id,
        suffix="map-pack",
    )
    map_packages.export_map_pack(package, archive_target)
    return FileResponse(temp_target, filename=temp_target.name, media_type="application/zip")
