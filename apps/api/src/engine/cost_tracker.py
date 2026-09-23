"""Har LLM/TTS/FLUX chaqirig'i shu yerga yoziladi (cost_log jadvali)."""

PRICES_USD_PER_1M = {  # TODO: yangilab bor
    "gemini-2.5-flash": (0.30, 2.50),
    "claude-sonnet-5": (3.0, 15.0),
}


async def log(workspace_id: str, node: str, provider: str, tokens_in: int, tokens_out: int, usd: float) -> None:
    raise NotImplementedError
