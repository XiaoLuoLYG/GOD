"""Pydantic models for AgentSociety2 experiment configuration validation"""

from datetime import datetime
from typing import Dict, Any, List, Union, Literal

from pydantic import BaseModel, Field, field_validator, model_serializer

__all__ = [
    "EnvModuleConfig",
    "AgentConfig",
    "CodeGenRouterConfig",
    "InitConfig",
    "RunStep",
    "AskStep",
    "InterveneStep",
    "QuestionItem",
    "QuestionnaireStep",
    "StepUnion",
    "StepsConfig",
]


class EnvModuleConfig(BaseModel):
    """环境模块配置模型"""
    
    module_type: str = Field(..., description="环境模块类型")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="环境模块初始化参数")


class AgentConfig(BaseModel):
    """Agent配置模型，匹配init_config.json中的格式"""
    
    agent_id: int = Field(..., description="Agent的唯一ID")
    agent_type: str = Field(..., description="Agent类型")
    kwargs: Dict[str, Any] = Field(..., description="Agent初始化参数，包含id、profile等所有参数")
    
    @field_validator("kwargs")
    @classmethod
    def validate_kwargs(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """验证kwargs中必须包含id字段"""
        if "id" not in v:
            raise ValueError("kwargs must contain 'id' field")
        return v


class CodeGenRouterConfig(BaseModel):
    """CodeGenRouter 配置模型"""

    final_summary_enabled: bool = Field(True, description="是否启用 ask 最终 summary")


class InitConfig(BaseModel):
    """初始化配置文件模型"""

    env_modules: List[EnvModuleConfig] = Field(..., min_length=1, description="环境模块列表")
    agents: List[AgentConfig] = Field(..., min_length=1, description="Agent列表")
    codegen_router: CodeGenRouterConfig = Field(
        default_factory=CodeGenRouterConfig,
        description="CodeGenRouter 配置",
    )
    agent_backend: Dict[str, Any] | None = Field(
        default=None,
        description="可选实验级决策后端。为空时不写入配置，默认仍是 jiuwenclaw",
    )

    @field_validator("agent_backend", mode="before")
    @classmethod
    def _coerce_agent_backend(cls, value: Any) -> Dict[str, Any] | None:
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            return {"type": text} if text else None
        raise ValueError("agent_backend must be a string or object")

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if isinstance(data, dict) and data.get("agent_backend") is None:
            data.pop("agent_backend", None)
        return data


class RunStep(BaseModel):
    """运行指定步数的步骤"""
    
    type: Literal["run"] = Field("run", description="步骤类型")
    num_steps: int = Field(..., gt=0, description="运行的步数")
    tick: int = Field(1, gt=0, description="每步的时间间隔（秒）")


class AskStep(BaseModel):
    """提问步骤"""
    
    type: Literal["ask"] = Field("ask", description="步骤类型")
    question: str = Field(..., min_length=1, description="要提问的问题")


class InterveneStep(BaseModel):
    """干预步骤"""
    
    type: Literal["intervene"] = Field("intervene", description="步骤类型")
    instruction: str = Field(..., min_length=1, description="干预指令")


class QuestionItem(BaseModel):
    """单道问卷题目配置。"""

    id: str = Field(..., min_length=1, description="题目唯一标识")
    prompt: str = Field(..., min_length=1, description="题目提示文本")
    response_type: Literal["text", "integer", "float", "choice", "json"] = Field(
        "text",
        description="回答类型",
    )
    choices: List[str] = Field(default_factory=list, description="choice 题型可选项")

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: List[str]) -> List[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned

    @field_validator("choices")
    @classmethod
    def validate_choice_question(cls, value: List[str], info) -> List[str]:
        if info.data.get("response_type") == "choice" and not value:
            raise ValueError("choices are required when response_type='choice'")
        return value


class QuestionnaireStep(BaseModel):
    """问卷步骤。"""

    type: Literal["questionnaire"] = Field("questionnaire", description="步骤类型")
    questionnaire_id: str = Field(..., min_length=1, description="问卷唯一标识")
    title: str | None = Field(None, description="问卷标题")
    description: str | None = Field(None, description="问卷说明")
    target_agent_ids: List[int] | None = Field(
        None,
        description="目标 Agent ID 列表；为空时发给全部 Agent",
    )
    questions: List[QuestionItem] = Field(..., min_length=1, description="题目列表")


StepUnion = Union[RunStep, AskStep, InterveneStep, QuestionnaireStep]


class StepsConfig(BaseModel):
    """Steps.yaml配置文件模型"""
    
    start_t: str = Field(..., description="仿真开始时间（ISO格式）")
    steps: List[StepUnion] = Field(..., min_length=1, description="步骤列表")
    
    @field_validator("start_t")
    @classmethod
    def validate_start_t(cls, v: str) -> str:
        """验证开始时间格式"""
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid ISO datetime format: {v}")
        return v
