"""
Core ML Agent execution loop.

Flow per stage:
  plan()     → LLM generates AgentPlan
  execute()  → for each step: generate code → run in sandbox → evaluate → repair if needed
  result()   → AgentRunResult with all artifacts and metrics
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Callable

from app.infra.llm.client import chat_completion
from app.infra.sandbox.base import SandboxClient
from app.orchestration.agent_runner import prompts
from app.orchestration.agent_runner.schemas import (
    AgentPlan,
    AgentRunResult,
    PlanStep,
    StepResult,
    StepStatus,
)

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 3


class AgentRunner:
    def __init__(
        self,
        sandbox: SandboxClient,
        session_id: str,
        on_event: Callable[[str, dict], None] | None = None,
    ):
        self._sandbox = sandbox
        self._session_id = session_id
        self._on_event = on_event or (lambda _type, _payload: None)

    async def plan(self, goal: str, data_context: dict) -> AgentPlan:
        self._emit("agent.planning_started", {"goal": goal})

        files = await self._sandbox.list_files(self._session_id, "/workspace/inputs")

        response = await chat_completion(
            messages=[
                {"role": "system", "content": prompts.PLANNER_SYSTEM},
                {"role": "user", "content": prompts.planner_user(goal, data_context, files)},
            ],
            response_format={"type": "json_object"},
        )

        raw = json.loads(response)
        plan = AgentPlan(
            goal_summary=raw["goal_summary"],
            steps=[PlanStep(**s) for s in raw["steps"]],
            eval_criteria=raw.get("eval_criteria", []),
        )

        self._emit("agent.plan_ready", {"steps_count": len(plan.steps), "goal_summary": plan.goal_summary})
        return plan

    async def execute(self, plan: AgentPlan, data_context: dict) -> AgentRunResult:
        step_results: list[StepResult] = []
        all_artifacts: list[str] = []

        for step in plan.steps:
            step.status = StepStatus.RUNNING
            self._emit("agent.step_started", {"step_index": step.index, "title": step.title})

            result = await self._run_step(step, data_context, all_artifacts)
            step_results.append(result)
            all_artifacts.extend(result.artifacts)

            if result.success:
                step.status = StepStatus.COMPLETED
                step.result_summary = result.summary
                self._emit("agent.step_completed", {
                    "step_index": step.index,
                    "title": step.title,
                    "summary": result.summary,
                    "artifacts": result.artifacts,
                    "metrics": result.metrics,
                })
            else:
                step.status = StepStatus.FAILED
                step.error = (result.stderr or result.stdout or f"exit_code={result.exit_code}")[-500:]
                self._emit("agent.step_failed", {
                    "step_index": step.index,
                    "title": step.title,
                    "error": step.error,
                })
                return AgentRunResult(
                    plan=plan,
                    step_results=step_results,
                    final_artifacts=all_artifacts,
                    overall_success=False,
                    failure_reason=f"Step {step.index} '{step.title}' failed: {step.error}",
                )

        self._emit("agent.execution_completed", {"artifacts": all_artifacts})
        return AgentRunResult(
            plan=plan,
            step_results=step_results,
            final_artifacts=all_artifacts,
            overall_success=True,
        )

    async def _run_step(
        self,
        step: PlanStep,
        data_context: dict,
        prev_artifacts: list[str],
    ) -> StepResult:
        code = await self._generate_code(step, data_context, prev_artifacts)

        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            exec_result = await self._sandbox.exec_python(self._session_id, code, timeout=600)

            evaluation = await self._evaluate_step(step, exec_result.stdout, exec_result.stderr, exec_result.exit_code)

            if evaluation["success"]:
                return StepResult(
                    step_index=step.index,
                    stdout=exec_result.stdout,
                    stderr=exec_result.stderr,
                    exit_code=exec_result.exit_code,
                    artifacts=evaluation.get("artifacts", []),
                    metrics=evaluation.get("metrics", {}),
                    summary=evaluation.get("summary", ""),
                    success=True,
                )

            if attempt >= MAX_REPAIR_ATTEMPTS:
                break

            self._emit("agent.step_repair_attempt", {"step_index": step.index, "attempt": attempt + 1})
            code = await self._repair_code(step, code, exec_result.stdout, exec_result.stderr)

        return StepResult(
            step_index=step.index,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            exit_code=exec_result.exit_code,
            success=False,
        )

    async def _generate_code(self, step: PlanStep, data_context: dict, prev_artifacts: list[str]) -> str:
        return await chat_completion(
            messages=[
                {"role": "system", "content": prompts.CODER_SYSTEM},
                {"role": "user", "content": prompts.coder_user(
                    step.title, step.description, step.code_hint, data_context, prev_artifacts,
                )},
            ],
            temperature=0.1,
            max_tokens=8192,
        )

    async def _evaluate_step(self, step: PlanStep, stdout: str, stderr: str, exit_code: int) -> dict:
        response = await chat_completion(
            messages=[
                {"role": "system", "content": prompts.EVALUATOR_SYSTEM},
                {"role": "user", "content": prompts.evaluator_user(
                    step.description, stdout, stderr, exit_code,
                )},
            ],
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"success": exit_code == 0, "artifacts": [], "metrics": {}, "summary": ""}

    async def _repair_code(self, step: PlanStep, code: str, stdout: str, stderr: str) -> str:
        return await chat_completion(
            messages=[
                {"role": "system", "content": prompts.REPAIR_SYSTEM},
                {"role": "user", "content": prompts.repair_user(
                    step.description, code, stdout, stderr,
                )},
            ],
            temperature=0.05,
            max_tokens=8192,
        )

    def _emit(self, event_type: str, payload: dict) -> None:
        try:
            self._on_event(event_type, payload)
        except Exception as e:
            logger.warning("Event emit failed: %s", e)
