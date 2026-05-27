"""GOD Map Studio APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agentsociety2.backend.routers import god_setup
from agentsociety2.backend.services import map_generation

router = APIRouter(prefix="/api/v1/god/map-studio", tags=["god-map-studio"])
REFERENCE_UPLOAD_MAX_BYTES = 12 * 1024 * 1024
REFERENCE_UPLOAD_CHUNK_BYTES = 1024 * 1024


class MapValidationStatus(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MapStudioLocation(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    localized: dict[str, dict[str, Any]] = Field(default_factory=dict)
    anchor_tile: dict[str, int]
    scene_type: str = ""
    bounds: dict[str, int] | None = None
    interaction_ids: list[str] = Field(default_factory=list)
    visual_asset: str | None = None


class MapStudioInteraction(BaseModel):
    id: str
    name: str
    description: str = ""
    localized: dict[str, dict[str, Any]] = Field(default_factory=dict)
    allowed_location_ids: list[str] = Field(default_factory=list)
    effects: dict[str, Any] = Field(default_factory=dict)


class CollisionEdit(BaseModel):
    x: int = Field(..., ge=0, lt=map_generation.MAP_WIDTH)
    y: int = Field(..., ge=0, lt=map_generation.MAP_HEIGHT)
    blocked: bool


class MapImageConfigRequest(BaseModel):
    image_config: dict[str, Any] = Field(default_factory=dict)


class MapDraftCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    image_config: dict[str, Any] = Field(default_factory=dict)


class MapDraftPatchRequest(BaseModel):
    locations: list[MapStudioLocation] | None = None
    interactions: list[MapStudioInteraction] | None = None
    collision_edits: list[CollisionEdit] = Field(default_factory=list)


class PublishDraftRequest(BaseModel):
    map_id: str | None = None


class MapDraftResponse(BaseModel):
    draft_id: str
    map_id: str
    prompt: str
    status: str
    package_path: str
    preview_url: str
    map_image_url: str
    locations: list[MapStudioLocation]
    interactions: list[MapStudioInteraction]
    validation: MapValidationStatus
    warnings: list[str] = Field(default_factory=list)
    style_reference_used: str = "none"
    collision_data: list[int] = Field(default_factory=list)


class PublishDraftResponse(BaseModel):
    map_id: str
    package_path: str
    manifest_path: str
    validation: MapValidationStatus
    setup_url: str


def _agentsociety_root() -> Path:
    return (god_setup._god_root() / "agentsociety").resolve()


IMAGE_CONFIG_ALIASES = {
    "IMAGE_GEN_API_KEY": ("IMAGE_GEN_API_KEY", "image_api_key", "api_key"),
    "IMAGE_GEN_API_BASE": ("IMAGE_GEN_API_BASE", "image_api_base", "api_base"),
    "IMAGE_GEN_MODEL_NAME": ("IMAGE_GEN_MODEL_NAME", "image_model", "model"),
    "IMAGE_GEN_PROVIDER": ("IMAGE_GEN_PROVIDER", "image_provider", "provider"),
}


def _submitted_image_env(image_config: dict[str, Any] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for target_key, aliases in IMAGE_CONFIG_ALIASES.items():
        for alias in aliases:
            value = (image_config or {}).get(alias)
            if isinstance(value, str) and value.strip():
                values[target_key] = value.strip()
                break
    return values


def _image_env(image_config: dict[str, Any] | None = None) -> dict[str, str]:
    env = god_setup._merged_image_env()
    env.update(_submitted_image_env(image_config))
    return env


def _persist_submitted_image_env_if_used(state: dict[str, Any], image_config: dict[str, Any] | None) -> None:
    submitted = _submitted_image_env(image_config)
    if submitted and state.get("style_reference_used") != "local_placeholder":
        god_setup._write_image_env_values(submitted)


def _draft_response(state: dict[str, Any]) -> MapDraftResponse:
    draft_id = str(state["draft_id"])
    return MapDraftResponse(
        draft_id=draft_id,
        map_id=str(state["map_id"]),
        prompt=str(state.get("prompt") or ""),
        status=str(state.get("status") or "ready"),
        package_path=str(state["package_path"]),
        preview_url=f"/api/v1/god/map-studio/drafts/{draft_id}/preview.png",
        map_image_url=f"/api/v1/god/map-studio/drafts/{draft_id}/map.png",
        locations=[MapStudioLocation.model_validate(item) for item in state.get("locations", [])],
        interactions=[MapStudioInteraction.model_validate(item) for item in state.get("interactions", [])],
        validation=MapValidationStatus.model_validate(state.get("validation") or {}),
        warnings=[str(item) for item in state.get("warnings", [])],
        style_reference_used=str(state.get("style_reference_used") or "none"),
        collision_data=[int(value or 0) for value in state.get("collision_data", [])],
    )


async def _read_reference_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining_before_reject = REFERENCE_UPLOAD_MAX_BYTES + 1 - total
        chunk = await file.read(min(REFERENCE_UPLOAD_CHUNK_BYTES, remaining_before_reject))
        if not chunk:
            break
        total += len(chunk)
        if total > REFERENCE_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=400, detail="Reference image is too large; keep it under 12 MB")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/drafts", response_model=MapDraftResponse)
async def create_draft(request: MapDraftCreateRequest) -> MapDraftResponse:
    state = await map_generation.create_draft(
        root=_agentsociety_root(),
        prompt=request.prompt,
        image_config=_image_env(request.image_config),
    )
    _persist_submitted_image_env_if_used(state, request.image_config)
    return _draft_response(state)


@router.post("/drafts/upload", response_model=MapDraftResponse)
async def create_draft_with_reference(
    prompt: str = Form(...),
    file: UploadFile = File(...),
    image_api_key: str = Form(""),
    image_api_base: str = Form(""),
    image_model: str = Form(""),
    image_provider: str = Form("openai"),
) -> MapDraftResponse:
    content = await _read_reference_upload(file)
    image_config = {
        "image_api_key": image_api_key,
        "image_api_base": image_api_base,
        "image_model": image_model,
        "image_provider": image_provider,
    }
    state = await map_generation.create_draft(
        root=_agentsociety_root(),
        prompt=prompt,
        image_config=_image_env(image_config),
        reference_bytes=content,
        reference_filename=file.filename or "reference.png",
        reference_content_type=file.content_type or "image/png",
    )
    _persist_submitted_image_env_if_used(state, image_config)
    return _draft_response(state)


@router.post("/image-config")
async def save_image_config(request: MapImageConfigRequest) -> dict[str, Any]:
    values = _submitted_image_env(request.image_config)
    if values:
        god_setup._write_image_env_values(values)
    return await god_setup.setup_status()


@router.get("/drafts/{draft_id}", response_model=MapDraftResponse)
async def get_draft(draft_id: str) -> MapDraftResponse:
    return _draft_response(map_generation.load_draft(root=_agentsociety_root(), draft_id=draft_id))


@router.patch("/drafts/{draft_id}", response_model=MapDraftResponse)
async def patch_draft(draft_id: str, request: MapDraftPatchRequest) -> MapDraftResponse:
    state = map_generation.patch_draft(
        root=_agentsociety_root(),
        draft_id=draft_id,
        locations=[item.model_dump(mode="json") for item in request.locations] if request.locations is not None else None,
        interactions=[item.model_dump(mode="json") for item in request.interactions] if request.interactions is not None else None,
        collision_edits=[item.model_dump(mode="json") for item in request.collision_edits],
    )
    return _draft_response(state)


@router.post("/drafts/{draft_id}/regenerate-image", response_model=MapDraftResponse)
async def regenerate_image(draft_id: str, request: MapImageConfigRequest | None = None) -> MapDraftResponse:
    image_config = request.image_config if request is not None else {}
    state = await map_generation.regenerate_image(
        root=_agentsociety_root(),
        draft_id=draft_id,
        image_config=_image_env(image_config),
    )
    state["draft_id"] = draft_id
    _persist_submitted_image_env_if_used(state, image_config)
    return _draft_response(state)


@router.post("/drafts/{draft_id}/validate", response_model=MapDraftResponse)
async def validate_draft(draft_id: str) -> MapDraftResponse:
    return _draft_response(map_generation.validate_draft(root=_agentsociety_root(), draft_id=draft_id))


@router.post("/drafts/{draft_id}/publish", response_model=PublishDraftResponse)
async def publish_draft(draft_id: str, request: PublishDraftRequest) -> PublishDraftResponse:
    return PublishDraftResponse.model_validate(
        map_generation.publish_draft(
            root=_agentsociety_root(),
            draft_id=draft_id,
            map_id=request.map_id,
        )
    )


@router.get("/drafts/{draft_id}/preview.png")
async def draft_preview(draft_id: str) -> FileResponse:
    package_path = map_generation.draft_package_path(_agentsociety_root(), draft_id)
    path = package_path / "visuals" / "preview.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Draft preview not found")
    return FileResponse(path)


@router.get("/drafts/{draft_id}/map.png")
async def draft_map_image(draft_id: str) -> FileResponse:
    package_path = map_generation.draft_package_path(_agentsociety_root(), draft_id)
    path = package_path / "visuals" / "map_assets" / "generated_full_map_tileset.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Draft map image not found")
    return FileResponse(path)
