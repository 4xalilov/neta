"""Jarvis harakat darajalari. docs/06-jarvis-crm.md bilan sinxron saqla."""
from enum import StrEnum


class Level(StrEnum):
    AUTONOMOUS = "autonomous"
    REQUIRES_APPROVAL = "requires_approval"


LEVELS: dict[str, Level] = {
    "send_report": Level.AUTONOMOUS,
    "assign_task": Level.AUTONOMOUS,
    "remind_staff": Level.AUTONOMOUS,
    "escalate_owner": Level.AUTONOMOUS,
    "message_lead": Level.REQUIRES_APPROVAL,
    "call_lead": Level.REQUIRES_APPROVAL,
    "change_deal": Level.REQUIRES_APPROVAL,
}

DEFAULT_SLA_HOURS = {"hot": 2, "warm": 24, "cold": 72}


def level_for(action_type: str) -> Level:
    return LEVELS.get(action_type, Level.REQUIRES_APPROVAL)
