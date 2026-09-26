"""local-deep-research (LDR) HTTP client — optional literature augmentation.

Calls a running LDR server (https://github.com/LearningCircuit/local-deep-research)
to produce a research report from a query. Opt-in via
``literature_search.deep_research.*``; every failure is non-fatal (returns "").

Dependency isolation: this module uses only the standard library and never
imports the heavy LDR/torch stack, so it is safe to ship inside ``researchclaw``.
The LDR server must be started separately (``ldr-web``, default port 5000).
"""

from __future__ import annotations

import http.cookiejar
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from researchclaw.literature.models import Paper

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SEC = 30

# LDR engine selection by research domain. The LDR server accepts a per-request
# ``search_engine`` override, so we route each topic to an engine that fits its
# field instead of relying on a single server-side default (e.g. pubmed, which
# returns irrelevant hits for non-biomedical topics).
_ENGINE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "pubmed",
        (
            "biomed", "medic", "clinic", "health", "biolog", "genom",
            "epidemi", "oncolog", "pharma", "neuro", "cell", "immuno",
        ),
    ),
    (
        "openalex",
        (
            "social", "psycholog", "behavio", "economic", "policy",
            "environment", "sociolog", "political", "education",
            "humanities", "business", "law", "sustainab", "climate",
        ),
    ),
    (
        "arxiv",
        (
            "physics", "quantum", "astro", "math", "computer",
            "machine-learning", "machine learning", "artificial intelligence",
            "nlp", "vision", "statistic", "robotics", "deep learning",
        ),
    ),
)
_DEFAULT_ENGINE = "openalex"


def select_search_engine(domains: Any) -> str:
    """Pick an LDR search engine for *domains* (iterable of domain labels).

    Vote-based: each domain label matching an engine's keywords adds a vote;
    the engine with the most votes wins, ties resolved toward the default
    (``openalex``, all-discipline). Returns the default when nothing matches.
    """
    votes: dict[str, int] = {}
    for domain in domains or ():
        text = str(domain).lower()
        for engine, keywords in _ENGINE_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                votes[engine] = votes.get(engine, 0) + 1
    if not votes:
        return _DEFAULT_ENGINE
    return max(votes, key=lambda engine: (votes[engine], engine == _DEFAULT_ENGINE))


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _request(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = _DEFAULT_TIMEOUT_SEC,
) -> Any:
    request = urllib.request.Request(
        url, data=data, method=method, headers=headers or {}
    )
    with opener.open(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    try:
        return json.loads(body)
    except ValueError:
        return {"raw": body}


def _first(payload: Any, keys: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value)
    return ""


def deep_research_report(
    query: str,
    *,
    endpoint: str,
    username: str = "",
    password: str = "",
    strategy: str = "",
    engine: str = "",
    timeout_sec: int = 900,
    poll_sec: float = 5.0,
) -> str:
    """Return a markdown report from an LDR server, or "" on any failure.

    ``engine`` overrides the server-side search engine for this run only
    (LDR honors a per-request ``search_engine``); empty keeps the server
    default.
    """
    base = (endpoint or "").rstrip("/")
    if not base or not query.strip():
        return ""
    try:
        opener = _opener()
        csrf = _first(_request(opener, f"{base}/auth/csrf-token"), (
            "csrf_token", "token", "csrfToken",
        ))
        if username and password:
            form = urllib.parse.urlencode(
                {"username": username, "password": password, "csrf_token": csrf}
            ).encode()
            _request(
                opener,
                f"{base}/auth/login",
                method="POST",
                data=form,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRF-Token": csrf,
                },
            )
            # Login rotates the session (session-fixation defence), which
            # invalidates the pre-login token; re-fetch before /api/start_research.
            csrf = _first(_request(opener, f"{base}/auth/csrf-token"), (
                "csrf_token", "token", "csrfToken",
            ))
        payload: dict[str, object] = {"query": query}
        if strategy:
            payload["strategy"] = strategy
        if engine:
            payload["search_engine"] = engine
        started = _request(
            opener,
            f"{base}/api/start_research",
            method="POST",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
        )
        research_id = _first(started, ("research_id", "id", "researchId"))
        if not research_id:
            logger.warning("[deep-research] no research_id in start response")
            return ""

        deadline = time.time() + max(1, timeout_sec)
        while time.time() < deadline:
            status = _first(
                _request(opener, f"{base}/api/research/{research_id}/status"),
                ("status", "state"),
            ).lower()
            if status in ("completed", "complete", "done", "finished", "success"):
                break
            if status in ("failed", "error", "terminated", "cancelled"):
                logger.warning("[deep-research] run %s ended with status=%s", research_id, status)
                return ""
            time.sleep(max(1.0, poll_sec))

        report = _request(opener, f"{base}/api/report/{research_id}")
        text = _first(report, ("content", "report", "markdown", "result", "raw"))
        if text:
            logger.info("[deep-research] report for %r: %d chars", query[:60], len(text))
        return text
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        logger.warning("[deep-research] unavailable (%s) — skipping", exc)
        return ""
    except Exception as exc:  # noqa: BLE001 — never break Stage 4
        logger.warning("[deep-research] unexpected error: %s", exc)
        return ""


# Report "Sources" entries look like:
#   [3] Some paper title. [Q1 ★★★★] (source nr: 3)
#      URL: https://doi.org/10.1234/abc
_SOURCE_ENTRY_RE = re.compile(
    r"^\s*\[(\d+)\]\s*(.+?)\s*(?:\[Q[^\]]*\])?\s*(?:\(source nr:\s*\d+\))?\s*\n"
    r"\s*URL:\s*(\S+)",
    re.MULTILINE,
)
_DOI_IN_URL_RE = re.compile(r"doi\.org/(10\.\d{4,9}/[^\s>]+)")


def parse_report_sources(report: str) -> list[Paper]:
    """Extract cited sources (title + DOI/URL) from an LDR markdown report.

    Returns one ``Paper`` per unique source (deduped by DOI, else URL) with
    ``source="ldr"`` so Stage 4 can merge them into the candidate corpus.
    """
    if not report:
        return []
    papers: list[Paper] = []
    seen: set[str] = set()
    for num, raw_title, raw_url in _SOURCE_ENTRY_RE.findall(report):
        url = raw_url.strip().strip("<>")
        doi_match = _DOI_IN_URL_RE.search(url)
        doi = doi_match.group(1).rstrip(".,);") if doi_match else ""
        key = (doi or url).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        papers.append(
            Paper(
                paper_id=f"ldr-{num}",
                title=re.sub(r"\s+", " ", raw_title).strip().rstrip("."),
                doi=doi,
                url=url,
                source="ldr",
            )
        )
    return papers
