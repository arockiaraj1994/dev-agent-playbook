"""
cache.py - Boot-cached or TTL-reloaded corpus.

Standards stay boot-cached (change weekly, CI-gated). Requirements pay a TTL
cost so PM edits show up without a server restart. Reload is atomic (swap,
never mutate) and single-flight under an asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from corpus import CorpusSpec
from loader import RuleDoc, parse_corpus

logger = logging.getLogger(__name__)


class CorpusCache:
    """Boot-cached or TTL-reloaded corpus. Reload is atomic (swap, never mutate)."""

    def __init__(
        self,
        spec: CorpusSpec,
        *,
        on_reload: Callable[[str, list[RuleDoc]], None] | None = None,
    ) -> None:
        self._spec = spec
        self._docs: list[RuleDoc] = []
        self._loaded_at: float = 0.0
        self._lock = asyncio.Lock()
        self._on_reload = on_reload

    @property
    def spec(self) -> CorpusSpec:
        return self._spec

    def load_sync(self) -> list[RuleDoc]:
        """Synchronous initial load (used at server startup)."""
        self._docs = parse_corpus(self._spec)
        self._loaded_at = time.monotonic()
        logger.info(
            "CorpusCache[%s] loaded %d docs (policy=%s).",
            self._spec.name,
            len(self._docs),
            self._spec.cache_policy,
        )
        return self._docs

    def snapshot(self) -> list[RuleDoc]:
        """Return the current docs without triggering a reload."""
        return self._docs

    async def docs(self) -> list[RuleDoc]:
        if self._spec.cache_policy == "boot":
            return self._docs
        if self._spec.ttl_seconds <= 0:
            return self._docs
        if time.monotonic() - self._loaded_at < self._spec.ttl_seconds:
            return self._docs
        async with self._lock:  # single-flight
            if time.monotonic() - self._loaded_at < self._spec.ttl_seconds:
                return self._docs  # lost the race, someone else reloaded
            fresh = await asyncio.to_thread(parse_corpus, self._spec)
            self._docs = fresh  # atomic swap
            self._loaded_at = time.monotonic()
            logger.info(
                "CorpusCache[%s] reloaded %d docs.",
                self._spec.name,
                len(fresh),
            )
            if self._on_reload is not None:
                self._on_reload(self._spec.name, fresh)
            return self._docs

    async def force_reload(self) -> list[RuleDoc]:
        """Manual override (dashboard POST /reload)."""
        async with self._lock:
            fresh = await asyncio.to_thread(parse_corpus, self._spec)
            self._docs = fresh
            self._loaded_at = time.monotonic()
            logger.info(
                "CorpusCache[%s] force-reloaded %d docs.",
                self._spec.name,
                len(fresh),
            )
            if self._on_reload is not None:
                self._on_reload(self._spec.name, fresh)
            return self._docs
