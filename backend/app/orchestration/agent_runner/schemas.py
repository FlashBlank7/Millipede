from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    index: int
    title: str
    description: str
    code_hint: str = ""
    status: StepStatus = StepStatus.PENDING
    result_summary: str = ""
    error: str = ""


class AgentPlan(BaseModel):
    goal_summary: str
    steps: list[PlanStep]
    eval_criteria: list[str] = Field(default_factory=list)


class StepResult(BaseModel):
    step_index: int
    stdout: str
    stderr: str
    exit_code: int
    artifacts: list[str] = Field(default_factory=list)  # file paths created
    metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    success: bool = True


class AgentRunResult(BaseModel):
    plan: AgentPlan
    step_results: list[StepResult]
    final_artifacts: list[str] = Field(default_factory=list)
    overall_success: bool = True
    failure_reason: str = ""
