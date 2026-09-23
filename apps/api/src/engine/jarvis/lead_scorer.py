"""LeadScorer: yangi lidni baholaydi — issiq/iliq/sovuq, 0-100 ball, sabab, keyingi qadam.

LLM: ``engine.llm.complete_json`` tier ``"draft"`` (arzon/tez model — docs/03 5.4, docs/04
jadvali: "LeadScorer ... autonomous"). Prompt: ``agents/prompts/jarvis_lead_scorer.md``.
Natija CRM'ga ``crm.update_lead_score`` orqali yoziladi va shu bilan birga qaytariladi,
shunda supervisor uni ``jarvis_action.payload`` ichiga yozib, egaga ko'rsata oladi.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from engine import llm
from engine.integrations.crm_adapter import CRM

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "agents" / "prompts" / "jarvis_lead_scorer.md"
)

_TEMPERATURES = ("hot", "warm", "cold")


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


async def score_lead(crm: CRM, lead_id: str, *, workspace_id: str = "") -> dict:
    """Lidni CRM'dan o'qiydi, LLM bilan baholaydi, CRM'ga yozadi.

    Qaytadi: ``{"temperature": "hot"|"warm"|"cold", "score": 0-100, "reason": str,
    "next_step": str}``.
    """
    lead = await crm.get_lead(lead_id)
    if lead is None:
        raise ValueError(f"lead_scorer: lid topilmadi: {lead_id!r}")

    system = _load_prompt()
    user = json.dumps(
        {
            "name": lead.name,
            "phone": lead.phone,
            "ig_handle": lead.ig_handle,
            "source": lead.source,
            "campaign_id": lead.campaign_id,
            "stage": lead.stage,
        },
        ensure_ascii=False,
    )

    raw = await llm.complete_json(
        "draft", system, user, node="jarvis.lead_scorer", workspace_id=workspace_id
    )

    temperature = raw.get("temperature", "warm")
    if temperature not in _TEMPERATURES:
        logger.warning("lead_scorer: noma'lum temperature %r, 'warm' qo'yildi", temperature)
        temperature = "warm"

    try:
        score = max(0, min(100, int(raw.get("score", 50))))
    except (TypeError, ValueError):
        score = 50

    reason = str(raw.get("reason", ""))
    next_step = str(raw.get("next_step", ""))

    await crm.update_lead_score(lead_id, temperature, score)
    await crm.log_activity(lead_id, f"Jarvis baholadi: {temperature} ({score}). {reason}".strip())

    return {"temperature": temperature, "score": score, "reason": reason, "next_step": next_step}
