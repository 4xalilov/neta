"""Vault indekslovchi paketi (docs/10-obsidian-vault.md, roadmap 3.6-3.7)."""

from engine.vault.indexer import graph_snapshot, load_for_prompt, reindex, search

__all__ = ["graph_snapshot", "load_for_prompt", "reindex", "search"]
