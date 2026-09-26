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
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SEC = 30


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
    timeout_sec: int = 900,
    poll_sec: float = 5.0,
) -> str:
    """Return a markdown report from an LDR server, or "" on any failure."""
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
        payload: dict[str, object] = {"query": query}
        if strategy:
            payload["strategy"] = strategy
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
