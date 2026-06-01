"""GOD ExperimentPack APIs."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.services import experiment_packs, package_archives


router = APIRouter(prefix="/api/v1/god/experiment-packs", tags=["god-experiment-packs"])


class ExportExperimentPackRequest(BaseModel):
    workspace_path: str
    hypothesis_id: str
    experiment_id: str


@router.post("/export")
async def export_experiment_pack(request: ExportExperimentPackRequest) -> FileResponse:
    experiment_path = (
        Path(request.workspace_path).expanduser().resolve()
        / f"hypothesis_{request.hypothesis_id}"
        / f"experiment_{request.experiment_id}"
    )
    if not experiment_path.exists():
        raise HTTPException(status_code=404, detail=f"Experiment not found: {experiment_path}")
    preview = experiment_packs.preview_experiment_pack(experiment_path)
    if not preview.ok:
        raise HTTPException(status_code=400, detail=preview.validation.as_dict())
    filename = f"{request.hypothesis_id}-experiment-pack.zip"
    temp_target = Path(tempfile.gettempdir()) / filename
    agentsociety_root = (god_setup._god_root() / "agentsociety").resolve()
    experiment_packs.export_experiment_pack(experiment_path, temp_target, agentsociety_root=agentsociety_root)
    archive_target = package_archives.archive_copy_path(
        god_root=god_setup._god_root(),
        category="experiments",
        resource_id=request.hypothesis_id,
        suffix="experiment-pack",
    )
    experiment_packs.export_experiment_pack(experiment_path, archive_target, agentsociety_root=agentsociety_root)
    return FileResponse(temp_target, filename=temp_target.name, media_type="application/zip")
