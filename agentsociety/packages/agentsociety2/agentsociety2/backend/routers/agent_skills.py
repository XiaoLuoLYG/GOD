"""
Agent Skills API 路由

提供 agent skill 的列表、启用/禁用、扫描自定义 skill、导入/创建/上传 skill 的 API 端点。

关联文件：
- @packages/agentsociety2/agentsociety2/agent/skills/__init__.py - Skill 注册表
- @extension/src/apiClient.ts - VSCode 扩展 API 客户端
- @frontend/src/pages/Skills/index.tsx - Web 前端 Skill 管理页

API 端点：
- GET  /api/v1/agent-skills/list       — 列出所有 agent skill
- POST /api/v1/agent-skills/enable     — 启用指定 skill
- POST /api/v1/agent-skills/disable    — 禁用指定 skill
- POST /api/v1/agent-skills/scan       — 扫描 workspace/custom/skills/ 下的自定义 skill
- POST /api/v1/agent-skills/import     — 从路径导入 skill 目录
- POST /api/v1/agent-skills/create     — 在线创建新 skill（SKILL.md + 可选脚本）
- POST /api/v1/agent-skills/upload     — 上传 zip 包导入 skill
- POST /api/v1/agent-skills/reload     — 热重载指定 skill
- GET  /api/v1/agent-skills/{name}/info — 获取 SKILL.md 内容
- POST /api/v1/agent-skills/remove     — 移除自定义 skill
"""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from agentsociety2.agent.skills import get_skill_registry
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/agent-skills", tags=["agent-skills"])


# ── 请求/响应模型 ──


class SkillItem(BaseModel):
    name: str
    description: str
    source: str
    enabled: bool
    path: str
    has_skill_md: bool
    script: str = ""
    requires: list[str] = []
    effects: list[str] = []
    args_schema: dict[str, Any] = Field(default_factory=dict)
    trigger_examples: list[str] = []
    shared: bool = False
    validation_status: str = "unknown"


class ListResponse(BaseModel):
    success: bool
    skills: list[SkillItem]
    total: int


class NameRequest(BaseModel):
    name: str = Field(..., description="skill 名称")


class ScanRequest(BaseModel):
    workspace_path: str | None = Field(None, description="工作区路径")


class ScanResponse(BaseModel):
    success: bool
    new_skills: list[str]
    total: int
    message: str


class ImportRequest(BaseModel):
    source_path: str = Field(..., description="skill 目录的绝对路径")
    workspace_path: str | None = Field(None, description="工作区路径")


class ImportResponse(BaseModel):
    success: bool
    name: str
    message: str


class CreateRequest(BaseModel):
    name: str = Field(..., description="skill 名称（也作为目录名）")
    description: str = Field("", description="skill 描述")
    requires: list[str] = Field(default_factory=list, description="依赖的其他 skill")
    script: str = Field("", description="subprocess 脚本相对路径（留空则为 prompt-only）")
    effects: list[str] = Field(default_factory=list, description="允许该 skill 返回的 effect 类型")
    shared: bool = Field(False, description="是否可作为所有 agent 共享 skill")
    body: str = Field("", description="SKILL.md 正文（frontmatter 之后的内容）")
    script_content: str = Field("", description="脚本文件内容（当 script 非空时使用）")
    workspace_path: str | None = Field(None, description="工作区路径")


class SimpleResponse(BaseModel):
    success: bool
    message: str


# ── API 端点 ──


@router.get("/list", response_model=ListResponse)
async def list_skills():
    """列出所有已发现的 Agent Skill（builtin + custom + env）。"""
    from pathlib import Path as PathLib

    reg = get_skill_registry()
    _ensure_custom_scanned(reg)
    _ensure_env_skills_scanned(reg)

    skills = [skill for skill in reg.list_all() if _is_visible_runtime_skill(skill)]
    items = [
        SkillItem(
            name=s.name,
            description=s.description,
            source=s.source,
            enabled=s.enabled,
            path=s.path,
            has_skill_md=(PathLib(s.path) / "SKILL.md").exists(),
            script=s.script,
            requires=list(s.requires),
            effects=list(s.effects),
            args_schema=dict(s.args_schema),
            trigger_examples=list(s.trigger_examples),
            shared=bool(s.shared),
            validation_status=_validation_status(s),
        )
        for s in skills
    ]
    return ListResponse(success=True, skills=items, total=len(items))


@router.post("/enable", response_model=SimpleResponse)
async def enable_skill(req: NameRequest):
    """启用指定的 Agent Skill。"""
    reg = get_skill_registry()
    if reg.enable(req.name):
        logger.info(f"[Skills] Enabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' enabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/disable", response_model=SimpleResponse)
async def disable_skill(req: NameRequest):
    """禁用指定的 Agent Skill。"""
    reg = get_skill_registry()
    if reg.disable(req.name):
        logger.info(f"[Skills] Disabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' disabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/scan", response_model=ScanResponse)
async def scan_custom_skills(req: ScanRequest):
    """扫描工作区的自定义 Agent Skill（{workspace}/custom/skills/）。"""
    workspace = _resolve_workspace_path(req.workspace_path)
    if not workspace:
        raise HTTPException(
            400, "workspace_path not provided and WORKSPACE_PATH not set"
        )

    reg = get_skill_registry()
    new_names = reg.scan_custom(workspace)

    return ScanResponse(
        success=True,
        new_skills=new_names,
        total=len([skill for skill in reg.list_all() if _is_visible_runtime_skill(skill)]),
        message=f"发现 {len(new_names)} 个新 skill" if new_names else "未发现新 skill",
    )


@router.post("/import", response_model=ImportResponse)
async def import_skill(req: ImportRequest):
    """从外部路径导入 Agent Skill（复制到 custom/skills/）。"""
    source = Path(req.source_path)
    if not source.is_dir():
        raise HTTPException(400, f"Source path is not a directory: {source}")

    if not (source / "SKILL.md").exists() and not (source / "scripts").is_dir():
        raise HTTPException(
            400, "Directory does not look like a skill (missing SKILL.md and scripts/)"
        )

    workspace = _resolve_workspace_path(req.workspace_path)
    if not workspace:
        raise HTTPException(
            400, "workspace_path not provided and WORKSPACE_PATH not set"
        )

    dest = Path(workspace) / "custom" / "skills" / source.name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source), str(dest))

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Imported skill '{source.name}' from {source} → {dest}")
    return ImportResponse(
        success=True,
        name=source.name,
        message=f"Skill '{source.name}' imported to {dest}",
    )


@router.post("/create", response_model=ImportResponse)
async def create_skill(req: CreateRequest):
    """在线创建新的自定义 Skill。

    在 custom/skills/{name}/ 下生成 SKILL.md（+ 可选脚本文件）。
    """
    workspace = _resolve_workspace_path(req.workspace_path)
    if not workspace:
        raise HTTPException(400, "workspace_path not provided and WORKSPACE_PATH not set")

    safe_name = req.name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    if not safe_name:
        raise HTTPException(400, "Invalid skill name")

    dest = Path(workspace) / "custom" / "skills" / safe_name
    if dest.exists():
        raise HTTPException(400, f"Skill '{safe_name}' already exists. Remove it first or use a different name.")
    dest.mkdir(parents=True, exist_ok=True)

    # 生成 SKILL.md + skill.json。前端创建的 skill 也必须是可执行结构。
    frontmatter_lines = ["---", f"name: {safe_name}", f"description: {req.description}"]
    script = req.script.strip() or "scripts/run_skill.py"
    frontmatter_lines.append(f"script: {script}")
    frontmatter_lines.append(f"shared: {'true' if req.shared else 'false'}")
    effects = req.effects or ["set_state", "remember"]
    frontmatter_lines.append("effects:")
    for effect in effects:
        frontmatter_lines.append(f"  - {effect}")
    frontmatter_lines.append('args_schema: {"type":"object","additionalProperties":true}')
    frontmatter_lines.append("trigger_examples:")
    frontmatter_lines.append(f"  - current context calls for {safe_name}")
    if req.requires:
        frontmatter_lines.append("requires:")
        for dep in req.requires:
            frontmatter_lines.append(f"  - {dep}")
    frontmatter_lines.append("---")

    body = req.body.strip() or (
        f"# {safe_name}\n\n"
        "Return one standard `SkillResult` JSON object. The runtime applies "
        "`world_effect`, `speech_effect`, and `memory_effects` after validation."
    )
    skill_md_content = "\n".join(frontmatter_lines) + "\n\n" + body + "\n"
    (dest / "SKILL.md").write_text(skill_md_content, encoding="utf-8")
    skill_spec = _default_skill_spec(
        name=safe_name,
        description=req.description,
        effects=effects,
        shared=req.shared,
    )
    (dest / "skill.json").write_text(
        json.dumps(skill_spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 写脚本文件
    if req.script_content:
        script_path = dest / script
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(req.script_content, encoding="utf-8")
    else:
        script_path = dest / script
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(_default_skill_script(safe_name), encoding="utf-8")
        script_path.chmod(0o755)

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Created skill '{safe_name}' at {dest}")
    return ImportResponse(success=True, name=safe_name, message=f"Skill '{safe_name}' created")


@router.post("/upload", response_model=ImportResponse)
async def upload_skill(
    file: UploadFile = File(..., description="skill 目录的 zip 包"),
    workspace_path: str | None = None,
):
    """上传 zip 包导入 Skill。

    zip 包应包含一个顶层目录，内含 SKILL.md。
    """
    workspace = _resolve_workspace_path(workspace_path)
    if not workspace:
        raise HTTPException(400, "workspace_path not provided and WORKSPACE_PATH not set")

    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid zip file")

    # 找到顶层目录名
    top_dirs = {n.split("/")[0] for n in zf.namelist() if "/" in n}
    if len(top_dirs) != 1:
        raise HTTPException(400, "Zip should contain exactly one top-level directory")
    skill_dir_name = top_dirs.pop()

    has_skill_md = any(
        n == f"{skill_dir_name}/SKILL.md" or n.endswith("/SKILL.md")
        for n in zf.namelist()
    )
    if not has_skill_md:
        raise HTTPException(400, "Zip does not contain a SKILL.md file")

    dest = Path(workspace) / "custom" / "skills" / skill_dir_name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    zf.extractall(str(Path(workspace) / "custom" / "skills"))
    zf.close()

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Uploaded skill '{skill_dir_name}' to {dest}")
    return ImportResponse(
        success=True,
        name=skill_dir_name,
        message=f"Skill '{skill_dir_name}' uploaded",
    )


@router.post("/reload", response_model=SimpleResponse)
async def reload_skill(req: NameRequest):
    """热重载指定 Skill 的 SKILL.md 元数据。"""
    reg = get_skill_registry()
    if reg.reload_skill(req.name):
        logger.info(f"[Skills] Reloaded: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' reloaded")
    raise HTTPException(404, f"Skill '{req.name}' not found or reload failed")


@router.get("/{name}/info")
async def get_skill_info(name: str) -> dict[str, Any]:
    """获取 Skill 的详细信息（含 SKILL.md 内容）。"""
    reg = get_skill_registry()
    info = reg.get_skill_info(name)

    if not info or not _is_visible_runtime_skill(info):
        raise HTTPException(404, f"Skill '{name}' not found")

    return {
        "success": True,
        "name": info.name,
        "description": info.description,
        "source": info.source,
        "enabled": info.enabled,
        "path": info.path,
        "script": info.script,
        "requires": list(info.requires),
        "effects": list(info.effects),
        "args_schema": dict(info.args_schema),
        "trigger_examples": list(info.trigger_examples),
        "shared": bool(info.shared),
        "validation_status": _validation_status(info),
        "skill_md": info.skill_md,
    }


@router.post("/remove", response_model=SimpleResponse)
async def remove_custom_skill(req: NameRequest):
    """移除自定义 Skill（删除目录 + 注册表记录）。仅限 source=custom。"""
    reg = get_skill_registry()
    info_dict = {s.name: s for s in reg.list_all()}
    info = info_dict.get(req.name)

    if not info:
        raise HTTPException(404, f"Skill '{req.name}' not found")
    if info.source != "custom":
        raise HTTPException(400, f"Cannot remove builtin skill '{req.name}'")

    skill_path = Path(info.path)
    if skill_path.exists():
        shutil.rmtree(skill_path)

    reg.remove_custom(req.name)
    logger.info(f"[Skills] Removed custom skill: {req.name}")
    return SimpleResponse(success=True, message=f"Custom skill '{req.name}' removed")


# ── 辅助函数 ──


def _ensure_custom_scanned(reg) -> None:
    """确保 custom skills 已扫描"""
    workspace = _resolve_workspace_path()
    if workspace:
        reg.scan_custom(workspace)


def _ensure_env_skills_scanned(reg) -> None:
    """扫描已注册环境模块附带的 agent skill 到全局 registry。"""
    from agentsociety2.registry import get_registered_env_modules
    for _module_type, env_class in get_registered_env_modules():
        for skills_dir in env_class.get_agent_skills_dirs():
            if skills_dir.is_dir():
                reg.scan_env_skills(skills_dir, env_class.__name__)


def _resolve_workspace_path(workspace_path: str | None = None) -> str | None:
    if workspace_path:
        return workspace_path
    for env_key in ("WORKSPACE_PATH", "AGENTSOCIETY_WORKSPACE_PATH", "GOD_BACKEND_ROOT"):
        env_workspace = os.getenv(env_key)
        if env_workspace and (Path(env_workspace) / "custom" / "skills").is_dir():
            return env_workspace
    god_root = os.getenv("GOD_ROOT")
    if god_root and (Path(god_root) / "agentsociety" / "custom" / "skills").is_dir():
        return str(Path(god_root) / "agentsociety")
    cwd = Path.cwd()
    if (cwd / "custom" / "skills").is_dir():
        return str(cwd)
    for parent in cwd.parents:
        if (parent / "custom" / "skills").is_dir():
            return str(parent)
    for parent in Path(__file__).resolve().parents:
        if (parent / "custom" / "skills").is_dir():
            return str(parent)
    return None


def _validation_status(info: Any) -> str:
    if not info.enabled:
        return "disabled"
    if not (Path(info.path) / "skill.json").exists():
        return "missing_skill_json"
    if not info.script:
        return "missing_script"
    if not info.effects:
        return "missing_effects"
    if not (Path(info.path) / info.script).exists():
        return "script_not_found"
    return "ready"


def _is_visible_runtime_skill(info: Any) -> bool:
    return (
        getattr(info, "source", "") == "custom"
        and (Path(info.path) / "skill.json").exists()
        and bool(getattr(info, "script", ""))
        and bool(getattr(info, "effects", []))
        and (Path(info.path) / info.script).exists()
    )


def _default_skill_spec(
    *,
    name: str,
    description: str,
    effects: list[str],
    shared: bool,
) -> dict[str, Any]:
    return {
        "skill_id": name,
        "name": name.replace(".", " ").title(),
        "description": description or f"Use {name} as a real executable GOD skill.",
        "shared": shared,
        "effects": list(effects),
        "target_locations": ["park", "cafe", "home"],
        "target_interactions": ["take_walk", "chat_over_coffee", "relax_at_home"],
        "status": "active",
        "emotion": "calm",
        "speech": "我会根据当前场景执行这个能力。",
        "memory_template": f"Used {name}: {{summary}} at {{location_id}}.",
        "failure_strategy": "set_state",
        "strategy": "configured_action",
        "trigger_examples": [f"current context calls for {name}"],
        "args_schema": {"type": "object", "additionalProperties": True},
    }


def _default_skill_script(skill_id: str) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR.parent / "_shared"))

from agent_skill_runtime import (  # noqa: E402
    build_skill_result,
    choose_available_interaction,
    choose_available_location,
    emit_result,
    load_local_skill_spec,
    memory_effect,
    observation_from,
    parse_args,
)

SKILL_ID = {skill_id!r}


def choose_world_effect(observation: dict, spec: dict) -> dict:
    current = str(observation.get("location_id") or "")
    location_id = choose_available_location(observation, list(spec.get("target_locations") or []))
    if location_id and location_id != current:
        return {{"type": "move", "location_id": location_id, "reason": f"{{SKILL_ID}}: move toward local skill target"}}
    interaction_id = choose_available_interaction(
        observation,
        list(spec.get("target_interactions") or []),
        location_id=current or location_id,
    )
    if interaction_id:
        return {{"type": "interact", "interaction_id": interaction_id, "params": {{"message": spec.get("description", SKILL_ID)}}, "reason": f"{{SKILL_ID}}: perform local skill interaction"}}
    return {{"type": "set_state", "action": str(spec.get("description") or SKILL_ID), "status": str(spec.get("status") or "active"), "emotion": str(spec.get("emotion") or "calm"), "reason": f"{{SKILL_ID}}: no configured target is reachable"}}


def main() -> int:
    args = parse_args()
    observation = observation_from(args)
    spec = load_local_skill_spec(SKILL_DIR)
    summary = str(spec.get("description") or SKILL_ID)
    location_id = str(observation.get("location_id") or "unknown")
    template = str(spec.get("memory_template") or "Used {{skill_id}}: {{summary}} at {{location_id}}.")
    result = build_skill_result(
        skill_id=SKILL_ID,
        summary=summary,
        reason=f"{{SKILL_ID}} uses its local skill.json and generated executable script.",
        world_effect=choose_world_effect(observation, spec),
        memory_effects=[
            memory_effect(
                SKILL_ID,
                template.format(skill_id=SKILL_ID, summary=summary, location_id=location_id),
                location_id=location_id,
            )
        ],
        confidence=0.72,
    )
    return emit_result(args, SKILL_ID, result)


if __name__ == "__main__":
    raise SystemExit(main())
'''
