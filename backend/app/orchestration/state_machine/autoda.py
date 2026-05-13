"""
AutoDA state machine (Phase 1: L1 channel only).

L1 flow (no intermediate reviews):
  DRAFT → REQ_READY → PRE_ANALYZING → PREPROCESSING → DA_PLANNING
        → DATA_ANALYZING → AWAIT_REVIEW_DA_REPORT → AWAIT_DISPATCH_DA_REPORT
        → PACKAGING → DELIVERED

L2/L3 (placeholder, fully implemented in Phase 2):
  Adds AWAIT_REVIEW/AWAIT_DISPATCH nodes after each processing stage.
"""

from transitions import Machine

AUTODA_STATES_L1 = [
    "DRAFT",
    "REQ_READY",
    "PRE_ANALYZING",
    "PREPROCESSING",
    "DA_PLANNING",
    "DATA_ANALYZING",
    "AWAIT_REVIEW_DA_REPORT",
    "AWAIT_DISPATCH_DA_REPORT",
    "PACKAGING",
    "DELIVERED",
    "FAILED",
    "PAUSED",
]

AUTODA_TRANSITIONS_L1 = [
    {"trigger": "confirm_requirement", "source": "DRAFT", "dest": "REQ_READY"},
    {"trigger": "start_analysis", "source": "REQ_READY", "dest": "PRE_ANALYZING"},
    {"trigger": "finish_pre_analysis", "source": "PRE_ANALYZING", "dest": "PREPROCESSING"},
    {"trigger": "finish_preprocessing", "source": "PREPROCESSING", "dest": "DA_PLANNING"},
    {"trigger": "finish_da_planning", "source": "DA_PLANNING", "dest": "DATA_ANALYZING"},
    {"trigger": "finish_data_analyzing", "source": "DATA_ANALYZING", "dest": "AWAIT_REVIEW_DA_REPORT"},
    {"trigger": "dispatch_report", "source": "AWAIT_REVIEW_DA_REPORT", "dest": "AWAIT_DISPATCH_DA_REPORT"},
    {"trigger": "confirm_dispatch", "source": "AWAIT_DISPATCH_DA_REPORT", "dest": "PACKAGING"},
    {"trigger": "finish_packaging", "source": "PACKAGING", "dest": "DELIVERED"},
    {"trigger": "fail", "source": "*", "dest": "FAILED"},
]

# L2/L3 adds intermediate review nodes — same state machine, extended transitions
AUTODA_STATES_L2 = AUTODA_STATES_L1 + [
    "AWAIT_REVIEW_PRE_PLAN",
    "AWAIT_DISPATCH_PRE_PLAN",
    "AWAIT_REVIEW_PRE_OUTPUT",
    "AWAIT_DISPATCH_PRE_OUTPUT",
    "AWAIT_REVIEW_DA_PLAN",
    "AWAIT_DISPATCH_DA_PLAN",
]


class AutoDAStateMachine:
    """
    Wraps `transitions.Machine`. Stateless — state is stored in RunCard.current_state.
    Instantiate with the current state, call trigger methods, read `.state` for new state.
    """

    def __init__(self, initial_state: str, task_level: str = "L1"):
        states = AUTODA_STATES_L1 if task_level == "L1" else AUTODA_STATES_L2
        transitions = AUTODA_TRANSITIONS_L1  # Phase 2 will extend for L2/L3

        self.machine = Machine(
            model=self,
            states=states,
            transitions=transitions,
            initial=initial_state,
            model_attribute="_sm_state",
            ignore_invalid_triggers=False,
            auto_transitions=False,
        )

    @property
    def state(self) -> str:
        return self._sm_state

    def is_executing(self) -> bool:
        return self.state.endswith("ING") or self.state == "REQ_READY"

    def is_awaiting_review(self) -> bool:
        return self.state.startswith("AWAIT_REVIEW")

    def is_awaiting_dispatch(self) -> bool:
        return self.state.startswith("AWAIT_DISPATCH")
