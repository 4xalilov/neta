"""Writer → Critics → AssetGen → Render → VisionQA → interrupt → Publish.

TODO (1.7, 2.2): nodelarni amalga oshirish. Har node alohida funksiya, State bilan tiplangan.
"""
from langgraph.graph import END, StateGraph

from .state import DayState

MAX_ITER = 3
PASS_SCORE = 8


def route_after_critics(state: DayState) -> str:
    scores = [r["score"] for r in state.get("reviews", [])]
    if scores and min(scores) >= PASS_SCORE:
        return "asset_gen"
    if state.get("iteration", 0) >= MAX_ITER:
        return "asset_gen"  # eng yaxshi versiya bilan davom, egaga ogohlantirish
    return "writer"


def build() -> StateGraph:
    g = StateGraph(DayState)
    # g.add_node("writer", writer)
    # g.add_node("critics", critics)        # 3 kritik parallel
    # g.add_node("asset_gen", asset_gen)    # TTS ∥ FLUX ∥ depth
    # g.add_node("render", render)
    # g.add_node("vision_qa", vision_qa)
    # g.add_node("approval", approval)      # interrupt()
    # g.add_node("publish", publish)
    # g.set_entry_point("writer")
    # g.add_conditional_edges("critics", route_after_critics)
    return g
