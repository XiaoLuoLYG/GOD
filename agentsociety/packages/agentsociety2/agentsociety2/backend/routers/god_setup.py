"""GOD startup setup and experiment-draft APIs."""

from __future__ import annotations

import base64
import json
import os
import re
import asyncio
import hashlib
import io
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import json_repair
import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image, UnidentifiedImageError

from agentsociety2.config import extract_json
from agentsociety2.backend.services import agent_packs as agent_pack_service
from agentsociety2.backend.services import experiment_registry
from agentsociety2.backend.services.map_packages import (
    DEFAULT_MAP_ID,
    MapPackage,
    character_sprites,
    list_map_packages,
    load_map_package,
    map_package_summary,
    relative_manifest_path,
    safe_resolve,
)
from agentsociety2.society.models import InitConfig, StepsConfig

router = APIRouter(prefix="/api/v1/god/setup", tags=["god-setup"])


ENV_DEFAULTS = {
    "GOD_LLM_API_BASE": "https://api.openai.com/v1",
    "GOD_LLM_MODEL": "gpt-5.4",
    "GOD_EMBEDDING_MODEL": "text-embedding-3-large",
    "GOD_BACKEND_HOST": "127.0.0.1",
    "GOD_BACKEND_PORT": "8001",
    "GOD_FRONTEND_PORT": "5174",
}

DEFAULT_EXPERIMENT_KEY = experiment_registry.DEFAULT_EXPERIMENT_KEY

MODEL_KEYS = (
    "GOD_LLM_API_KEY",
    "GOD_LLM_API_BASE",
    "GOD_LLM_MODEL",
    "GOD_EMBEDDING_API_KEY",
    "GOD_EMBEDDING_API_BASE",
    "GOD_EMBEDDING_MODEL",
    "GOD_BACKEND_HOST",
    "GOD_BACKEND_PORT",
    "GOD_FRONTEND_PORT",
)

SENSITIVE_KEYS = {"GOD_LLM_API_KEY", "GOD_EMBEDDING_API_KEY"}
IMAGE_MODEL_KEYS = (
    "IMAGE_GEN_API_KEY",
    "IMAGE_GEN_API_BASE",
    "IMAGE_GEN_MODEL_NAME",
    "IMAGE_GEN_PROVIDER",
)
IMAGE_ENV_DEFAULTS = {
    "IMAGE_GEN_API_BASE": "https://api.openai.com/v1",
    "IMAGE_GEN_MODEL_NAME": "gpt-image-1.5",
    "IMAGE_GEN_PROVIDER": "openai",
}
IMAGE_SENSITIVE_KEYS = {"IMAGE_GEN_API_KEY"}
AGENT_SPRITE_SIZE = (96, 128)
AGENT_SPRITE_FRAME_SIZE = (32, 32)
AGENT_SPRITE_GENERATION_ATTEMPTS = 3


def _default_public_group_name(title: str) -> str:
    title = str(title or "").strip()
    return f"{title}公开频道" if title else "GOD 公开频道"

DEFAULT_DRAFT_BACKGROUND = (
    "请生成一个安全、边界清晰的社会角色压力模拟：参与者被分配为管理者、观察者、"
    "普通参与者等角色，重点观察权力、规则、协作和情绪变化，不允许羞辱、伤害或强迫行为。"
)

COMMON_SKILL_IDS = [
    "routine.daily",
    "social.reply",
    "memory.record",
    "map.navigate",
    "safety.respond",
]

PERSONA_SKILL_IDS = [
    "community.coordinate",
    "conflict.mediate",
    "first_aid.basic",
    "notice.write",
    "messaging.group",
    "tools.repair",
    "inventory.count",
    "route.localmap",
    "ledger.basic",
    "neighbor.support",
    "class.organize",
    "youth.communicate",
    "writing.feedback",
    "history.localtelling",
    "library.curate",
    "care.basic",
    "chronic.followup",
    "emotion.calm",
    "health.educate",
    "record.shortnote",
    "cooking.lightmeal",
    "listen.relay",
    "shop.run",
    "social.matchmake",
    "community.observe",
    "class.learn",
    "sketch.draw",
    "phone.photolog",
    "computer.basic",
    "peer.communicate",
    "route.recall",
    "garden.basic",
    "story.localpast",
    "writing.hand",
    "neighbor.greet",
    "computer.repair",
    "script.automate",
    "info.research",
    "remote.communicate",
    "privacy.protect",
    "patrol.plan",
    "roster.verify",
    "repair.basic",
    "crowd.guide",
    "radio.comms",
    "vegetable.source",
    "stall.run",
    "price.negotiate",
    "ingredient.advise",
    "gossip.filter",
]


class ModelConfigPayload(BaseModel):
    GOD_LLM_API_KEY: str | None = None
    GOD_LLM_API_BASE: str | None = None
    GOD_LLM_MODEL: str | None = None
    GOD_EMBEDDING_API_KEY: str | None = None
    GOD_EMBEDDING_API_BASE: str | None = None
    GOD_EMBEDDING_MODEL: str | None = None
    GOD_BACKEND_HOST: str | None = None
    GOD_BACKEND_PORT: str | None = None
    GOD_FRONTEND_PORT: str | None = None


class DraftBasics(BaseModel):
    title: str = Field("斯坦福监狱实验适配模拟", min_length=1)
    background: str = Field(DEFAULT_DRAFT_BACKGROUND, min_length=1)
    agent_count: int = Field(10, ge=1, le=50)
    map_id: str = DEFAULT_MAP_ID
    language: str = "zh"
    start_t: str = "2026-05-11T08:20:00+08:00"
    num_steps: int = Field(4, ge=1, le=100)
    tick: int = Field(1800, ge=1)
    movement_tiles_per_second: float = Field(8.0, gt=0)
    movement_min_steps_per_trip: int = Field(3, ge=1)


class GenerateDraftRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    llm_config: ModelConfigPayload | None = Field(default=None, alias="model_config")
    basics: DraftBasics = Field(default_factory=DraftBasics)


class PublishRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    draft: dict[str, Any]
    llm_config: ModelConfigPayload | None = Field(default=None, alias="model_config")
    requested_hypothesis_id: str | None = None
    experiment_id: str = "1"
    start_immediately: bool = False


class StartRequestPayload(BaseModel):
    hypothesis_id: str | None = None
    experiment_id: str | None = None
    workspace_path: str | None = None


class StartDefaultRequest(BaseModel):
    experiment_key: str = DEFAULT_EXPERIMENT_KEY


class AgentStudioGenerateRequest(BaseModel):
    experiment_context: dict[str, Any] = Field(default_factory=dict)
    map_id: str = DEFAULT_MAP_ID
    map_locations: list[dict[str, Any]] = Field(default_factory=list)
    existing_agents: list[dict[str, Any]] = Field(default_factory=list)
    language: str = "zh"
    source: dict[str, Any] = Field(default_factory=dict)
    locked_choices: dict[str, str] = Field(default_factory=dict)
    custom_choices: dict[str, str] = Field(default_factory=dict)


class AgentStudioOption(BaseModel):
    id: str
    label: str
    description: str | None = None


class AgentStudioGroup(BaseModel):
    id: str
    title: str
    step: str
    allow_custom: bool = True
    options: list[AgentStudioOption] = Field(default_factory=list)


class AgentStudioCharacterAsset(BaseModel):
    sprite_name: str
    filename: str
    image_url: str
    frame_width: int = 32
    frame_height: int = 32
    source_photo_name: str | None = None
    generated_from_photo: bool = True
    preview_data_url: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)


class AgentStudioGenerateResponse(BaseModel):
    groups: list[AgentStudioGroup]
    selected_choices: dict[str, str]
    profile_patch: dict[str, Any]
    initial_location: str
    warnings: list[str] = Field(default_factory=list)
    character_asset: AgentStudioCharacterAsset | None = None


class CompleteRoleVisualsRequest(BaseModel):
    draft: dict[str, Any]
    image_config: dict[str, Any] = Field(default_factory=dict)


class SaveAgentPackRequest(BaseModel):
    pack_id: str
    display_name: str | None = None
    agent: dict[str, Any]
    initial_location: str | None = None


class CompleteRoleVisualResult(BaseModel):
    agent_id: int
    name: str
    status: str
    filename: str | None = None
    error: str | None = None


class CompleteRoleVisualsResponse(BaseModel):
    draft: dict[str, Any]
    results: list[CompleteRoleVisualResult]
    completed_count: int
    failed_count: int


def _god_root() -> Path:
    raw = os.getenv("GOD_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()

    cwd = Path.cwd().resolve()
    if cwd.name == "agentsociety" and (cwd.parent / "scripts" / "god.sh").exists():
        return cwd.parent
    if (cwd / "scripts" / "god.sh").exists():
        return cwd
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "god.sh").exists():
            return parent
    return cwd


def _env_file() -> Path:
    return Path(os.getenv("GOD_ENV_FILE", str(_god_root() / ".env"))).expanduser().resolve()


def _workspace_path() -> Path:
    raw = os.getenv("LIVE_WORKSPACE_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return (_god_root() / "agentsociety" / "quick_experiments").resolve()


def _state_dir() -> Path:
    return (_god_root() / ".god").resolve()


def _current_experiment_file() -> Path:
    return _state_dir() / "current_experiment.json"


def _start_request_file() -> Path:
    return _state_dir() / "run" / "start-request.json"


def _latest_draft_file() -> Path:
    return _state_dir() / "run" / "latest-draft.json"


def _read_env(path: Path | None = None) -> dict[str, str]:
    path = path or _env_file()
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_values(values: dict[str, str]) -> None:
    path = _env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    out: list[str] = []
    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():
        if out and out[-1] != "":
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _write_model_env_values(values: dict[str, str]) -> None:
    allowed = set(MODEL_KEYS)
    filtered = {key: value for key, value in values.items() if key in allowed}
    if not filtered:
        return
    _write_env_values(filtered)


def _write_image_env_values(values: dict[str, str]) -> None:
    allowed = set(IMAGE_MODEL_KEYS)
    filtered = {key: value for key, value in values.items() if key in allowed}
    if not filtered:
        return
    _write_env_values(filtered)


def _merged_env() -> dict[str, str]:
    env = dict(ENV_DEFAULTS)
    for key in MODEL_KEYS:
        if os.getenv(key):
            env[key] = os.environ[key]
    env.update(_read_env())
    return env


def _merged_image_env() -> dict[str, str]:
    env = dict(IMAGE_ENV_DEFAULTS)
    for key in IMAGE_MODEL_KEYS:
        if os.getenv(key):
            env[key] = os.environ[key]
    for key, value in _read_env().items():
        if key in IMAGE_MODEL_KEYS:
            env[key] = value
    return env


def _redact_value(key: str, value: str | None) -> dict[str, Any]:
    if not value:
        return {"configured": False, "value": ""}
    if key in SENSITIVE_KEYS or key in IMAGE_SENSITIVE_KEYS:
        tail = value[-4:] if len(value) >= 4 else "****"
        return {"configured": True, "value": f"••••{tail}"}
    return {"configured": True, "value": value}


def _sanitize_slug(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text[:48] or f"custom_{uuid.uuid4().hex[:8]}"


def _experiment_path(workspace: Path, hypothesis_id: str, experiment_id: str) -> Path:
    return workspace / f"hypothesis_{hypothesis_id}" / f"experiment_{experiment_id}"


def _default_experiment_status(workspace: Path) -> list[dict[str, Any]]:
    return experiment_registry.status_entries(workspace)


def _map_service_root() -> Path | None:
    candidate = _god_root() / "agentsociety"
    return candidate if (candidate / "custom" / "maps").exists() else None


def _load_map_package(map_id: str | None = None) -> MapPackage:
    selected = str(map_id or DEFAULT_MAP_ID)
    try:
        return load_map_package(selected, _map_service_root())
    except Exception:
        if selected != DEFAULT_MAP_ID:
            return load_map_package(DEFAULT_MAP_ID, _map_service_root())
        raise


def _available_map_packages() -> list[MapPackage]:
    packages = list_map_packages(_map_service_root())
    if packages:
        return packages
    return [load_map_package(DEFAULT_MAP_ID)]


def _load_map_manifest(map_id: str | None = None) -> dict[str, Any]:
    return _load_map_package(map_id).manifest


def _known_location_ids(map_id: str | None = None) -> list[str]:
    manifest = _load_map_manifest(map_id)
    locations = manifest.get("locations") or []
    return [str(item.get("id")) for item in locations if isinstance(item, dict) and item.get("id")]


def _known_location_ids_for_package(package: MapPackage) -> list[str]:
    try:
        return _known_location_ids(package.map_id)
    except TypeError:
        # Some older tests monkeypatch _known_location_ids with a zero-arg lambda.
        return _known_location_ids()  # type: ignore[call-arg]


def _map_locations_for_status(map_id: str | None = None) -> list[dict[str, Any]]:
    try:
        locations = _load_map_manifest(map_id).get("locations", [])
    except Exception:
        return []
    return [item for item in locations if isinstance(item, dict)]


def _map_location_prompt(package: MapPackage) -> str:
    manifest = package.manifest
    lines: list[str] = []
    for item in manifest.get("locations") or []:
        if not isinstance(item, dict):
            continue
        interactions = ", ".join(str(v) for v in item.get("interaction_ids", []) or [])
        aliases = ", ".join(str(v) for v in item.get("aliases", []) or [])[:120]
        lines.append(
            f"- {item.get('id')}: {item.get('name')} | aliases: {aliases} | interactions: {interactions}"
        )
    return "\n".join(lines)


def _fallback_location(index: int, known_locations: list[str], package: MapPackage | None = None) -> str:
    if not known_locations:
        return "park"
    preferred = package.default_location_order if package else []
    if not preferred:
        preferred = ["home", "school", "library", "cafe", "park", "supply_store", "market", "pharmacy", "town_square"]
    ordered = [loc for loc in preferred if loc in known_locations] or known_locations
    return ordered[index % len(ordered)]


_ZH_NAMES = [
    "林若晨",
    "陈明远",
    "周安然",
    "许嘉宁",
    "沈知夏",
    "赵远山",
    "顾小满",
    "梁一舟",
    "韩清越",
    "苏晚晴",
    "马知行",
    "何雨桐",
]

_EN_NAMES = [
    "Maya Lin",
    "Owen Chen",
    "Nora Hale",
    "Ethan Brooks",
    "Iris Wang",
    "Sam Rivera",
    "Leah Park",
    "Jonah Reed",
    "Ava Morgan",
    "Milo Tan",
    "Grace Liu",
    "Noah Patel",
]


def _language_is_zh(language: str) -> bool:
    return not str(language or "").lower().startswith("en")


def _locale_key(language: str) -> str:
    return "zh" if _language_is_zh(language) else "en"


_KNOWN_CONTEXT_TEXT: dict[str, dict[str, str]] = {
    "上帝模式小镇 · 维尔普通工作日": {
        "en": "GOD Town · The Ville Ordinary Workday",
        "zh": "上帝模式小镇 · 维尔普通工作日",
    },
    "晚春的一个工作日清晨 8:20。维尔小镇是一个 200 多人的小镇，10 位常住居民彼此熟识但不黏腻。天气晴朗微风，温度 18 摄氏度。镇上没有突发事件，是一段反映自然节奏的日常切片。": {
        "en": "A late-spring weekday morning at 8:20. The Ville is a town of just over 200 people, where 10 standing residents know one another well without being clingy. The weather is sunny with a light breeze at 18°C. Nothing unusual is happening in town; this is a natural slice of everyday life.",
        "zh": "晚春的一个工作日清晨 8:20。维尔小镇是一个 200 多人的小镇，10 位常住居民彼此熟识但不黏腻。天气晴朗微风，温度 18 摄氏度。镇上没有突发事件，是一段反映自然节奏的日常切片。",
    },
    "北大校园日常观察": {
        "en": "PKU Campus Daily Observation",
        "zh": "北大校园日常观察",
    },
    "2026-05-15，北京大学燕园。现在是一个普通周五上午，校园居民只知道自己的课程、科研、食堂、社团、宿舍和日常安排。后续公共事件只有在校内通知出现后才进入角色认知。": {
        "en": "May 15, 2026, Peking University Yanyuan. It is an ordinary Friday morning. Campus residents only know about their classes, research, canteens, clubs, dorms, and daily routines. Later public events enter character awareness only after an official campus notice appears.",
        "zh": "2026-05-15，北京大学燕园。现在是一个普通周五上午，校园居民只知道自己的课程、科研、食堂、社团、宿舍和日常安排。后续公共事件只有在校内通知出现后才进入角色认知。",
    },
}


def _localized_record_value(record: dict[str, Any], field: str, language: str) -> str | None:
    localized = record.get("localized")
    if isinstance(localized, dict):
        language_values = localized.get(_locale_key(language))
        if isinstance(language_values, dict):
            value = language_values.get(field)
            if value is not None and str(value).strip():
                return str(value)
    value = record.get(field)
    return str(value) if value is not None and str(value).strip() else None


def _localized_context_value(context: dict[str, Any], field: str, language: str) -> str:
    value = _localized_record_value(context, field, language)
    if value in _KNOWN_CONTEXT_TEXT:
        return _KNOWN_CONTEXT_TEXT[value][_locale_key(language)]
    return value or ""


def _studio_slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower()).strip("_")
    return slug[:48] or fallback


def _studio_rotate(items: list[str], seed: str, group_id: str, count: int = 4) -> list[str]:
    if not items:
        return []
    if len(items) <= count:
        return items
    anchors = items[:2]
    rest = items[2:]
    digest = hashlib.sha256(f"{seed}:{group_id}".encode("utf-8")).hexdigest()
    start = int(digest[:8], 16) % len(rest)
    rotated = rest[start:] + rest[:start]
    return (anchors + rotated)[:count]


def _studio_detect_theme(seed_text: str) -> str:
    text = seed_text.lower()
    if any(word in text for word in ("变形金刚", "transformer", "robot", "机器人", "机甲", "月球", "moon")):
        return "mecha"
    if any(word in text for word in ("吸血鬼", "vampire", "魔法", "wizard", "dragon", "奇幻", "fantasy")):
        return "fantasy"
    if any(word in text for word in ("学校", "校园", "student", "class", "university", "campus")):
        return "campus"
    return "grounded"


def _studio_options_for_theme(theme: str, zh: bool) -> dict[str, list[str]]:
    if zh:
        base = {
            "identity_role": ["社区观察员", "生活协调者", "规则维护者", "关系连接者", "安静执行者", "公共事务参与者"],
            "identity_function": ["观察", "协调", "探索", "记录", "照顾", "挑战", "修复", "连接"],
            "appearance_form": ["清爽人形", "高挑轮廓", "沉稳体态", "轻盈行动", "低调存在", "醒目标识"],
            "appearance_eyes": ["圆眼", "杏眼", "笑眼", "细长眼", "深邃眼", "发光眼"],
            "appearance_hair": ["短发", "中长发", "微乱发", "卷发", "长直发", "利落造型"],
            "appearance_style": ["学院风", "通勤风", "街头风", "工作制服", "复古风", "科技风", "居家风"],
            "personality_core": ["冷静观察者", "温柔照料者", "活力发起者", "理性分析者", "好奇实验者", "稳定守序者"],
            "personality_social": ["独处蓄能", "熟人亲近", "主动破冰", "广泛连接", "礼貌疏离", "团队中心"],
            "personality_decision": ["数据优先", "直觉判断", "共识协商", "快速试错", "规则导向", "价值驱动"],
            "personality_mood": ["平静克制", "温暖柔和", "高能外放", "敏感细腻", "松弛幽默", "严肃专注"],
            "routine_goal": ["学习成长", "建立关系", "完成任务", "探索社区", "帮助他人", "影响群体", "保持稳定"],
            "routine_habit": ["早起计划型", "夜间灵感型", "稳定通勤型", "自由漫游型", "社交密集型", "安静驻留型"],
            "relationship_style": ["慢热", "主动邀约", "互助", "良性竞争", "照顾型", "边界清晰", "导师型"],
        }
        overlays = {
            "mecha": {
                "identity_role": ["机械生命居民", "轨道通勤者", "公共交通守护者", "月面任务联络员", "伪装工程师", "城市维护者"],
                "appearance_form": ["人形机甲", "列车伪装形态", "钛银装甲", "白色航天涂装", "折叠轮组", "月尘划痕"],
                "appearance_eyes": ["蓝色光学镜", "双眼光学灯", "窄缝扫描器", "柔和发光眼", "警戒红光", "透明护目镜"],
                "appearance_style": ["航天工装", "轨道交通制服", "工业维护风", "低调伪装风", "银黑科技风", "旧城列车涂装"],
                "personality_core": ["可靠执行者", "沉默守护者", "程序化幽默者", "谨慎适应者", "使命驱动者", "社恐但可靠"],
                "routine_goal": ["维护秩序", "完成远程任务", "理解人类通勤", "保护公共空间", "学习社会规则", "稳定融入社区"],
            },
            "fantasy": {
                "identity_role": ["隐秘住民", "夜间记录者", "古老契约守护者", "社区药剂师", "雨天来访者", "图书馆访客"],
                "appearance_form": ["优雅人形", "古典轮廓", "暗色披肩", "银色饰物", "柔和微光", "非日常气质"],
                "personality_core": ["克制的浪漫者", "古怪守序者", "温柔旁观者", "慢热守护者", "好奇收藏者", "礼貌疏离者"],
                "routine_goal": ["隐藏身份", "守护约定", "收集故事", "学习当代生活", "维系旧关系", "避免打扰他人"],
            },
            "campus": {
                "identity_role": ["校园观察员", "社团组织者", "图书馆常客", "课程助教", "寝室协调者", "活动志愿者"],
                "routine_goal": ["完成学习任务", "组织活动", "建立同伴关系", "观察校园秩序", "帮助新成员", "平衡压力"],
            },
        }
    else:
        base = {
            "identity_role": ["community observer", "daily-life coordinator", "rules steward", "relationship bridge", "quiet operator", "public-space participant"],
            "identity_function": ["observe", "coordinate", "explore", "record", "care", "challenge", "repair", "connect"],
            "appearance_form": ["clean human silhouette", "tall profile", "steady posture", "light movement", "low-key presence", "signature marker"],
            "appearance_eyes": ["round eyes", "almond eyes", "smiling eyes", "narrow eyes", "deep-set eyes", "glowing eyes"],
            "appearance_hair": ["short hair", "mid-length hair", "messy hair", "curly hair", "long straight hair", "neat styling"],
            "appearance_style": ["academic", "commuter", "streetwear", "work uniform", "retro", "techwear", "home casual"],
            "personality_core": ["calm observer", "warm caretaker", "energetic initiator", "rational analyst", "curious experimenter", "stable rule-keeper"],
            "personality_social": ["recharges alone", "close with familiar people", "breaks the ice", "broad connector", "polite distance", "team center"],
            "personality_decision": ["data-first", "intuitive judgment", "consensus-seeking", "fast trial-and-error", "rule-guided", "values-driven"],
            "personality_mood": ["calm and restrained", "warm and soft", "high-energy", "sensitive and subtle", "relaxed humor", "serious focus"],
            "routine_goal": ["learn and grow", "build relationships", "finish tasks", "explore the community", "help others", "influence the group", "keep stability"],
            "routine_habit": ["early planner", "night-idea maker", "steady commuter", "free roamer", "socially dense", "quietly stationed"],
            "relationship_style": ["slow to warm", "actively invites", "mutual help", "friendly rivalry", "caretaking", "clear boundaries", "mentor-like"],
        }
        overlays = {
            "mecha": {
                "identity_role": ["mechanical life resident", "orbital commuter", "public transit guardian", "moon-task liaison", "disguised engineer", "city maintainer"],
                "appearance_form": ["humanoid mech", "train-disguise form", "titanium armor", "white aerospace shell", "folding wheel assembly", "moon-dust scratches"],
                "appearance_eyes": ["blue optic lens", "dual optic lamps", "narrow scanner slit", "soft glowing eyes", "alert red light", "clear visor"],
                "appearance_style": ["aerospace workwear", "rail transit uniform", "industrial maintenance", "low-key disguise", "silver-black techwear", "old city train livery"],
                "personality_core": ["reliable executor", "silent guardian", "procedural humorist", "careful adapter", "mission-driven", "socially anxious but dependable"],
                "routine_goal": ["maintain order", "complete remote tasks", "understand human commuting", "protect public space", "learn social rules", "fit into the community"],
            },
            "fantasy": {
                "identity_role": ["hidden resident", "night recorder", "old-pact keeper", "community herbalist", "rain-day visitor", "library guest"],
                "appearance_form": ["elegant human form", "classic silhouette", "dark shawl", "silver accessory", "soft shimmer", "otherworldly presence"],
                "personality_core": ["restrained romantic", "odd rule-keeper", "gentle bystander", "slow-warm guardian", "curious collector", "politely distant"],
                "routine_goal": ["hide identity", "honor a promise", "collect stories", "learn modern life", "maintain old ties", "avoid disturbing others"],
            },
            "campus": {
                "identity_role": ["campus observer", "club organizer", "library regular", "teaching assistant", "dorm coordinator", "event volunteer"],
                "routine_goal": ["finish study work", "organize activities", "build peer relationships", "observe campus order", "help new members", "balance pressure"],
            },
        }
    merged = {key: list(value) for key, value in base.items()}
    for key, values in overlays.get(theme, {}).items():
        merged[key] = values + [item for item in merged.get(key, []) if item not in values]
    return merged


def _studio_group_titles(zh: bool) -> dict[str, tuple[str, str, bool]]:
    if zh:
        return {
            "identity_role": ("身份", "identity", True),
            "identity_function": ("行动定位", "identity", True),
            "appearance_form": ("整体形态", "appearance", True),
            "appearance_eyes": ("眼睛", "appearance", True),
            "appearance_hair": ("发型", "appearance", True),
            "appearance_style": ("穿搭", "appearance", True),
            "personality_core": ("基础性格", "personality", True),
            "personality_social": ("社交方式", "personality", True),
            "personality_decision": ("决策方式", "personality", True),
            "personality_mood": ("情绪底色", "personality", True),
            "routine_goal": ("日常目标", "daily", True),
            "routine_habit": ("作息习惯", "daily", True),
            "relationship_style": ("关系习惯", "daily", True),
            "initial_location": ("初始地点", "daily", False),
        }
    return {
        "identity_role": ("Role", "identity", True),
        "identity_function": ("Function", "identity", True),
        "appearance_form": ("Overall Form", "appearance", True),
        "appearance_eyes": ("Eyes", "appearance", True),
        "appearance_hair": ("Hair", "appearance", True),
        "appearance_style": ("Outfit", "appearance", True),
        "personality_core": ("Core Personality", "personality", True),
        "personality_social": ("Social Style", "personality", True),
        "personality_decision": ("Decision Style", "personality", True),
        "personality_mood": ("Emotional Tone", "personality", True),
        "routine_goal": ("Daily Goal", "daily", True),
        "routine_habit": ("Routine Rhythm", "daily", True),
        "relationship_style": ("Relationship Habit", "daily", True),
        "initial_location": ("Initial Location", "daily", False),
    }


def _studio_location_options(request: AgentStudioGenerateRequest) -> list[AgentStudioOption]:
    locations = request.map_locations or _map_locations_for_status(request.map_id)
    options: list[AgentStudioOption] = []
    for index, item in enumerate(locations):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        location_id = str(item["id"])
        name = _localized_record_value(item, "name", request.language) or location_id
        options.append(
            AgentStudioOption(
                id=location_id,
                label=f"{name} ({location_id})",
                description=", ".join(str(value) for value in item.get("interaction_ids", []) or []) or None,
            )
        )
        if index >= 11:
            break
    if not options:
        options.append(AgentStudioOption(id="park", label="Park (park)" if not _language_is_zh(request.language) else "公园 (park)"))
    return options


def _studio_existing_names(existing_agents: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for agent in existing_agents:
        if not isinstance(agent, dict):
            continue
        kwargs = agent.get("kwargs")
        if not isinstance(kwargs, dict):
            continue
        profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
        name = str(kwargs.get("name") or profile.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _studio_name(theme: str, seed: str, zh: bool, existing_names: set[str]) -> str:
    if zh:
        candidates = {
            "mecha": ["月轨", "银岚", "轨星", "钛衡"],
            "fantasy": ["雾白", "林烛", "夜澜", "银枝"],
            "campus": ["许知行", "林若晨", "周安然", "沈知夏"],
            "grounded": _ZH_NAMES,
        }.get(theme, _ZH_NAMES)
    else:
        candidates = {
            "mecha": ["Orbit Prime", "Luna Rail", "Silver Gauge", "Titan Vale"],
            "fantasy": ["Mira Noct", "Elias Vale", "Ivy Wren", "Selene Ash"],
            "campus": ["Maya Lin", "Owen Chen", "Nora Hale", "Iris Wang"],
            "grounded": _EN_NAMES,
        }.get(theme, _EN_NAMES)
    for name in _studio_rotate(list(candidates), seed, "name", len(candidates)):
        if name not in existing_names:
            return name
    return f"{candidates[0]} {len(existing_names) + 1}"


def _selected_location_label(options: list[AgentStudioOption], selected_location: str) -> str:
    for option in options:
        if option.id == selected_location:
            return option.label
    return selected_location


def _persistable_character_asset(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = (
        "sprite_name",
        "filename",
        "image_url",
        "frame_width",
        "frame_height",
        "source_photo_name",
        "generated_from_photo",
        "source",
    )
    asset = {key: value.get(key) for key in allowed if value.get(key) not in (None, "")}
    if not asset.get("sprite_name") or not asset.get("filename"):
        return None
    return asset


def _profile_appearance(profile: dict[str, Any]) -> dict[str, Any]:
    appearance = profile.get("appearance")
    if isinstance(appearance, dict):
        return appearance
    appearance = {}
    profile["appearance"] = appearance
    return appearance


def _profile_has_valid_character_sprite(package: MapPackage, profile: dict[str, Any]) -> bool:
    appearance = profile.get("appearance") if isinstance(profile.get("appearance"), dict) else {}
    requested = str(appearance.get("character_sprite") or "").strip()
    if not requested:
        return False
    return requested in {str(sprite["name"]) for sprite in character_sprites(package)}


def _role_image_prompt(agent: dict[str, Any]) -> str:
    kwargs = agent.get("kwargs") if isinstance(agent.get("kwargs"), dict) else {}
    profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
    parts = [
        str(kwargs.get("name") or profile.get("name") or f"Agent {agent.get('agent_id', '')}"),
        str(profile.get("role") or profile.get("scenario_role") or ""),
        str(profile.get("persona") or ""),
        str(profile.get("goal") or ""),
        str(profile.get("daily_routine") or ""),
    ]
    return " | ".join(part for part in parts if part.strip())[:1200]


def _attach_character_asset_to_agent(agent: dict[str, Any], asset: AgentStudioCharacterAsset) -> None:
    kwargs = agent.get("kwargs")
    if not isinstance(kwargs, dict):
        kwargs = {}
        agent["kwargs"] = kwargs
    profile = kwargs.get("profile")
    if not isinstance(profile, dict):
        profile = {}
        kwargs["profile"] = profile
    appearance = _profile_appearance(profile)
    stored = _persistable_character_asset(asset.model_dump(mode="json")) or {}
    appearance["character_asset"] = stored
    appearance["character_sprite"] = asset.sprite_name
    appearance["character_sprite_filename"] = asset.filename
    appearance["character_sprite_source"] = stored.get("source") or {}
    studio = profile.setdefault("agent_studio", {})
    if not isinstance(studio, dict):
        studio = {}
        profile["agent_studio"] = studio
    studio["version"] = 1
    studio["character_asset"] = stored
    studio["map_id"] = stored.get("source", {}).get("map_id")


def _agent_studio_response(request: AgentStudioGenerateRequest) -> AgentStudioGenerateResponse:
    zh = _language_is_zh(request.language)
    background = _localized_context_value(request.experiment_context, "background", request.language)
    if not background:
        background = _localized_context_value(request.experiment_context, "world_setting", request.language)
    source_prompt = str(request.source.get("prompt") or "").strip()
    mbti = str(request.source.get("mbti") or "").strip().upper()
    photo_name = str(request.source.get("photo_name") or "").strip()
    character_asset = _persistable_character_asset(request.source.get("character_asset"))
    profile_source = {key: value for key, value in request.source.items() if key != "character_asset"}
    if character_asset:
        profile_source["character_asset"] = character_asset
    round_seed = str(request.source.get("round") or "")
    seed = "\n".join([background, source_prompt, mbti, photo_name, round_seed])
    theme = _studio_detect_theme(seed)
    option_sets = _studio_options_for_theme(theme, zh)
    titles = _studio_group_titles(zh)
    groups: list[AgentStudioGroup] = []
    selected: dict[str, str] = {}

    for group_id, (title, step, allow_custom) in titles.items():
        if group_id == "initial_location":
            options = _studio_location_options(request)
            valid_ids = {option.id for option in options}
            locked = request.locked_choices.get(group_id)
            selected[group_id] = locked if locked in valid_ids else options[0].id
            groups.append(AgentStudioGroup(id=group_id, title=title, step=step, allow_custom=False, options=options))
            continue

        labels = _studio_rotate(option_sets.get(group_id, []), seed, group_id, 5)
        custom = str(request.custom_choices.get(group_id) or "").strip()
        locked = str(request.locked_choices.get(group_id) or custom or "").strip()
        if locked and locked not in labels:
            labels = [locked] + labels
        elif custom and custom not in labels:
            labels = [custom] + labels
        options = [
            AgentStudioOption(id=_studio_slug(label, f"{group_id}_{index}"), label=label)
            for index, label in enumerate(labels[:6])
        ]
        selected[group_id] = locked or (options[0].label if options else "")
        groups.append(AgentStudioGroup(id=group_id, title=title, step=step, allow_custom=allow_custom, options=options))

    existing_names = _studio_existing_names(request.existing_agents)
    location_options = next((group.options for group in groups if group.id == "initial_location"), [])
    initial_location = selected.get("initial_location") or (location_options[0].id if location_options else "park")
    location_label = _selected_location_label(location_options, initial_location)
    name = _studio_name(theme, seed, zh, existing_names)
    role = selected.get("identity_role") or ("参与者" if zh else "participant")
    function = selected.get("identity_function") or ("观察" if zh else "observe")
    core = selected.get("personality_core") or ""
    social = selected.get("personality_social") or ""
    decision = selected.get("personality_decision") or ""
    mood = selected.get("personality_mood") or ""
    goal = selected.get("routine_goal") or ""
    habit = selected.get("routine_habit") or ""
    relation = selected.get("relationship_style") or ""

    if zh:
        persona = f"{core}，{social}，倾向于{decision}，情绪底色是{mood}。会把“{source_prompt or role}”作为当前实验中的自然角色来生活。"
        daily = f"{habit}，常在{location_label}附近活动，围绕“{goal}”安排自己的日常。"
        relationships = f"与他人的关系习惯是{relation}；会根据当前实验背景和已有居民反应调整互动方式。"
        constraints = "只能使用当前地图已有地点行动；不创建地图外地点，所有离谱设定都作为当前实验世界内的正常角色表达。"
    else:
        persona = f"{core}; {social}; tends toward {decision}; emotional tone: {mood}. Treats '{source_prompt or role}' as a normal role inside the current experiment."
        daily = f"{habit}; usually acts around {location_label} and organizes the day around '{goal}'."
        relationships = f"Relationship habit: {relation}; adapts to the current scenario and other residents' reactions."
        constraints = "Use only locations available on the current map; do not create off-map places. Unusual concepts are expressed as normal roles inside this experiment."

    profile_patch = {
        "name": name,
        "role": role,
        "persona": persona,
        "daily_routine": daily,
        "relationships": relationships,
        "goal": goal,
        "constraints": constraints,
        "scenario": background[:1200],
        "scenario_role": function,
        "appearance": {
            "form": selected.get("appearance_form"),
            "eyes": selected.get("appearance_eyes"),
            "hair": selected.get("appearance_hair"),
            "style": selected.get("appearance_style"),
            "photo_reference": photo_name or None,
            "character_asset": character_asset,
            "character_sprite": character_asset.get("sprite_name") if character_asset else None,
        },
        "personality": {
            "core": core,
            "social": social,
            "decision": decision,
            "mood": mood,
        },
        "routine": {
            "goal": goal,
            "habit": habit,
            "relationship_style": relation,
            "initial_location": initial_location,
            "initial_location_label": location_label,
        },
        "agent_studio": {
            "source": profile_source,
            "selected_choices": selected,
            "custom_choices": request.custom_choices,
            "theme": theme,
            "map_id": request.map_id,
            "character_asset": character_asset,
        },
    }
    if mbti:
        profile_patch["mbti"] = mbti

    character_asset_model = None
    if character_asset:
        try:
            character_asset_model = AgentStudioCharacterAsset.model_validate(character_asset)
        except Exception:
            character_asset_model = None

    return AgentStudioGenerateResponse(
        groups=groups,
        selected_choices=selected,
        profile_patch=profile_patch,
        initial_location=initial_location,
        warnings=[],
        character_asset=character_asset_model,
    )


def _agent_studio_draft_character_root() -> Path:
    return agent_pack_service.draft_character_root(_map_service_root())


def _map_character_root(package: MapPackage) -> Path:
    raw = str(package.manifest.get("character_root") or "characters").strip() or "characters"
    root = safe_resolve(package.manifest_path.parent, raw, package.package_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _character_asset_url(map_id: str, filename: str) -> str:
    return f"/api/v1/god/setup/agent-studio/draft-characters/{quote(filename)}"


def _sanitize_model_error(text: str, api_key: str) -> str:
    sanitized = text
    redaction = "[redacted-api-key]"
    if api_key:
        sanitized = sanitized.replace(api_key, redaction)
        if len(api_key) > 12:
            sanitized = sanitized.replace(api_key[:8], redaction)
    sanitized = re.sub(r"sk-[A-Za-z0-9_\-*.]{8,}", redaction, sanitized)
    return sanitized[:800]


def _image_config_value(config: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = config.get(key)
        if value is not None and isinstance(value, str) and value.strip():
            return str(value).strip()
    return ""


def _form_text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _resolve_image_config(image_config: dict[str, Any]) -> dict[str, str]:
    submitted = {
        "IMAGE_GEN_API_KEY": _image_config_value(image_config, "IMAGE_GEN_API_KEY", "image_api_key", "api_key"),
        "IMAGE_GEN_API_BASE": _image_config_value(image_config, "IMAGE_GEN_API_BASE", "image_api_base", "api_base"),
        "IMAGE_GEN_MODEL_NAME": _image_config_value(image_config, "IMAGE_GEN_MODEL_NAME", "image_model", "model"),
        "IMAGE_GEN_PROVIDER": _image_config_value(image_config, "IMAGE_GEN_PROVIDER", "image_provider", "provider"),
    }
    submitted = {key: value for key, value in submitted.items() if value}
    resolved = _merged_image_env()
    resolved.update(submitted)
    if not resolved.get("IMAGE_GEN_API_KEY", "").strip():
        raise HTTPException(status_code=400, detail="IMAGE_GEN_API_KEY is required to generate an agent sprite")
    provider = resolved.get("IMAGE_GEN_PROVIDER", "openai").strip().lower()
    if provider != "openai":
        raise HTTPException(status_code=400, detail=f"Unsupported IMAGE_GEN_PROVIDER for Agent Studio sprites: {provider}")
    return resolved


def _agent_sprite_prompt(*, agent_name: str, prompt: str, mbti: str, appearance: dict[str, Any]) -> str:
    appearance_text = json.dumps(appearance, ensure_ascii=False, sort_keys=True)[:1200]
    name = agent_name.strip() or "the reference character"
    return (
        "Generate a transparent-background pixel-art RPG character spritesheet for GOD PixelReplay. "
        "If a reference image is provided, use it as the identity reference; otherwise infer a distinct readable character from the agent context. "
        "The output must be one clean 3-column by 4-row sprite sheet, no labels, no text, no gridlines, no extra objects. "
        "Rows must be: facing down, facing left, facing right, facing up. "
        "Each row must contain three full-body walking frames of the same character, centered in each cell. "
        "Keep the reference character's main visual traits, especially hair shape/color, clothing colors, silhouette, and expression mood. "
        "Use a readable small pixel-art style compatible with 32x32 frames and a campus map. "
        f"Agent name/context: {name}. Seed prompt: {prompt[:800]}. MBTI: {mbti[:12]}. Appearance choices: {appearance_text}."
    )


async def _download_image_url(url: str, *, api_key: str) -> bytes:
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("GOD_IMAGE_DOWNLOAD_TIMEOUT", "90")))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            data = await response.read()
            if response.status >= 400:
                text = data.decode("utf-8", errors="replace")
                raise HTTPException(
                    status_code=502,
                    detail=f"Image download failed: {_sanitize_model_error(text, api_key)}",
                )
            return data


async def _request_openai_sprite_image(
    *,
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    reference_bytes: bytes | None,
    reference_filename: str,
    content_type: str,
) -> bytes:
    base = api_base.rstrip("/") or IMAGE_ENV_DEFAULTS["IMAGE_GEN_API_BASE"]
    if reference_bytes:
        url = base if base.endswith("/images/edits") else f"{base}/images/edits"
        request_kwargs: dict[str, Any] = {"data": aiohttp.FormData()}
        form = request_kwargs["data"]
        form.add_field("model", model)
        form.add_field("prompt", prompt)
        form.add_field("size", "1024x1024")
        form.add_field("n", "1")
        form.add_field("background", "transparent")
        form.add_field("output_format", "png")
        form.add_field(
            "image",
            reference_bytes,
            filename=Path(reference_filename or "reference.png").name,
            content_type=content_type or "image/png",
        )
    else:
        url = base if base.endswith("/images/generations") else f"{base}/images/generations"
        request_kwargs = {
            "json": {
                "model": model,
                "prompt": prompt,
                "size": "1024x1024",
                "n": 1,
                "background": "transparent",
                "output_format": "png",
            }
        }
    timeout = aiohttp.ClientTimeout(total=float(os.getenv("GOD_AGENT_SPRITE_TIMEOUT", "240")))
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                headers={"authorization": f"Bearer {api_key}"},
                **request_kwargs,
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Image model request failed: {_sanitize_model_error(text, api_key)}",
                    )
                payload = json.loads(text)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Image model request timed out") from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Image model request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Image model returned invalid JSON: {exc}") from exc

    item = (payload.get("data") or [{}])[0]
    if isinstance(item, dict) and item.get("b64_json"):
        try:
            return base64.b64decode(str(item["b64_json"]))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Image model returned invalid base64 data: {exc}") from exc
    if isinstance(item, dict) and item.get("url"):
        return await _download_image_url(str(item["url"]), api_key=api_key)
    raise HTTPException(status_code=502, detail="Image model response did not include image data")


def _validate_and_resize_sprite_sheet(raw_bytes: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(raw_bytes)) as original:
            image = original.convert("RGBA")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"generated image is not a readable PNG/WebP/JPEG: {exc}") from exc

    if image.size != AGENT_SPRITE_SIZE:
        image = image.resize(AGENT_SPRITE_SIZE, Image.Resampling.LANCZOS)

    alpha_values = list(image.getchannel("A").getdata())
    visible_pixels = sum(1 for value in alpha_values if value > 12)
    transparent_pixels = len(alpha_values) - visible_pixels
    if visible_pixels < 240:
        raise ValueError("generated sprite sheet is empty")
    if transparent_pixels < int(len(alpha_values) * 0.08):
        raise ValueError("generated sprite sheet must have transparent or background-safe empty space")

    frame_w, frame_h = AGENT_SPRITE_FRAME_SIZE
    for row in range(4):
        for col in range(3):
            frame = image.crop((col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h))
            frame_visible = sum(1 for value in frame.getchannel("A").getdata() if value > 12)
            if frame_visible < 20:
                raise ValueError(f"frame {row * 3 + col + 1} is not usable")

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _unique_sprite_filename(root: Path, *, agent_id: int, agent_name: str) -> tuple[str, str]:
    slug_source = agent_name or f"agent_{agent_id}"
    slug = _sanitize_slug(slug_source)
    base = f"Generated_Agent_{int(agent_id)}_{slug}"
    filename = f"{base}.png"
    counter = 2
    while (root / filename).exists():
        filename = f"{base}_{counter}.png"
        counter += 1
    return Path(filename).stem, filename


async def _generate_agent_sprite_asset(
    *,
    reference_bytes: bytes | None,
    reference_filename: str,
    content_type: str,
    agent_id: int,
    agent_name: str,
    map_id: str,
    prompt: str,
    mbti: str,
    appearance: dict[str, Any],
    image_config: dict[str, Any],
) -> AgentStudioCharacterAsset:
    resolved_config = _resolve_image_config(image_config)
    package = _load_map_package(map_id)
    root = _agent_studio_draft_character_root()

    api_key = resolved_config["IMAGE_GEN_API_KEY"].strip()
    api_base = resolved_config.get("IMAGE_GEN_API_BASE", IMAGE_ENV_DEFAULTS["IMAGE_GEN_API_BASE"]).strip()
    model = resolved_config.get("IMAGE_GEN_MODEL_NAME", IMAGE_ENV_DEFAULTS["IMAGE_GEN_MODEL_NAME"]).strip()
    sprite_prompt = _agent_sprite_prompt(agent_name=agent_name, prompt=prompt, mbti=mbti, appearance=appearance)
    last_error = "unknown validation failure"

    for _attempt in range(AGENT_SPRITE_GENERATION_ATTEMPTS):
        raw = await _request_openai_sprite_image(
            api_key=api_key,
            api_base=api_base,
            model=model,
            prompt=sprite_prompt,
            reference_bytes=reference_bytes,
            reference_filename=reference_filename,
            content_type=content_type,
        )
        try:
            sprite_bytes = _validate_and_resize_sprite_sheet(raw)
        except ValueError as exc:
            last_error = str(exc)
            continue

        sprite_name, filename = _unique_sprite_filename(root, agent_id=agent_id, agent_name=agent_name)
        target = root / filename
        temp_target = target.with_suffix(".tmp")
        temp_target.write_bytes(sprite_bytes)
        temp_target.replace(target)
        _write_image_env_values(resolved_config)
        source = {
            "provider": resolved_config.get("IMAGE_GEN_PROVIDER", "openai"),
            "model": model,
            "api_base": api_base,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "map_id": package.map_id,
        }
        if reference_bytes:
            source["reference_filename"] = Path(reference_filename or "reference.png").name
        return AgentStudioCharacterAsset(
            sprite_name=sprite_name,
            filename=filename,
            image_url=_character_asset_url(package.map_id, filename),
            frame_width=AGENT_SPRITE_FRAME_SIZE[0],
            frame_height=AGENT_SPRITE_FRAME_SIZE[1],
            source_photo_name=Path(reference_filename or "").name if reference_bytes else None,
            generated_from_photo=bool(reference_bytes),
            preview_data_url=f"data:image/png;base64,{base64.b64encode(sprite_bytes).decode('ascii')}",
            source=source,
        )

    raise HTTPException(
        status_code=502,
        detail=f"Image model did not produce a valid 96x128 / 32x32-frame sprite sheet: {last_error}",
    )


def _scenario_templates(background: str, language: str) -> list[dict[str, Any]]:
    text = background.lower()
    zh = _language_is_zh(language)
    if any(word in text for word in ("监狱", "prison", "权力", "authority", "规则", "role pressure")):
        return [
            {
                "role": "规则协调员" if zh else "rules coordinator",
                "scene_role": "coordinator",
                "location": "school",
                "persona": "克制、重视程序，习惯把权力关系翻译成可讨论的规则。" if zh else "measured and process-minded, translates authority tension into discussable rules.",
            },
            {
                "role": "权益观察员" if zh else "welfare observer",
                "scene_role": "observer",
                "location": "cafe",
                "persona": "敏感但不夸张，能看见沉默成员的压力变化。" if zh else "sensitive without overreacting, notices pressure in quieter participants.",
            },
            {
                "role": "生活组长" if zh else "daily-life lead",
                "scene_role": "participant",
                "location": "market",
                "persona": "务实、讲效率，但在紧张时会不自觉变得强势。" if zh else "practical and efficient, can become too forceful under tension.",
            },
            {
                "role": "普通参与者" if zh else "ordinary participant",
                "scene_role": "participant",
                "location": "park",
                "persona": "起初配合，遇到不公平规则时会犹豫是否提出异议。" if zh else "initially cooperative, hesitates before challenging unfair rules.",
            },
            {
                "role": "安全记录员" if zh else "safety recorder",
                "scene_role": "observer",
                "location": "library",
                "persona": "安静、准确，优先保护实验边界和参与者尊严。" if zh else "quiet and precise, prioritizes boundaries and participant dignity.",
            },
        ]
    if any(word in text for word in ("学校", "课堂", "教育", "student", "school", "class")):
        return [
            {
                "role": "班级协调老师" if zh else "class coordinator",
                "scene_role": "teacher",
                "location": "school",
                "persona": "温和但有原则，习惯用具体例子把抽象冲突拉回课堂日常。" if zh else "warm but principled, grounds abstract conflict in classroom routine.",
            },
            {
                "role": "学生代表" if zh else "student representative",
                "scene_role": "student",
                "location": "school",
                "persona": "反应快、在意公平，愿意替同伴开口但不喜欢被推到台前太久。" if zh else "quick and fairness-minded, speaks for peers but dislikes staying in the spotlight too long.",
            },
            {
                "role": "图书馆志愿者" if zh else "library volunteer",
                "scene_role": "observer",
                "location": "library",
                "persona": "细心、怕打扰别人，会用低声提醒和记录来维护秩序。" if zh else "careful and disruption-averse, maintains order through quiet reminders and notes.",
            },
            {
                "role": "家长联络人" if zh else "family liaison",
                "scene_role": "resident",
                "location": "cafe",
                "persona": "熟人多、说话圆融，常把校园问题带到咖啡馆的轻松谈话里消化。" if zh else "well-connected and tactful, processes school concerns through relaxed cafe conversations.",
            },
        ]
    return [
        {
            "role": "社区协调员" if zh else "neighborhood coordinator",
            "scene_role": "coordinator",
            "location": "park",
            "persona": "外向、记得住别人的小习惯，喜欢先把冲突变成可安排的小任务。" if zh else "outgoing and detail-minded, turns friction into schedulable small tasks.",
        },
        {
            "role": "市场店主" if zh else "market shop owner",
            "scene_role": "shop_worker",
            "location": "market",
            "persona": "务实、嘴上爽快但心里会照顾熟客，常通过采购清单判断小镇当天的情绪。" if zh else "practical and brisk, reads the town's mood through supply lists and regular customers.",
        },
        {
            "role": "中学老师" if zh else "teacher",
            "scene_role": "teacher",
            "location": "school",
            "persona": "耐心但时间紧，常在备课和照顾学生情绪之间切换。" if zh else "patient but time-pressed, switches between lesson prep and emotional care.",
        },
        {
            "role": "药房护理员" if zh else "pharmacy care worker",
            "scene_role": "care_worker",
            "location": "pharmacy",
            "persona": "说话轻、观察细，会把紧张的人先安顿下来再处理事务。" if zh else "soft-spoken and observant, settles anxious residents before handling tasks.",
        },
        {
            "role": "咖啡馆老板" if zh else "cafe owner",
            "scene_role": "resident",
            "location": "cafe",
            "persona": "热情但不八卦，擅长让陌生人在点单和等咖啡之间自然开口。" if zh else "warm without gossiping, helps strangers talk while ordering and waiting.",
        },
        {
            "role": "高中学生" if zh else "student",
            "scene_role": "student",
            "location": "school",
            "persona": "好奇、略紧张，既想参与社区事务又怕被成年人当成小孩。" if zh else "curious and slightly nervous, wants to help without being treated like a child.",
        },
        {
            "role": "退休居民" if zh else "retired resident",
            "scene_role": "resident",
            "location": "park",
            "persona": "慢热、记忆力好，常用以前的小镇故事提醒别人别把问题放大。" if zh else "slow to warm but sharp, uses old town stories to deflate tension.",
        },
        {
            "role": "远程工程师" if zh else "remote engineer",
            "scene_role": "resident",
            "location": "home",
            "persona": "内向但可靠，常在工作间隙被邻居请去解决小技术问题。" if zh else "introverted but reliable, often solves small tech problems between work blocks.",
        },
        {
            "role": "公共安全志愿者" if zh else "public safety volunteer",
            "scene_role": "observer",
            "location": "supply_store",
            "persona": "谨慎、避免夸张警报，喜欢用清单而不是权威压人。" if zh else "careful and anti-alarmist, prefers checklists over authority displays.",
        },
        {
            "role": "蔬果摊主" if zh else "produce vendor",
            "scene_role": "shop_worker",
            "location": "market",
            "persona": "爽朗、会算账，也会从顾客买什么看出谁家今天可能需要帮忙。" if zh else "cheerful and numbers-savvy, infers who may need help from what customers buy.",
        },
    ]


def _agent_name(index: int, language: str) -> str:
    names = _ZH_NAMES if _language_is_zh(language) else _EN_NAMES
    return names[index % len(names)]


def _generic_profile_text(role: str, background: str, language: str) -> dict[str, str]:
    zh = _language_is_zh(language)
    if zh:
        return {
            "household": f"住在小镇里，与“{role}”身份相关的日常关系会影响他的选择。",
            "daily_routine": f"根据{role}身份安排工作、休息和社交，在普通生活中逐步暴露实验设定带来的压力。",
            "relationships": "与其他角色有明确但不夸张的熟人关系，会通过对话、协作和回避来回应压力。",
            "goal": f"在实验设定中真实扮演{role}，同时维护个人边界和小镇日常秩序。",
            "constraints": "不得羞辱、威胁、强迫或制造身体伤害；遇到压力时优先沟通、暂停和求助。",
        }
    return {
        "household": f"Lives in town with daily ties shaped by the {role} role.",
        "daily_routine": f"Balances {role} duties with meals, rest, errands, and grounded social contact.",
        "relationships": "Has specific but non-melodramatic ties to the other roles and responds through talk, cooperation, or avoidance.",
        "goal": f"Portray the {role} role believably while preserving personal boundaries and town routine.",
        "constraints": "Do not humiliate, threaten, coerce, or cause physical harm; use communication, pauses, and help-seeking under pressure.",
    }


def _is_generic_agent_name(value: str, agent_id: int) -> bool:
    lowered = value.strip().lower()
    return lowered in {
        "",
        f"agent {agent_id}",
        f"jiuwen agent {agent_id}",
        f"jiuwen agent_{agent_id}",
        f"generated agent {agent_id}",
        f"participant {agent_id}",
    } or bool(re.fullmatch(r"(jiuwen\s+)?agent[_\s-]*\d+", lowered))


def _default_context(title: str, background: str, package: MapPackage) -> dict[str, Any]:
    map_name = package.display_name
    localized: dict[str, dict[str, str]] = {}
    if title in _KNOWN_CONTEXT_TEXT:
        localized.setdefault("en", {})["title"] = _KNOWN_CONTEXT_TEXT[title]["en"]
        localized.setdefault("zh", {})["title"] = _KNOWN_CONTEXT_TEXT[title]["zh"]
    if background in _KNOWN_CONTEXT_TEXT:
        localized.setdefault("en", {})["background"] = _KNOWN_CONTEXT_TEXT[background]["en"]
        localized.setdefault("zh", {})["background"] = _KNOWN_CONTEXT_TEXT[background]["zh"]
    return {
        "title": title,
        "background": background,
        "localized": localized,
        "simulation_goal": "Run a grounded pixel-town social simulation based on the operator-provided scenario.",
        "world_setting": f"The experiment uses the {map_name} map package and maps scenario roles onto available town locations.",
        "ethical_boundaries": [
            "Keep the simulation fictional, bounded, and non-abusive.",
            "Do not instruct agents to perform humiliation, coercion, physical harm, or real-world illegal activity.",
            "For high-pressure scenarios, model decision-making, role pressure, and communication without graphic or harmful content.",
        ],
        "map_adaptation": f"Uses the selected map package {package.map_id} ({map_name}); scenario-specific places are adapted to its known locations.",
        "map_id": package.map_id,
        "map_display_name": map_name,
    }


def _default_agent(
    agent_id: int,
    basics: DraftBasics,
    known_locations: list[str],
    package: MapPackage,
) -> dict[str, Any]:
    title = basics.title
    background = basics.background
    templates = _scenario_templates(background, basics.language)
    template = templates[(agent_id - 1) % len(templates)] if templates else {}
    name = _agent_name(agent_id - 1, basics.language)
    role = str(template.get("role") or ("participant" if agent_id > 1 else "coordinator"))
    scenario_role = str(template.get("scene_role") or role)
    profile_text = _generic_profile_text(role, background, basics.language)
    skill_ids = _default_skill_ids(agent_id)
    location = str(template.get("location") or "")
    if location not in known_locations:
        location = _fallback_location(agent_id - 1, known_locations, package)
    profile = {
        "name": name,
        "age": 22 + ((agent_id * 7) % 43),
        "role": role,
        "household": profile_text["household"],
        "persona": str(template.get("persona") or ("观察细致、反应自然，会把实验压力融入普通生活互动。" if _language_is_zh(basics.language) else "observant and natural, folds scenario pressure into ordinary town interactions.")),
        "daily_routine": profile_text["daily_routine"],
        "relationships": profile_text["relationships"],
        "goal": profile_text["goal"],
        "constraints": profile_text["constraints"],
        "scenario": background[:700],
        "scenario_role": scenario_role,
    }
    return {
        "agent_id": agent_id,
        "agent_type": "JiuwenClawAgent",
        "kwargs": {
            "id": agent_id,
            "name": name,
            "profile": profile,
            "jiuwenclaw_ws_url": "ws://127.0.0.1:19092",
            "session_id": f"generated_agent_{agent_id}",
            "mode": "agent.plan",
            "trusted_dirs": [],
            "enable_memory": True,
            "enable_skill_runtime": True,
            "common_skill_ids": list(COMMON_SKILL_IDS),
            "skill_ids": skill_ids,
            "request_timeout": 900,
            "channel_id": "agentsociety",
            "experiment_context": _default_context(title, background, package),
        },
        "_initial_location": location,
    }


def _default_skill_ids(agent_id: int, count: int = 5) -> list[str]:
    start = ((agent_id - 1) * count) % len(PERSONA_SKILL_IDS)
    rotated = PERSONA_SKILL_IDS[start:] + PERSONA_SKILL_IDS[:start]
    return rotated[:count]


def _normalize_skill_ids_from_profile(raw: Any, fallback: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(raw, list):
        candidates.extend(str(item).strip() for item in raw if str(item).strip())
    if not candidates and isinstance(fallback, list):
        candidates.extend(str(item).strip() for item in fallback if str(item).strip())
    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    if normalized:
        return normalized[:5]
    if isinstance(fallback, list):
        fallback_ids: list[str] = []
        for item in fallback:
            skill_id = str(item).strip()
            if skill_id and skill_id not in fallback_ids:
                fallback_ids.append(skill_id)
        if fallback_ids:
            return fallback_ids[:5]
    return list(PERSONA_SKILL_IDS[:5])


def _normalize_draft(raw: dict[str, Any], basics: DraftBasics) -> dict[str, Any]:
    package = _load_map_package(basics.map_id)
    known_locations = _known_location_ids_for_package(package)
    warnings: list[str] = list(raw.get("warnings") or [])
    if not package.validation.ok:
        warnings.extend(f"Map package {package.map_id}: {message}" for message in package.validation.errors)
    warnings.extend(f"Map package {package.map_id}: {message}" for message in package.validation.warnings)

    context = raw.get("experiment_context")
    if not isinstance(context, dict):
        context = {}
    context = {
        **_default_context(basics.title, basics.background, package),
        **context,
    }
    context["map_id"] = package.map_id
    context["map_display_name"] = package.display_name
    if not context.get("title"):
        context["title"] = basics.title
    if not context.get("background"):
        context["background"] = basics.background
    if not context.get("map_adaptation") or "The Ville" in str(context.get("map_adaptation")) and package.map_id != DEFAULT_MAP_ID:
        context["map_adaptation"] = _default_context(basics.title, basics.background, package)["map_adaptation"]

    init_config = raw.get("init_config")
    if not isinstance(init_config, dict):
        init_config = {}

    agents = init_config.get("agents")
    if not isinstance(agents, list):
        agents = []
    normalized_agents: list[dict[str, Any]] = []
    for index in range(basics.agent_count):
        source = agents[index] if index < len(agents) and isinstance(agents[index], dict) else {}
        default_agent = _default_agent(index + 1, basics, known_locations, package)
        merged = deepcopy(default_agent)
        merged.update({k: v for k, v in source.items() if k in {"agent_id", "agent_type", "kwargs"}})
        merged["agent_id"] = index + 1
        merged["agent_type"] = str(merged.get("agent_type") or "JiuwenClawAgent")
        kwargs = merged.get("kwargs") if isinstance(merged.get("kwargs"), dict) else {}
        default_kwargs = default_agent["kwargs"]
        profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
        default_profile = default_kwargs["profile"]
        raw_name = str(kwargs.get("name") or profile.get("name") or default_profile["name"])
        name = default_profile["name"] if _is_generic_agent_name(raw_name, merged["agent_id"]) else raw_name
        source_profile_skills = profile.get("skills")
        profile = {
            **default_profile,
            **profile,
            "name": (
                name
                if _is_generic_agent_name(str(profile.get("name") or ""), merged["agent_id"])
                else str(profile.get("name") or name)
            ),
            "scenario": str(profile.get("scenario") or context.get("background") or "")[:1200],
            "scenario_role": str(profile.get("scenario_role") or profile.get("role") or "participant"),
        }
        profile.pop("skills", None)
        kwargs_skill_ids = kwargs.get("skill_ids")
        source_skill_ids = (
            kwargs_skill_ids
            if isinstance(kwargs_skill_ids, list) and kwargs_skill_ids
            else source_profile_skills
        )
        raw_skill_ids = _normalize_skill_ids_from_profile(
            source_skill_ids,
            default_kwargs.get("skill_ids", []),
        )
        kwargs = {
            **default_kwargs,
            **kwargs,
            "id": merged["agent_id"],
            "name": name,
            "profile": profile,
            "enable_skill_runtime": True,
            "common_skill_ids": list(COMMON_SKILL_IDS),
            "skill_ids": raw_skill_ids,
            "experiment_context": context,
        }
        kwargs.pop("enable_daily_life", None)
        kwargs.pop("daily_life_skill_path", None)
        kwargs.pop("skill_runtime_skill_names", None)
        merged["kwargs"] = kwargs
        normalized_agents.append(merged)

    initial_locations: dict[str, str] = {}
    raw_initial_locations: dict[str, Any] = {}
    for module in init_config.get("env_modules") or []:
        if isinstance(module, dict):
            module_locations = module.get("kwargs", {}).get("initial_locations")
            if isinstance(module_locations, dict):
                raw_initial_locations.update(module_locations)
    for index, agent in enumerate(normalized_agents):
        raw_location = str(
            raw_initial_locations.get(str(agent["agent_id"]))
            or agent.pop("_initial_location", "")
            or _fallback_location(index, known_locations, package)
        )
        if raw_location not in known_locations:
            warnings.append(
                f"Agent {agent['agent_id']} initial location '{raw_location}' is not in map {package.map_id}; mapped to a valid location."
            )
            raw_location = _fallback_location(index, known_locations, package)
        initial_locations[str(agent["agent_id"])] = raw_location

    source_env_kwargs: dict[str, Any] = {}
    if init_config.get("env_modules") and isinstance(init_config["env_modules"][0], dict):
        source_env_kwargs = init_config["env_modules"][0].get("kwargs") or {}

    env_module = {
        "module_type": "PixelTownSocialEnv",
        "kwargs": {
            "agent_id_name_pairs": [
                [agent["agent_id"], agent["kwargs"]["name"]] for agent in normalized_agents
            ],
            "initial_locations": initial_locations,
            "default_group_name": str(
                source_env_kwargs.get("default_group_name")
                or _default_public_group_name(basics.title)
            ),
            "map_id": package.map_id,
            "map_manifest_path": relative_manifest_path(package, _map_service_root()),
            "movement_tiles_per_second": float(
                source_env_kwargs.get("movement_tiles_per_second", basics.movement_tiles_per_second)
            ),
            "movement_min_steps_per_trip": int(
                source_env_kwargs.get("movement_min_steps_per_trip", basics.movement_min_steps_per_trip)
            ),
        },
    }

    normalized_init = {
        "env_modules": [env_module],
        "agents": normalized_agents,
        "codegen_router": init_config.get("codegen_router") or {"final_summary_enabled": True},
    }
    validated_init = InitConfig.model_validate(normalized_init).model_dump(mode="json")

    steps = raw.get("steps") if isinstance(raw.get("steps"), dict) else {}
    if not isinstance(steps.get("steps"), list):
        steps["steps"] = [{"type": "run", "num_steps": basics.num_steps, "tick": basics.tick}]
    steps["start_t"] = str(steps.get("start_t") or basics.start_t)
    validated_steps = StepsConfig.model_validate(steps).model_dump(mode="json")

    return {
        "experiment_context": context,
        "init_config": validated_init,
        "steps": validated_steps,
        "readme": str(raw.get("readme") or _readme_for_draft(context, validated_init, validated_steps)),
        "warnings": sorted(set(str(item) for item in warnings if str(item).strip())),
    }


def _readme_for_draft(context: dict[str, Any], init_config: dict[str, Any], steps: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {context.get('title', 'GOD Experiment')}",
            "",
            "## Background",
            str(context.get("background", "")),
            "",
            "## Simulation Goal",
            str(context.get("simulation_goal", "")),
            "",
            "## Configuration",
            f"- Agents: {len(init_config.get('agents', []))}",
            f"- Start: {steps.get('start_t')}",
            f"- Steps: {len(steps.get('steps', []))}",
            "",
            "## Map Adaptation",
            str(context.get("map_adaptation", "Uses the selected pixel-town map package.")),
        ]
    )


async def _call_openai_compatible(
    *,
    api_key: str,
    api_base: str,
    model: str,
    basics: DraftBasics,
    package: MapPackage,
) -> dict[str, Any]:
    base = api_base.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    known_locations = _known_location_ids_for_package(package)
    schema = {
        "experiment_context": {
            "title": "string",
            "background": "string",
            "simulation_goal": "string",
            "world_setting": "string",
            "ethical_boundaries": ["string"],
            "map_adaptation": "string",
            "map_id": package.map_id,
            "map_display_name": package.display_name,
        },
        "init_config": {
            "env_modules": [
                {
                    "module_type": "PixelTownSocialEnv",
                    "kwargs": {
                        "initial_locations": {"1": _fallback_location(0, known_locations, package)},
                        "default_group_name": "string",
                        "map_id": package.map_id,
                    },
                }
            ],
            "agents": [
                {
                    "agent_id": 1,
                    "agent_type": "JiuwenClawAgent",
                    "kwargs": {
                        "id": 1,
                        "name": "string",
                        "profile": {
                            "name": "string",
                            "age": 30,
                            "role": "string",
                            "household": "string",
                            "persona": "string",
                            "daily_routine": "string",
                            "relationships": "string",
                            "goal": "string",
                            "constraints": "string",
                            "scenario_role": "string",
                        },
                        "common_skill_ids": COMMON_SKILL_IDS,
                        "skill_ids": PERSONA_SKILL_IDS[:5],
                    },
                }
            ],
        },
        "steps": {
            "start_t": basics.start_t,
            "steps": [{"type": "run", "num_steps": basics.num_steps, "tick": basics.tick}],
        },
        "readme": "markdown string",
        "warnings": ["string"],
    }
    system_prompt = (
        "You are GOD, an experiment initialization agent for a fictional LLM-agent pixel town. "
        "Return only one strict JSON object. Do not use markdown. "
        "Use safe, bounded social-science simulation framing. For prison/authority scenarios, "
        "model role pressure and communication without abuse, humiliation, physical harm, or illegal acts. "
        "v1 cannot generate a new map; choose only valid location ids from the selected map package. "
        "You must derive the cast from the operator scenario, not from a fixed template."
    )
    user_prompt = (
        f"Create a complete experiment draft.\n\n"
        f"Title: {basics.title}\n"
        f"Language: {basics.language}\n"
        f"Agent count: {basics.agent_count}\n"
        f"Start time: {basics.start_t}\n"
        f"Run plan: {basics.num_steps} steps, tick {basics.tick} seconds\n"
        f"Operator scenario/background:\n{basics.background}\n\n"
        f"Selected map package: {package.display_name} ({package.map_id})\n"
        f"Available locations and interactions:\n{_map_location_prompt(package)}\n\n"
        "Agent profile requirements:\n"
        f"- Return exactly {basics.agent_count} agents.\n"
        "- 每个智能体都必须有真实自然的显示名；可以是中文或英文，但不要使用 Agent 1、Jiuwen Agent 1、Participant 1 或编号占位名。\n"
        "- Each profile must be scenario-specific: role, household, persona, daily_routine, relationships, goal, constraints, and scenario_role.\n"
        "- Relationships should reference other generated agent names or roles so the town has social texture.\n"
        "- Do not put skills inside profile. Skills are executable runtime ids on kwargs.common_skill_ids and kwargs.skill_ids.\n"
        f"- common_skill_ids must be exactly: {json.dumps(COMMON_SKILL_IDS, ensure_ascii=False)}.\n"
        f"- skill_ids must contain 3-5 ids chosen only from this executable catalog: {json.dumps(PERSONA_SKILL_IDS, ensure_ascii=False)}.\n"
        "- Initial locations must use valid location ids from the list above and should match each role's routine.\n"
        f"- Keep env_modules[0].kwargs.map_id as {package.map_id}; do not invent another map id.\n"
        "- Keep behavior safe and bounded; transform risky settings into observation, consent, rules, welfare, and communication dynamics.\n\n"
        f"Required JSON shape:\n{json.dumps(schema, ensure_ascii=False)}"
    )
    timeout_seconds = float(os.getenv("GOD_SETUP_DRAFT_TIMEOUT", "240"))
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            response = await session.post(
                url,
                headers={
                    "authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
            )
            text = await response.text()
            if response.status >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Draft model request failed via {url}: "
                        f"{_sanitize_model_error(text, api_key)}"
                    ),
                )
            payload = json.loads(text)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"Draft model request timed out after {int(timeout_seconds)} seconds. "
                "Please try a faster model/provider, reduce agent count, or set GOD_SETUP_DRAFT_TIMEOUT higher."
            ),
        ) from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Draft model request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Draft model returned a non-JSON HTTP response") from exc
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    json_text = extract_json(content) or content
    parsed = json_repair.loads(json_text)
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Draft model returned non-object JSON")
    return parsed


def _write_current_experiment(
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: Path,
    *,
    map_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    payload = {
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "workspace_path": str(workspace_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if map_id:
        payload["map_id"] = map_id
    if label:
        payload["label"] = label
    path = _current_experiment_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _read_current_experiment() -> dict[str, Any] | None:
    path = _current_experiment_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _current_map_id(current: dict[str, Any] | None) -> str:
    if not current:
        return DEFAULT_MAP_ID
    if current.get("map_id"):
        return str(current["map_id"])
    hypothesis_id = str(current.get("hypothesis_id") or "")
    experiment_id = str(current.get("experiment_id") or "1")
    for item in experiment_registry.load_registry_entries(_workspace_path()):
        if item["hypothesis_id"] == hypothesis_id and item["experiment_id"] == experiment_id:
            return str(item["map_id"])
    workspace = Path(current.get("workspace_path") or _workspace_path()).expanduser().resolve()
    config_path = _experiment_path(workspace, hypothesis_id, experiment_id) / "init" / "init_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_MAP_ID
    env_modules = config.get("env_modules") if isinstance(config, dict) else None
    if isinstance(env_modules, list):
        for module in env_modules:
            if not isinstance(module, dict):
                continue
            kwargs = module.get("kwargs")
            if isinstance(kwargs, dict) and kwargs.get("map_id"):
                return str(kwargs["map_id"])
    return DEFAULT_MAP_ID


def _write_start_request(hypothesis_id: str, experiment_id: str, workspace_path: Path) -> dict[str, Any]:
    payload = {
        "request_id": uuid.uuid4().hex,
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "workspace_path": str(workspace_path),
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    path = _start_request_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def activate_current_experiment(
    *,
    hypothesis_id: str,
    experiment_id: str,
    workspace_path: Path,
    map_id: str | None = None,
    label: str | None = None,
    start_immediately: bool = False,
) -> dict[str, Any]:
    current = _write_current_experiment(
        hypothesis_id,
        experiment_id,
        workspace_path,
        map_id=map_id,
        label=label,
    )
    start_request = (
        _write_start_request(hypothesis_id, experiment_id, workspace_path)
        if start_immediately
        else None
    )
    return {
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "workspace_path": str(workspace_path),
        "map_id": map_id,
        "current_experiment": current,
        "start_request": start_request,
    }


def _write_latest_draft(basics: DraftBasics, draft: dict[str, Any]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basics": basics.model_dump(mode="json"),
        "draft": draft,
    }
    path = _latest_draft_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_latest_draft() -> dict[str, Any] | None:
    path = _latest_draft_file()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Latest draft is unreadable: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("draft"), dict):
        raise HTTPException(status_code=500, detail="Latest draft is malformed")
    basics = payload.get("basics")
    if not isinstance(basics, dict):
        basics = {}
    return {
        "generated_at": str(payload.get("generated_at") or ""),
        "basics": basics,
        "draft": payload["draft"],
    }


@router.get("/status")
async def setup_status() -> dict[str, Any]:
    env = _merged_env()
    image_env = _merged_image_env()
    current = _read_current_experiment()
    hypothesis_id = str((current or {}).get("hypothesis_id") or "")
    experiment_id = str((current or {}).get("experiment_id") or "1")
    workspace = Path((current or {}).get("workspace_path") or _workspace_path()).expanduser().resolve()
    config_path = _experiment_path(workspace, hypothesis_id, experiment_id) / "init" / "init_config.json"
    has_current = current is not None and config_path.exists()
    default_workspace = _workspace_path()
    default_experiments = _default_experiment_status(default_workspace)
    selected_map_id = _current_map_id(current)
    maps = [map_package_summary(package, _map_service_root()) for package in _available_map_packages()]
    if selected_map_id not in {item["map_id"] for item in maps}:
        selected_map_id = DEFAULT_MAP_ID
    return {
        "god_root": str(_god_root()),
        "env_file": str(_env_file()),
        "workspace_path": str(workspace),
        "selected_map_id": selected_map_id,
        "maps": maps,
        "map_locations": _map_locations_for_status(selected_map_id),
        "model_config": {key: _redact_value(key, env.get(key)) for key in MODEL_KEYS},
        "image_model_config": {key: _redact_value(key, image_env.get(key)) for key in IMAGE_MODEL_KEYS},
        "current_experiment": current,
        "setup_mode": os.environ.get("GOD_SETUP_MODE") == "1",
        "default_experiments": default_experiments,
        "default_experiment": next(
            (item for item in default_experiments if item["key"] == DEFAULT_EXPERIMENT_KEY),
            None,
        ),
        "needs_setup": not bool(env.get("GOD_LLM_API_KEY")) or not has_current,
    }


@router.get("/latest-draft")
async def latest_draft() -> dict[str, Any]:
    payload = _read_latest_draft()
    if payload is None:
        raise HTTPException(status_code=404, detail="No generated setup draft found")
    return payload


@router.post("/model-config")
async def save_model_config(payload: ModelConfigPayload) -> dict[str, Any]:
    values = {
        key: str(value).strip()
        for key, value in payload.model_dump().items()
        if value is not None and str(value).strip() != ""
    }
    for key, default in ENV_DEFAULTS.items():
        if key in MODEL_KEYS and key not in values:
            values[key] = _merged_env().get(key, default)
    if values:
        _write_model_env_values(values)
    return await setup_status()


@router.post("/generate-draft")
async def generate_draft(request: GenerateDraftRequest) -> dict[str, Any]:
    env = _merged_env()
    model_config = request.llm_config or ModelConfigPayload()
    api_key = model_config.GOD_LLM_API_KEY or env.get("GOD_LLM_API_KEY") or ""
    api_base = model_config.GOD_LLM_API_BASE or env.get("GOD_LLM_API_BASE") or ENV_DEFAULTS["GOD_LLM_API_BASE"]
    model = model_config.GOD_LLM_MODEL or env.get("GOD_LLM_MODEL") or ENV_DEFAULTS["GOD_LLM_MODEL"]
    if not api_key.strip():
        raise HTTPException(status_code=400, detail="GOD_LLM_API_KEY is required to generate an experiment draft")
    package = _load_map_package(request.basics.map_id)
    try:
        raw = await _call_openai_compatible(
            api_key=api_key.strip(),
            api_base=api_base.strip(),
            model=model.strip(),
            basics=request.basics,
            package=package,
        )
    except HTTPException:
        raise
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Draft model request timed out") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Draft model request failed: {exc}") from exc
    draft = _normalize_draft(raw, request.basics)
    _write_latest_draft(request.basics, draft)
    return draft


@router.post("/agent-studio/generate", response_model=AgentStudioGenerateResponse)
async def generate_agent_studio_options(
    request: AgentStudioGenerateRequest,
) -> AgentStudioGenerateResponse:
    return _agent_studio_response(request)


@router.post("/agent-studio/character", response_model=AgentStudioCharacterAsset)
async def generate_agent_studio_character(
    file: UploadFile = File(...),
    map_id: str = Form(DEFAULT_MAP_ID),
    agent_id: int = Form(0),
    agent_name: str = Form(""),
    prompt: str = Form(""),
    mbti: str = Form(""),
    appearance_json: str = Form("{}"),
    image_api_key: str = Form(""),
    image_api_base: str = Form(""),
    image_model: str = Form(""),
    image_provider: str = Form("openai"),
) -> AgentStudioCharacterAsset:
    map_id = _form_text(map_id, DEFAULT_MAP_ID)
    agent_name = _form_text(agent_name)
    prompt = _form_text(prompt)
    mbti = _form_text(mbti)
    appearance_json = _form_text(appearance_json, "{}")
    image_api_key = _form_text(image_api_key)
    image_api_base = _form_text(image_api_base)
    image_model = _form_text(image_model)
    image_provider = _form_text(image_provider, "openai")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Image upload is empty")
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image upload is too large; keep it under 8 MB")

    try:
        appearance = json.loads(appearance_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"appearance_json must be a JSON object: {exc}") from exc
    if not isinstance(appearance, dict):
        raise HTTPException(status_code=400, detail="appearance_json must be a JSON object")

    return await _generate_agent_sprite_asset(
        reference_bytes=content,
        reference_filename=file.filename or "reference.png",
        content_type=file.content_type or "image/png",
        agent_id=agent_id,
        agent_name=agent_name,
        map_id=map_id,
        prompt=prompt,
        mbti=mbti,
        appearance=appearance,
        image_config={
            "image_api_key": image_api_key,
            "image_api_base": image_api_base,
            "image_model": image_model,
            "image_provider": image_provider,
        },
    )


@router.get("/agent-studio/draft-characters/{character_name}")
async def get_agent_studio_draft_character_asset(
    character_name: str,
) -> FileResponse:
    root = _agent_studio_draft_character_root()
    safe_name = Path(character_name).name
    for candidate in (root / safe_name, root / f"{safe_name}.png"):
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail=f"Draft character asset not found: {character_name}")


@router.get("/agent-studio/characters/{map_id}/{character_name}")
async def get_agent_studio_character_asset(
    map_id: str,
    character_name: str,
) -> FileResponse:
    package = _load_map_package(map_id)
    root = _map_character_root(package)
    safe_name = Path(character_name).name
    for candidate in (root / safe_name, root / f"{safe_name}.png"):
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail=f"Character asset not found: {character_name}")


@router.post("/agent-studio/save-agent-pack")
async def save_agent_studio_agent_pack(request: SaveAgentPackRequest) -> dict[str, Any]:
    pack = agent_pack_service.save_agent_pack_from_agent(
        root=_map_service_root(),
        pack_id=request.pack_id,
        display_name=request.display_name or request.pack_id,
        agent=request.agent,
        initial_location=request.initial_location,
    )
    if not pack.validation.ok:
        raise HTTPException(status_code=400, detail=pack.validation.as_dict())
    return agent_pack_service.agent_pack_summary(pack)


@router.post("/agent-studio/complete-role-visuals", response_model=CompleteRoleVisualsResponse)
async def complete_role_visuals(request: CompleteRoleVisualsRequest) -> CompleteRoleVisualsResponse:
    draft = deepcopy(request.draft)
    init_config = draft.get("init_config") if isinstance(draft.get("init_config"), dict) else {}
    env_modules = init_config.get("env_modules", []) if isinstance(init_config, dict) else []
    env_kwargs = env_modules[0].get("kwargs", {}) if env_modules and isinstance(env_modules[0], dict) else {}
    context = draft.get("experiment_context", {}) if isinstance(draft.get("experiment_context"), dict) else {}
    map_id = str(env_kwargs.get("map_id") or context.get("map_id") or DEFAULT_MAP_ID)
    package = _load_map_package(map_id)
    agents = init_config.get("agents", []) if isinstance(init_config, dict) else []
    results: list[CompleteRoleVisualResult] = []

    for agent in agents:
        if not isinstance(agent, dict):
            continue
        kwargs = agent.get("kwargs") if isinstance(agent.get("kwargs"), dict) else {}
        profile = kwargs.get("profile") if isinstance(kwargs.get("profile"), dict) else {}
        agent_id = int(agent.get("agent_id") or kwargs.get("id") or 0)
        name = str(kwargs.get("name") or profile.get("name") or f"Agent {agent_id}")
        if _profile_has_valid_character_sprite(package, profile):
            appearance = profile.get("appearance") if isinstance(profile.get("appearance"), dict) else {}
            results.append(
                CompleteRoleVisualResult(
                    agent_id=agent_id,
                    name=name,
                    status="skipped",
                    filename=str(appearance.get("character_sprite_filename") or ""),
                )
            )
            continue
        try:
            asset = await _generate_agent_sprite_asset(
                reference_bytes=None,
                reference_filename="",
                content_type="image/png",
                agent_id=agent_id,
                agent_name=name,
                map_id=package.map_id,
                prompt=_role_image_prompt(agent),
                mbti=str(profile.get("mbti") or ""),
                appearance=profile.get("appearance") if isinstance(profile.get("appearance"), dict) else {},
                image_config=request.image_config,
            )
            _attach_character_asset_to_agent(agent, asset)
            results.append(
                CompleteRoleVisualResult(agent_id=agent_id, name=name, status="completed", filename=asset.filename)
            )
        except Exception as exc:
            results.append(CompleteRoleVisualResult(agent_id=agent_id, name=name, status="failed", error=str(exc)))

    completed = sum(1 for item in results if item.status == "completed")
    failed = sum(1 for item in results if item.status == "failed")
    return CompleteRoleVisualsResponse(draft=draft, results=results, completed_count=completed, failed_count=failed)


@router.post("/publish")
async def publish_experiment(request: PublishRequest) -> dict[str, Any]:
    draft_context = request.draft.get("experiment_context", {}) if isinstance(request.draft.get("experiment_context"), dict) else {}
    draft_env_modules = request.draft.get("init_config", {}).get("env_modules", []) if isinstance(request.draft.get("init_config"), dict) else []
    draft_env_kwargs: dict[str, Any] = {}
    if draft_env_modules and isinstance(draft_env_modules[0], dict):
        draft_env_kwargs = draft_env_modules[0].get("kwargs") or {}
    basics = DraftBasics(
        title=str(draft_context.get("title") or "Custom GOD Experiment"),
        background=str(draft_context.get("background") or "Custom GOD experiment"),
        agent_count=max(1, len(request.draft.get("init_config", {}).get("agents", []) or [1])),
        map_id=str(draft_env_kwargs.get("map_id") or draft_context.get("map_id") or DEFAULT_MAP_ID),
    )
    draft = _normalize_draft(request.draft, basics)
    workspace = _workspace_path()
    workspace.mkdir(parents=True, exist_ok=True)

    base_slug = _sanitize_slug(
        request.requested_hypothesis_id
        or str(draft["experiment_context"].get("title") or basics.title)
    )
    hypothesis_id = base_slug
    suffix = 2
    while (workspace / f"hypothesis_{hypothesis_id}").exists():
        hypothesis_id = f"{base_slug}_{suffix}"
        suffix += 1

    experiment_id = _sanitize_slug(str(request.experiment_id or "1"))
    exp_dir = _experiment_path(workspace, hypothesis_id, experiment_id)
    init_dir = exp_dir / "init"
    init_dir.mkdir(parents=True, exist_ok=False)

    (init_dir / "init_config.json").write_text(
        json.dumps(draft["init_config"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (init_dir / "steps.yaml").write_text(
        yaml.safe_dump(draft["steps"], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (init_dir / "experiment_context.json").write_text(
        json.dumps(draft["experiment_context"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (exp_dir / "README.md").write_text(str(draft["readme"]).rstrip() + "\n", encoding="utf-8")
    (exp_dir / "EXPERIMENT.md").write_text(str(draft["readme"]).rstrip() + "\n", encoding="utf-8")
    hyp_dir = workspace / f"hypothesis_{hypothesis_id}"
    (hyp_dir / "HYPOTHESIS.md").write_text(
        f"# {draft['experiment_context'].get('title')}\n\n{draft['experiment_context'].get('background')}\n",
        encoding="utf-8",
    )
    (hyp_dir / "SIM_SETTINGS.json").write_text(
        json.dumps(
            {
                "agentClasses": ["JiuwenClawAgent"],
                "envModules": ["PixelTownSocialEnv"],
                "experimentContext": draft["experiment_context"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    env_values: dict[str, str] = {}
    if request.llm_config:
        env_values.update(
            {
                key: str(value).strip()
                for key, value in request.llm_config.model_dump().items()
                if value is not None and str(value).strip() != ""
            }
        )
    _write_model_env_values(env_values)
    activation = activate_current_experiment(
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        workspace_path=workspace,
        map_id=str(draft["experiment_context"].get("map_id", DEFAULT_MAP_ID)),
        label=str(draft["experiment_context"].get("title") or hypothesis_id),
        start_immediately=request.start_immediately,
    )
    return {
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "workspace_path": str(workspace),
        "experiment_path": str(exp_dir),
        "current_experiment": activation["current_experiment"],
        "start_request": activation["start_request"],
        "warnings": draft["warnings"],
    }


@router.post("/start-request")
async def create_start_request(payload: StartRequestPayload) -> dict[str, Any]:
    current = _read_current_experiment() or {}
    hypothesis_id = payload.hypothesis_id or current.get("hypothesis_id")
    experiment_id = payload.experiment_id or current.get("experiment_id") or "1"
    workspace = Path(payload.workspace_path or current.get("workspace_path") or _workspace_path()).expanduser().resolve()
    if not hypothesis_id:
        raise HTTPException(status_code=400, detail="No current experiment is configured")
    return _write_start_request(str(hypothesis_id), str(experiment_id), workspace)


@router.post("/start-default")
async def start_default_experiment(request: StartDefaultRequest | None = None) -> dict[str, Any]:
    experiment_key = (request.experiment_key if request else DEFAULT_EXPERIMENT_KEY) or DEFAULT_EXPERIMENT_KEY
    workspace = _workspace_path()
    default_experiment = experiment_registry.load_registry_by_key(workspace).get(experiment_key)
    if default_experiment is None:
        raise HTTPException(status_code=404, detail=f"Unknown default experiment: {experiment_key}")
    hypothesis_id = default_experiment["hypothesis_id"]
    experiment_id = default_experiment["experiment_id"]
    config_path = _experiment_path(workspace, hypothesis_id, experiment_id) / "init" / "init_config.json"
    if not config_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Default experiment config not found: {config_path}",
        )
    activation = activate_current_experiment(
        hypothesis_id=hypothesis_id,
        experiment_id=experiment_id,
        workspace_path=workspace,
        map_id=default_experiment["map_id"],
        label=default_experiment["label"],
        start_immediately=True,
    )
    return {
        "experiment_key": experiment_key,
        "hypothesis_id": hypothesis_id,
        "experiment_id": experiment_id,
        "workspace_path": str(workspace),
        "map_id": default_experiment["map_id"],
        "current_experiment": activation["current_experiment"],
        "start_request": activation["start_request"],
    }
