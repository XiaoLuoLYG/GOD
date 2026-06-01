"""Unified GOD package import APIs."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.services import package_imports


router = APIRouter(prefix="/api/v1/god/packages", tags=["god-packages"])


class InstallPackageRequest(BaseModel):
    preview_token: str
    conflict_strategy: str = "save_as"
    requested_id: str | None = None


def _agentsociety_root() -> Path:
    return (god_setup._god_root() / "agentsociety").resolve()


def _workspace_root() -> Path:
    return god_setup._workspace_path().resolve()


@router.post("/import-preview")
async def import_preview(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "package.zip").suffix or ".zip"
    with tempfile.NamedTemporaryFile(prefix="god-package-upload-", suffix=suffix, delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(await file.read())
    try:
        preview = package_imports.create_preview(
            temp_path,
            agentsociety_root=_agentsociety_root(),
            workspace_root=_workspace_root(),
            original_filename=file.filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)
    return package_imports.preview_to_dict(preview)


@router.post("/install")
async def install_package(request: InstallPackageRequest) -> dict:
    if request.conflict_strategy not in {"save_as", "overwrite", "cancel"}:
        raise HTTPException(status_code=400, detail="conflict_strategy must be save_as, overwrite, or cancel")
    if request.conflict_strategy == "cancel":
        package_imports.cancel_preview(request.preview_token)
        return {"status": "cancelled"}
    try:
        result = package_imports.install_preview(
            preview_token=request.preview_token,
            conflict_strategy=request.conflict_strategy,
            agentsociety_root=_agentsociety_root(),
            workspace_root=_workspace_root(),
            requested_id=request.requested_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "installed", **result}
