PLANNER_SYSTEM = """You are an expert data scientist and ML engineer. Given a goal and data context, produce a structured execution plan.

Output ONLY valid JSON matching this schema:
{
  "goal_summary": "one-sentence restatement of the goal",
  "steps": [
    {
      "index": 0,
      "title": "short step title",
      "description": "what this step does and why",
      "code_hint": "key libraries or approach to use"
    }
  ],
  "eval_criteria": ["criterion 1", "criterion 2"]
}

Rules:
- Steps must be atomic, sequential, and executable as Python scripts
- Each step produces or transforms artifacts in /workspace/
- Final step must write the primary deliverable to /workspace/outputs/
- Raw input data lives in /workspace/inputs/ — reference it directly
- Use only standard scientific Python libraries (pandas, numpy, scikit-learn, matplotlib, seaborn, scipy, statsmodels)
- Steps must only reference files produced by earlier steps listed in "available artifacts"
"""

CODER_SYSTEM = """You are an expert Python data scientist. Write clean, executable Python code for the given step.

Output ONLY a raw Python script. No markdown fences, no explanations.

Rules:
- All file I/O uses paths under /workspace/ (inputs/, processing/, models/, reports/, outputs/)
- Raw input data is ALWAYS in /workspace/inputs/ — never assume cleaned files exist unless they are listed in "Previously produced artifacts"
- Print progress and key metrics to stdout
- On error, print the traceback and exit with code 1
- Save artifacts to appropriate subdirectory; create parent directories with os.makedirs(..., exist_ok=True)
- Code must be self-contained and runnable with python script.py
"""

EVALUATOR_SYSTEM = """You are reviewing the output of a data science execution step.

Given the step description, stdout/stderr, and exit code, determine:
1. Did the step succeed?
2. What artifacts were produced?
3. What metrics were observed?
4. A one-sentence summary.

Output ONLY valid JSON:
{
  "success": true,
  "artifacts": ["list of file paths mentioned in output"],
  "metrics": {"key": "value"},
  "summary": "one sentence"
}
"""

REPAIR_SYSTEM = """You are an expert Python debugger. A data science script failed. Fix it.

Output ONLY the corrected Python script. No markdown fences, no explanations.
"""


def planner_user(goal: str, data_context: dict, available_files: list[str]) -> str:
    return f"""Goal: {goal}

Data context:
{_fmt_dict(data_context)}

Available input files:
{chr(10).join(available_files) if available_files else "none"}

Produce a step-by-step execution plan."""


def coder_user(step_title: str, step_description: str, code_hint: str, data_context: dict, prev_artifacts: list[str]) -> str:
    return f"""Step: {step_title}
Description: {step_description}
Code hint: {code_hint}

Data context:
{_fmt_dict(data_context)}

Previously produced artifacts:
{chr(10).join(prev_artifacts) if prev_artifacts else "none"}

Write the Python script for this step."""


def evaluator_user(step_description: str, stdout: str, stderr: str, exit_code: int) -> str:
    return f"""Step description: {step_description}

Exit code: {exit_code}
Stdout (last 2000 chars):
{stdout[-2000:]}

Stderr (last 1000 chars):
{stderr[-1000:]}

Evaluate the result."""


def repair_user(step_description: str, code: str, stdout: str, stderr: str) -> str:
    return f"""Step description: {step_description}

Failed script:
{code}

Stdout:
{stdout[-1000:]}

Stderr:
{stderr[-1000:]}

Fix the script."""


def _fmt_dict(d: dict) -> str:
    if not d:
        return "{}"
    lines = []
    for k, v in d.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)
