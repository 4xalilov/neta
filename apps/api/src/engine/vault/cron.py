"""arq cron ishi: vaultni davriy qayta indekslash (docs/10, roadmap 3.6).

``engine.worker.WorkerSettings.cron_jobs`` ro'yxatiga arq ``cron()`` bilan
qo'shiladi (worker.py — boshqa agent egaligida, shu yerda faqat funksiya
ta'riflanadi). Masalan::

    from arq import cron
    from engine.vault.cron import reindex_job

    class WorkerSettings:
        cron_jobs = [cron(reindex_job, minute=set(range(0, 60, settings.vault_reindex_minutes)))]
"""

from __future__ import annotations

import logging
from typing import Any

from engine.db import async_session
from engine.settings import settings
from engine.vault.indexer import reindex

logger = logging.getLogger(__name__)

__all__ = ["reindex_job"]


async def reindex_job(ctx: dict[str, Any]) -> dict[str, int]:
    """arq cron entrypoint: ``settings.vault_dir`` ni qayta indekslaydi."""
    report = await reindex(async_session, settings.vault_dir)
    logger.info(
        "vault reindex: +%d ~%d -%d =%d",
        report.added,
        report.updated,
        report.removed,
        report.unchanged,
    )
    return {
        "added": report.added,
        "updated": report.updated,
        "removed": report.removed,
        "unchanged": report.unchanged,
    }
