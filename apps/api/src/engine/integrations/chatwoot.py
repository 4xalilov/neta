"""Chatwoot inbox: webhook qabul (message_created) va javob yuborish.

TODO (5.3): imzo tekshiruvi, contact ↔ lead (crm_link), reply API.
"""


async def handle_webhook(payload: dict) -> None:
    raise NotImplementedError("5.3")


async def reply(conversation_id: int, text: str) -> None:
    raise NotImplementedError("5.3")
