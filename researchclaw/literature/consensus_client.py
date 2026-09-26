"""Consensus.app API client.

Uses stdlib ``urllib`` + ``json`` — zero extra dependencies.

Public API
----------
- ``search_consensus(query, limit, year_min, api_key)`` → ``list[Paper]``

Constraints (see https://docs.consensus.app):
- Auth: ``x-api-key`` header.
- **1 request/second** per account; faster requests get HTTP 429.
- Billing is 1 call per 100 papers returned, so a large ``page_size`` is
  cheaper per paper.

The API returns abstracts, DOIs and citation counts, so results map cleanly
onto the shared :class:`~researchclaw.literature.models.Paper` model.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from researchclaw.literature.models import Author, Paper

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.consensus.app/v1/search"
_MAX_PER_REQUEST = 100
_TIMEOUT_SEC = 20
_RATE_LIMIT_SEC = 1.0  # hard 1 req/s limit
_MAX_RETRIES = 3
_MAX_WAIT_SEC = 60

_last_request_time: float = 0.0
_rate_lock = threading.Lock()


def _throttle() -> None:
    global _last_request_time
    with _rate_lock:
        wait = _RATE_LIMIT_SEC - (time.monotonic() - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.monotonic()


def _request_with_retry(url: str, api_key: str) -> Any:
    for attempt in range(1, _MAX_RETRIES + 1):
        _throttle()
        request = urllib.request.Request(url, headers={"x-api-key": api_key})
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SEC) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
            return data if isinstance(data, dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 402, 403):
                logger.warning(
                    "[consensus] HTTP %s (auth/plan/feature) — skipping", exc.code
                )
                return None
            if exc.code == 429 and attempt < _MAX_RETRIES:
                try:
                    retry_after = float(exc.headers.get("retry-after") or 0)
                except (TypeError, ValueError):
                    retry_after = 0.0
                wait = min(retry_after or 2.0 ** attempt, _MAX_WAIT_SEC)
                logger.warning(
                    "[consensus] 429 rate limited — waiting %.1fs (attempt %d/%d)",
                    wait, attempt, _MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            logger.warning("[consensus] HTTP %s — giving up", exc.code)
            return None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if attempt < _MAX_RETRIES:
                time.sleep(2.0 ** attempt)
                continue
            logger.warning("[consensus] request failed: %s", exc)
            return None
    return None


def _parse_consensus_paper(item: Any) -> Paper | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    authors = tuple(
        Author(name=str(name).strip())
        for name in (item.get("authors") or [])
        if str(name).strip()
    )
    doi = str(item.get("doi") or "").strip()
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    url = str(item.get("url") or "").strip() or (f"https://doi.org/{doi}" if doi else "")
    abstract = str(item.get("abstract") or item.get("takeaway") or "").strip()
    venue = str(item.get("journal_name") or item.get("publisher_name") or "").strip()
    try:
        year = int(item.get("publish_year") or 0)
    except (TypeError, ValueError):
        year = 0
    try:
        citation_count = int(item.get("citation_count") or 0)
    except (TypeError, ValueError):
        citation_count = 0
    paper_id = f"consensus-{doi}" if doi else f"consensus-{abs(hash(title)) & 0xFFFFFF:06x}"
    return Paper(
        paper_id=paper_id,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        venue=venue,
        citation_count=citation_count,
        doi=doi,
        arxiv_id="",
        url=url,
        source="consensus",
    )


def search_consensus(
    query: str,
    *,
    limit: int = 20,
    year_min: int = 0,
    api_key: str = "",
) -> list[Paper]:
    """Search Consensus for papers matching *query*.

    Returns an empty list when the key is missing or the request fails, so the
    multi-source search can fall back to other backends.
    """
    if not api_key:
        logger.warning("[consensus] no API key configured — skipping")
        return []
    if not query.strip():
        return []

    page_size = max(1, min(int(limit), _MAX_PER_REQUEST))
    params: dict[str, object] = {"query": query, "page": 0, "page_size": page_size}
    if year_min:
        params["year_min"] = int(year_min)
    url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"

    payload = _request_with_retry(url, api_key)
    if payload is None:
        return []
    results = payload.get("results") or []
    papers: list[Paper] = []
    for item in results if isinstance(results, list) else []:
        if isinstance(item, dict):
            paper = _parse_consensus_paper(item)
            if paper is not None:
                papers.append(paper)
    logger.info("[consensus] %d results for %r", len(papers), query[:60])
    return papers
