"""DaySubgraph: Writer → [UzCritic ∥ BrandCritic ∥ HookCritic] → collect → (halqa) →
AssetGen → Render → VisionQA → interrupt (Approval) → Publish.

::

    START → writer ─┬─ uz_critic ────┐
                    ├─ brand_critic ─┼─→ collect ─(route_after_critics)─┬─→ writer (score<8, iter<3)
                    └─ hook_critic ──┘                                  └─→ asset_gen
    asset_gen → render → vision_qa → approval ⟂interrupt⟂ ─(route_after_approval)─┬─→ publish → END
                                                                                  └─→ END (reject)

Checkpointer: ``settings.langgraph_checkpointer`` — ``"postgres"`` (AsyncPostgresSaver,
``langgraph-checkpoint-postgres``) yoki ``"memory"`` (MemorySaver, dev/test; resume faqat
shu jarayonda ishlaydi).
"""
from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from engine.settings import settings

from .nodes import (
    approval,
    asset_gen,
    brand_critic,
    collect,
    hook_critic,
    publish,
    render,
    uz_critic,
    vision_qa,
    writer,
)
from .nodes.approval import route_after_approval
from .nodes.critics import MAX_ITER, PASS_SCORE
from .state import DayState

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_ITER",
    "PASS_SCORE",
    "build",
    "close_graph",
    "compile",
    "compile_graph",
    "get_graph",
    "postgres_conn_string",
    "route_after_critics",
]

CRITIC_NODES = ("uz_critic", "brand_critic", "hook_critic")


def route_after_critics(state: DayState) -> str:
    scores = [r["score"] for r in state.get("reviews", [])]
    if scores and min(scores) >= PASS_SCORE:
        return "asset_gen"
    if state.get("iteration", 0) >= MAX_ITER:
        return "asset_gen"  # eng yaxshi versiya bilan davom (collect ogohlantirish yozadi)
    return "writer"


def build() -> StateGraph:
    g = StateGraph(DayState)
    g.add_node("writer", writer)
    g.add_node("uz_critic", uz_critic)
    g.add_node("brand_critic", brand_critic)
    g.add_node("hook_critic", hook_critic)
    g.add_node("collect", collect)
    g.add_node("asset_gen", asset_gen)
    g.add_node("render", render)
    g.add_node("vision_qa", vision_qa)
    g.add_node("approval", approval)
    g.add_node("publish", publish)

    g.add_edge(START, "writer")
    for name in CRITIC_NODES:
        g.add_edge("writer", name)          # fan-out
    g.add_edge(list(CRITIC_NODES), "collect")  # join: uchala kritik tugagach
    g.add_conditional_edges("collect", route_after_critics,
                            {"writer": "writer", "asset_gen": "asset_gen"})
    g.add_edge("asset_gen", "render")
    g.add_edge("render", "vision_qa")
    g.add_edge("vision_qa", "approval")
    g.add_conditional_edges("approval", route_after_approval,
                            {"publish": "publish", END: END})
    g.add_edge("publish", END)
    return g


def compile_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    """``build().compile(checkpointer)``; ``None`` → yangi ``MemorySaver``."""
    return build().compile(checkpointer=checkpointer or MemorySaver())


compile = compile_graph  # topshiriqdagi nom (builtin compile'ni faqat shu modulda yopadi)


def postgres_conn_string(database_url: str | None = None) -> str:
    """SQLAlchemy URL → psycopg URL (``postgresql+asyncpg://`` → ``postgresql://``)."""
    url = database_url or settings.database_url
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


_graph: Any = None
_saver_cm: AbstractAsyncContextManager | None = None


async def get_graph() -> Any:
    """Jarayon bo'yicha bitta kompilyatsiya qilingan graf (checkpointer bilan)."""
    global _graph, _saver_cm
    if _graph is not None:
        return _graph
    if settings.langgraph_checkpointer == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _saver_cm = AsyncPostgresSaver.from_conn_string(postgres_conn_string())
        saver = await _saver_cm.__aenter__()
        await saver.setup()
        _graph = compile_graph(saver)
    else:
        _graph = compile_graph(MemorySaver())
    return _graph


async def close_graph() -> None:
    global _graph, _saver_cm
    if _saver_cm is not None:
        await _saver_cm.__aexit__(None, None, None)
    _graph = None
    _saver_cm = None
