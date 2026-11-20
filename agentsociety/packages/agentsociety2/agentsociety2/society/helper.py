"""仿真社会辅助模块。

本模块提供 :class:`AgentSocietyHelper` 类，实现 Plan-and-Execute 模式的外部请求处理。

主要功能：

- **问答处理**: 通过 :meth:`ask` 方法回答关于仿真的问题
- **干预执行**: 通过 :meth:`intervene` 方法执行对仿真的干预
- **动态重规划**: 当执行失败时自动调整计划
- **工具调度**: 调度内置工具与环境路由器和智能体交互

内置工具：

- ``get_current_time`` — 获取当前仿真时间
- ``filter_agents_by_profile`` — 按属性筛选智能体
- ``ask_environment`` — 向环境路由器提问
- ``ask_agents`` — 向特定智能体提问

Example::

    from agentsociety2.society.helper import AgentSocietyHelper

    helper = AgentSocietyHelper(env_router=router, agents=[agent1, agent2])

    # 问答模式
    answer = await helper.ask("当前有多少智能体在线？")

    # 干预模式
    result = await helper.intervene("让所有智能体移动到城市中心")
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence

import json_repair
from litellm import AllMessageValues
from pydantic import BaseModel

from agentsociety2.agent import AgentBase
from agentsociety2.config import extract_json, get_llm_router_and_model
from agentsociety2.env import RouterBase
from agentsociety2.logger import get_logger

__all__ = ["AgentSocietyHelper"]


def _to_json_string(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps({"value": str(value)}, ensure_ascii=False)


def _truncate_text(text: str, max_len: int = 4000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...[truncated]..."


class PlanStep(BaseModel):
    """A single step in the execution plan."""

    description: str
    """Clear description of what this step does."""
    tool: str
    """The name of the tool to use."""
    args: Dict[str, Any]
    """Arguments to pass to the tool."""
    expected_output: str
    """What information or result this step should produce."""


@dataclass
class _ToolDef:
    schema: Dict[str, Any]
    fn: Callable[..., Any]


class AgentSocietyHelper:
    """
    Plan-and-Execute helper that answers external questions or executes interventions
    by first creating a plan, then executing steps, with support for dynamic replanning.
    """

    def __init__(
        self,
        env_router: RouterBase,
        agents: Sequence[AgentBase],
        max_steps: int = 8,
        max_replans: int = 2,
        max_llm_call_retry: int = 10,
    ):
        self._router, self._model_name = get_llm_router_and_model("coder")
        self._env_router = env_router
        self._agents = agents
        self._max_steps = max(1, max_steps)
        self._max_replans = max(0, max_replans)
        self._max_llm_call_retry = max(1, max_llm_call_retry)
        self._tools: Dict[str, _ToolDef] = {}
        self._current_readonly: bool = True
        self._register_tools()

    def _log_llm_raw_response(self, stage: str, response: str) -> None:
        logger = get_logger()
        logger.debug(
            "AgentSocietyHelper %s raw LLM response:\n%s",
            stage,
            _truncate_text(response),
        )

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        json_str = extract_json(response)
        if json_str is None:
            raise ValueError("Failed to extract JSON from LLM response")

        parsed = json_repair.loads(json_str)
        if not isinstance(parsed, dict):
            raise ValueError(
                f"Expected JSON object from LLM response, got {type(parsed).__name__}"
            )
        return parsed

    # ---- public API ----
    async def ask(self, question: str) -> str:
        return await self._run(question, readonly=True)

    async def intervene(self, instruction: str) -> str:
        return await self._run(instruction, readonly=False)

    # ---- internal: Plan-and-Execute loop ----
    async def _run(self, text: str, readonly: bool) -> str:
        mode = "Ask" if readonly else "Intervene"
        print(f"\n{'='*60}")
        print(f"AgentSocietyHelper Starting ({mode} Mode)")
        print(f"Task: {text}")
        print(f"{'='*60}\n")

        self._current_readonly = readonly

        # Phase 1: Planning
        plan = await self._create_plan(text, readonly)
        if isinstance(plan, str):
            # Planning returned direct answer or error
            return plan

        print(f"\n📋 Initial Plan ({len(plan)} steps):")
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step.description}")
        print()

        # Phase 2: Execution with dynamic replanning
        replan_count = 0
        execution_history: List[Dict[str, Any]] = []

        while plan and replan_count <= self._max_replans:
            step_index = len(execution_history)
            if step_index >= len(plan):
                # All steps completed
                break

            if len(execution_history) >= self._max_steps:
                print(f"⚠️ Max steps ({self._max_steps}) reached\n")
                break

            current_step = plan[step_index]
            print(f"[Step {step_index + 1}/{len(plan)}] {current_step.description}")

            # Execute step
            try:
                result = await self._execute_step(current_step, execution_history)
                execution_history.append(
                    {
                        "step": current_step,
                        "result": result,
                        "success": True,
                    }
                )
                print(f"  ✓ Result: {_to_json_string(result)}\n")

            except Exception as e:
                get_logger().error(f"Step execution failed: {e}")
                execution_history.append(
                    {
                        "step": current_step,
                        "error": str(e),
                        "success": False,
                    }
                )
                print(f"  ✗ Error: {str(e)}\n")

                # Check if replanning is needed
                if replan_count < self._max_replans:
                    print(
                        f"🔄 Replanning (attempt {replan_count + 1}/{self._max_replans})..."
                    )
                    new_plan = await self._replan(
                        text, plan, execution_history, readonly
                    )
                    if new_plan:
                        plan = new_plan
                        replan_count += 1
                        print(f"  Updated Plan ({len(plan)} steps):")
                        for i, step in enumerate(plan, 1):
                            print(f"    {i}. {step.description}")
                        print()
                    else:
                        print("  Replanning failed, continuing with original plan\n")

        # Phase 3: Generate final answer
        final_answer = await self._generate_final_answer(
            text, plan, execution_history, readonly
        )
        print(f"\n{'='*60}")
        print(f"✓ Completed ({len(execution_history)} steps executed)")
        print(f"Final Answer: {final_answer}")
        print(f"{'='*60}\n")
        return final_answer

    async def _create_plan(self, task: str, readonly: bool) -> str | List[PlanStep]:
        """Create an execution plan for the given task."""
        planning_prompt = self._build_planning_prompt(task, readonly)

        error_history = []
        for retry in range(self._max_llm_call_retry):
            # Build dialog with error history if this is a retry
            current_prompt = planning_prompt
            if error_history:
                error_feedback = "\n\n## Previous Attempt Errors\n"
                error_feedback += (
                    "The following attempts failed. Please fix these issues:\n\n"
                )
                for i, error_info in enumerate(error_history):
                    error_feedback += f"Attempt {i + 1}:\n"
                    error_feedback += f"Response: {error_info['response']}\n"
                    error_feedback += f"Error: {error_info['error']}\n\n"
                current_prompt = planning_prompt + error_feedback

            messages: List[AllMessageValues] = [
                {"role": "user", "content": current_prompt}
            ]

            try:
                resp = await self._router.acompletion(
                    model=self._model_name,
                    messages=messages,
                    stream=False,
                )
                response = resp.choices[0].message.content  # type: ignore

                if not response:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": "Empty response",
                                "error": "Model returned empty response",
                            }
                        )
                        continue
                    return "Planning failed: Empty model response"

                self._log_llm_raw_response(f"planning attempt {retry + 1}", response)
                plan_data = self._parse_json_response(response)

                # Check if this is a direct answer (no planning needed)
                if plan_data.get("direct_answer"):
                    return str(plan_data.get("answer", ""))

                # Extract and validate steps with PlanStep
                raw_steps = plan_data.get("steps", [])
                if not raw_steps:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": response,
                                "error": "No valid steps were generated",
                            }
                        )
                        continue
                    return "Unable to create a plan for this task."

                # Validate each step with Pydantic
                try:
                    steps = [PlanStep.model_validate(step) for step in raw_steps]
                    return steps
                except Exception as validation_error:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": response,
                                "error": f"Step validation failed: {str(validation_error)}",
                            }
                        )
                        continue
                    return f"Plan validation failed: {str(validation_error)}"

            except Exception as e:
                get_logger().error(f"Planning attempt {retry + 1} failed: {e}")
                if retry < self._max_llm_call_retry - 1:
                    error_history.append(
                        {
                            "response": resp.choices[0].message.content if "resp" in locals() else "No response",  # type: ignore
                            "error": str(e),
                        }
                    )
                    continue
                return f"Planning failed: {str(e)}"

        return "Unable to create a plan for this task after multiple attempts."

    async def _execute_step(
        self, step: PlanStep, history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a single step from the plan."""
        tool_name = step.tool
        args = step.args

        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        result = await self._dispatch_tool(tool_name, args, self._current_readonly)
        return result

    async def _replan(
        self,
        original_task: str,
        current_plan: List[PlanStep],
        execution_history: List[Dict[str, Any]],
        readonly: bool,
    ) -> List[PlanStep] | None:
        """Create a new plan based on execution history and failures."""
        replanning_prompt = self._build_replanning_prompt(
            original_task, current_plan, execution_history, readonly
        )

        error_history = []
        for retry in range(self._max_llm_call_retry):
            response = None
            # Build dialog with error history if this is a retry
            current_prompt = replanning_prompt
            if error_history:
                error_feedback = "\n\n## Previous Attempt Errors\n"
                error_feedback += (
                    "The following attempts failed. Please fix these issues:\n\n"
                )
                for i, error_info in enumerate(error_history):
                    error_feedback += f"Attempt {i + 1}:\n"
                    error_feedback += f"Response: {error_info['response']}\n"
                    error_feedback += f"Error: {error_info['error']}\n\n"
                current_prompt = replanning_prompt + error_feedback

            try:
                messages: List[AllMessageValues] = [
                    {"role": "user", "content": current_prompt}
                ]

                resp = await self._router.acompletion(
                    model=self._model_name,
                    messages=messages,
                    stream=False,
                )
                response = resp.choices[0].message.content  # type: ignore

                if not response:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": "Empty response",
                                "error": "Model returned empty response",
                            }
                        )
                        continue
                    return None

                self._log_llm_raw_response(f"replanning attempt {retry + 1}", response)
                plan_data = self._parse_json_response(response)
                raw_steps = plan_data.get("steps", [])

                if not raw_steps:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": response,
                                "error": "No valid steps were generated in replanning",
                            }
                        )
                        continue
                    return None

                # Validate steps with PlanStep
                try:
                    steps = [PlanStep.model_validate(step) for step in raw_steps]
                    return steps
                except Exception as validation_error:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": response,
                                "error": f"Step validation failed: {str(validation_error)}",
                            }
                        )
                        continue
                    return None

            except Exception as e:
                get_logger().error(f"Replanning attempt {retry + 1} failed: {e}")
                if retry < self._max_llm_call_retry - 1:
                    error_history.append(
                        {
                            "response": (
                                response if response is not None else "No response"
                            ),
                            "error": str(e),
                        }
                    )
                    continue
                return None

        return None

    async def _generate_final_answer(
        self,
        task: str,
        plan: List[PlanStep],
        execution_history: List[Dict[str, Any]],
        readonly: bool,
    ) -> str:
        """Generate the final answer based on execution history."""
        summary_prompt = self._build_summary_prompt(
            task, plan, execution_history, readonly
        )

        error_history = []
        for retry in range(self._max_llm_call_retry):
            final_answer = None
            # Build dialog with error history if this is a retry
            current_prompt = summary_prompt
            if error_history:
                error_feedback = "\n\n## Previous Attempt Errors\n"
                error_feedback += (
                    "The following attempts failed. Please fix these issues:\n\n"
                )
                for i, error_info in enumerate(error_history):
                    error_feedback += f"Attempt {i + 1}:\n"
                    error_feedback += f"Response: {error_info['response']}\n"
                    error_feedback += f"Error: {error_info['error']}\n\n"
                current_prompt = summary_prompt + error_feedback

            try:
                messages: List[AllMessageValues] = [
                    {"role": "user", "content": current_prompt}
                ]

                resp = await self._router.acompletion(
                    model=self._model_name,
                    messages=messages,
                    stream=False,
                )
                final_answer = resp.choices[0].message.content  # type: ignore

                if not final_answer:
                    if retry < self._max_llm_call_retry - 1:
                        error_history.append(
                            {
                                "response": "Empty response",
                                "error": "Model returned empty response",
                            }
                        )
                        continue
                    return "Unable to generate final answer based on execution results."

                self._log_llm_raw_response(
                    f"final answer attempt {retry + 1}", final_answer
                )
                # Parse final answer
                try:
                    answer_data = self._parse_json_response(final_answer)
                    if "answer" not in answer_data:
                        if retry < self._max_llm_call_retry - 1:
                            error_history.append(
                                {
                                    "response": final_answer,
                                    "error": "Response is a JSON object but missing 'answer' key",
                                }
                            )
                            continue
                        return "Unable to generate final answer based on execution results."
                    return str(answer_data.get("answer"))
                except Exception:
                    # If not JSON, use response as-is
                    return str(final_answer)

            except Exception as e:
                get_logger().error(
                    f"Final answer generation attempt {retry + 1} failed: {e}"
                )
                if retry < self._max_llm_call_retry - 1:
                    error_history.append(
                        {
                            "response": (
                                final_answer
                                if final_answer is not None
                                else "No response"
                            ),
                            "error": str(e),
                        }
                    )
                    continue
                return "Unable to generate final answer based on execution results."

        return "Unable to generate final answer based on execution results."

    async def _dispatch_tool(self, name: str, args: Dict[str, Any], readonly: bool):
        # Internally propagate readonly to tools that interact with env/agents
        if name in {"ask_environment", "ask_agents"}:
            return await self._tools[name].fn(**args, readonly=readonly)
        return await self._tools[name].fn(**args)

    # ---- Prompt builders ----
    def _build_planning_prompt(self, task: str, readonly: bool) -> str:
        """Build the planning prompt with structured format."""
        mode = "information retrieval" if readonly else "intervention and modification"
        restriction = (
            "You MUST NOT modify the environment or agent states. Only use read-only operations."
            if readonly
            else "You MAY modify the environment or agent states as needed to accomplish the task."
        )

        tools_desc = []
        for name, tool_def in self._tools.items():
            func_info = tool_def.schema.get("function", {})
            tools_desc.append(
                f"- **{name}**: {func_info.get('description', 'No description')}\n"
                f"  Parameters: {json.dumps(func_info.get('parameters', {}), ensure_ascii=False)}"
            )
        tools_text = "\n".join(tools_desc)

        return f"""# Task Planning for AgentSocietyHelper

## Objective
You are a planning assistant for AgentSocietyHelper. Your goal is to create a step-by-step execution plan for {mode}.

## Task
{task}

## Constraints
{restriction}

## Available Tools
{tools_text}

## Planning Guidelines
1. **Analyze the task** carefully to understand what information or actions are required
2. **Break down** the task into clear, sequential steps
3. **Select appropriate tools** for each step based on their capabilities
4. **Minimize steps** - be efficient and avoid redundant operations
5. **Consider dependencies** - ensure each step has the information it needs from previous steps
6. **Handle edge cases** - plan for potential failures or missing information

## Response Format
Respond with a JSON object in one of two formats:

**Format 1: If the task requires planning**
```json
{{
  "direct_answer": false,
  "reasoning": "Brief explanation of your planning strategy",
  "steps": [
    {{
      "description": "Clear description of what this step does",
      "tool": "tool_name",
      "args": {{"param1": "value1", "param2": "value2"}},
      "expected_output": "What information or result this step should produce"
    }}
  ]
}}
```

**Format 2: If the task is simple and can be answered directly**
```json
{{
  "direct_answer": true,
  "answer": "Direct answer to the task"
}}
```

## Important Notes
- Use `direct_answer: true` ONLY for trivial questions that require no tool calls
- For most tasks, create a proper plan with specific tool calls
- Ensure all required parameters for each tool are included in args
- Keep step descriptions clear and actionable
- The plan should be complete and executable without human intervention

Now, create a plan for the given task. Your JSON response:"""

    def _build_replanning_prompt(
        self,
        original_task: str,
        current_plan: List[PlanStep],
        execution_history: List[Dict[str, Any]],
        readonly: bool,
    ) -> str:
        """Build the replanning prompt."""
        history_text = []
        for i, entry in enumerate(execution_history, 1):
            step = entry.get("step")
            success = entry.get("success", False)
            status = "SUCCESS" if success else "FAILED"

            if isinstance(step, PlanStep):
                step_desc = step.description
                tool_name = step.tool
            else:
                step_desc = (
                    step.get("description", "N/A") if isinstance(step, dict) else "N/A"
                )
                tool_name = step.get("tool", "N/A") if isinstance(step, dict) else "N/A"

            history_text.append(
                f"Step {i}:\n"
                f"  Description: {step_desc}\n"
                f"  Tool: {tool_name}\n"
                f"  Status: {status}\n"
                f"  Result: {_to_json_string(entry.get('result') if success else entry.get('error'))}"
            )
        history_summary = "\n\n".join(history_text)

        tools_desc = []
        for name, tool_def in self._tools.items():
            func_info = tool_def.schema.get("function", {})
            tools_desc.append(
                f"- **{name}**: {func_info.get('description', 'No description')}\n"
                f"  Parameters: {json.dumps(func_info.get('parameters', {}), ensure_ascii=False)}"
            )
        tools_text = "\n".join(tools_desc)

        return f"""# Plan Adjustment for AgentSocietyHelper

## Original Task
{original_task}

## Execution History (with SUCCESS/FAILED status)
{history_summary}

**Note**: Each step includes:
- `Status`: SUCCESS or FAILED - indicates if the step completed successfully
- `Result`: The data returned by the step (for SUCCESS) or error message (for FAILED)

## Available Tools
{tools_text}

## Replanning Objective
Based on the execution history (including any failures), create an updated plan to complete the original task.

**CRITICAL RULES**:
1. **DO NOT repeat SUCCESS steps** - Tasks marked as SUCCESS have already been completed and may have side effects (database writes, file modifications, state changes). DO NOT include them in the new plan.
2. **Learn from FAILED steps** - Understand why they failed and use a different approach.
3. **Use information from SUCCESS steps** - Successful steps may have returned data that you can reference or build upon.

## Guidelines
1. **Review the execution history** - Identify which steps succeeded and which failed
2. **Analyze failures** - Understand what went wrong with FAILED steps
3. **Preserve successful work** - Never repeat SUCCESS steps, only plan remaining/failed work
4. **Adjust strategy** - Use different tools or approaches for previously failed steps
5. **Build on success** - Use data from successful steps' results when available
6. **Complete the task** - Ensure the original goal is still achievable
7. **Be pragmatic** - If the task is impossible, plan to gather relevant information instead

## Response Format
Respond with a JSON object containing the updated plan:

```json
{{
  "reasoning": "Explanation of what went wrong and how you're adjusting the plan",
  "steps": [
    {{
      "description": "Clear description of what this step does",
      "tool": "tool_name",
      "args": {{"param1": "value1"}},
      "expected_output": "Expected result"
    }}
  ]
}}
```

Create an updated plan. Your JSON response:"""

    def _build_summary_prompt(
        self,
        task: str,
        plan: List[PlanStep],
        execution_history: List[Dict[str, Any]],
        readonly: bool,
    ) -> str:
        """Build the summary prompt to generate final answer."""
        history_text = []
        for i, entry in enumerate(execution_history, 1):
            step = entry.get("step")
            success = entry.get("success", False)

            if isinstance(step, PlanStep):
                step_desc = step.description
                tool_name = step.tool
            else:
                step_desc = (
                    step.get("description", "N/A") if isinstance(step, dict) else "N/A"
                )
                tool_name = step.get("tool", "N/A") if isinstance(step, dict) else "N/A"

            history_text.append(
                f"Step {i}: {step_desc}\n"
                f"  Tool: {tool_name}\n"
                f"  Success: {success}\n"
                f"  Result: {_to_json_string(entry.get('result') if success else entry.get('error'))}"
            )
        execution_summary = "\n\n".join(history_text)

        return f"""# Final Answer Generation for AgentSocietyHelper

## Original Task
{task}

## Execution Summary
{execution_summary}

## Objective
Based on the execution results above, generate a clear, concise, and accurate final answer to the original task.

## Guidelines
1. **Synthesize information** from all successful step results
2. **Address the task directly** - answer what was asked
3. **Be concise** - provide only relevant information
4. **Answer language** - use the response language requested in the task, or the question's language if none is specified
5. **Acknowledge failures** if they prevented completing the task
6. **Be factual** - only state what the execution results support

## Response Format
Respond with a JSON object:

```json
{{
  "answer": "Your clear and direct final answer to the task"
}}
```

Generate the final answer. Your JSON response:"""

    # ---- tool registration ----
    def _register_tools(self):
        self._tools = {
            "get_current_time": _ToolDef(
                schema={
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "description": "Return current simulation datetime as ISO string.",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                fn=self._tool_get_current_time,
            ),
            "filter_agents_by_profile": _ToolDef(
                schema={
                    "type": "function",
                    "function": {
                        "name": "filter_agents_by_profile",
                        "description": (
                            "Filter agents by asking each agent for a profile field and matching equality. "
                            "Use field like 'gender' and value like 'male' or 'female'."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "value": {"type": ["string", "number", "boolean"]},
                            },
                            "required": ["field", "value"],
                        },
                    },
                },
                fn=self._tool_filter_agents_by_profile,
            ),
            "ask_environment": _ToolDef(
                schema={
                    "type": "function",
                    "function": {
                        "name": "ask_environment",
                        "description": (
                            "Ask the environment router a question; good for facts about modules, world, or aggregates."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {"question": {"type": "string"}},
                            "required": ["question"],
                        },
                    },
                },
                fn=self._tool_ask_environment,
            ),
            "ask_agents": _ToolDef(
                schema={
                    "type": "function",
                    "function": {
                        "name": "ask_agents",
                        "description": "Ask specific agents a question and aggregate their answers.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "agent_ids": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                },
                                "question": {"type": "string"},
                            },
                            "required": ["agent_ids", "question"],
                        },
                    },
                },
                fn=self._tool_ask_agents,
            ),
        }

    # ---- tool impls ----

    async def _tool_get_current_time(self) -> Dict[str, Any]:
        return {"current_time": self._env_router.t.isoformat()}

    # removed agent direct-inspection helpers to respect agent-only interfaces

    async def _tool_filter_agents_by_profile(
        self, field: str, value: Any
    ) -> Dict[str, Any]:
        ids: List[int] = []
        # Ask each agent for the requested field via its LLM interface
        tasks: List[Any] = []
        order: List[int] = []
        question = (
            f"Please return your `{field}` field value, only output the original value."
        )
        for a in self._agents:
            order.append(a.id)
            tasks.append(a.ask(question, readonly=True))
        results: List[str] = []
        if tasks:
            results = list(await asyncio.gather(*tasks, return_exceptions=False))
        for agent_id, ans in zip(order, results):
            try:
                if str(ans).strip().lower() == str(value).strip().lower():
                    ids.append(agent_id)
            except Exception:
                continue
        return {"agent_ids": ids}

    async def _tool_ask_environment(
        self,
        question: str,
        readonly: bool,
    ) -> Dict[str, Any]:
        ctx = {}
        more_ctx, answer = await self._env_router.ask(
            ctx, question, readonly=bool(readonly)
        )
        return {"answer": answer, "context": more_ctx}

    async def _tool_ask_agents(
        self, agent_ids: List[int], question: str, readonly: bool | None = None
    ) -> Dict[str, Any]:
        by_id: Dict[int, AgentBase] = {a.id: a for a in self._agents}
        tasks = []
        order: List[int] = []
        for i in agent_ids:
            a = by_id.get(int(i))
            if a is None:
                continue
            order.append(int(i))
            tasks.append(a.ask(question, readonly=bool(readonly)))
        results: List[str] = []
        if tasks:
            results = list(await asyncio.gather(*tasks, return_exceptions=False))
        answers: Dict[str, Any] = {}
        for i, ans in zip(order, results):
            answers[str(i)] = ans
        return {"answers": answers}
