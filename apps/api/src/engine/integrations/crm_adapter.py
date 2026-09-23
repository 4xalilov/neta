"""Twenty CRM ustida yupqa adapter. Kodning boshqa joyi Twenty API'ni bilmaydi.

TODO (5.3): GraphQL mijoz, retry, xatolar. Testlar mock bilan.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Lead:
    id: str
    name: str
    phone: str | None
    source: str
    campaign_id: str | None
    temperature: str  # hot|warm|cold
    stage: str        # new|contacted|meeting|deal|lost
    assigned_to: str | None


class CRM(Protocol):
    async def create_lead(self, lead: Lead) -> str: ...
    async def update_stage(self, lead_id: str, stage: str) -> None: ...
    async def create_task(self, staff_id: str, title: str, due_at: str, lead_id: str | None) -> str: ...
    async def list_overdue_tasks(self) -> list[dict]: ...
    async def campaign_stats(self, campaign_id: str) -> dict: ...


class TwentyCRM:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url, self.api_key = base_url, api_key

    async def create_lead(self, lead: Lead) -> str:
        raise NotImplementedError("5.3")
