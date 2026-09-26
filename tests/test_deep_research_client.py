# pyright: reportPrivateUsage=false
"""Offline tests for the local-deep-research (LDR) HTTP client."""

from __future__ import annotations

import researchclaw.literature.deep_research_client as drc


def test_deep_research_report_flow(monkeypatch) -> None:
    seen: list[str] = []

    def fake_request(opener, url, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(url)
        if url.endswith("/auth/csrf-token"):
            return {"csrf_token": "c"}
        if url.endswith("/auth/login"):
            return {"ok": True}
        if url.endswith("/api/start_research"):
            return {"research_id": "r1"}
        if "/api/research/r1/status" in url:
            return {"status": "completed"}
        if "/api/report/r1" in url:
            return {"content": "# Report\nfindings"}
        return {}

    monkeypatch.setattr(drc, "_request", fake_request)
    monkeypatch.setattr(drc, "_opener", lambda: object())
    out = drc.deep_research_report(
        "q", endpoint="http://localhost:5000", username="u", password="p"
    )
    assert out == "# Report\nfindings"
    assert any("/api/start_research" in u for u in seen)


def test_deep_research_report_empty_endpoint() -> None:
    assert drc.deep_research_report("q", endpoint="") == ""


def test_deep_research_report_unreachable(monkeypatch) -> None:
    def boom() -> object:
        raise OSError("connection refused")

    monkeypatch.setattr(drc, "_opener", boom)
    assert drc.deep_research_report("q", endpoint="http://localhost:5000") == ""


def test_deep_research_report_no_research_id(monkeypatch) -> None:
    monkeypatch.setattr(drc, "_request", lambda *a, **k: {"csrf_token": "c"})
    monkeypatch.setattr(drc, "_opener", lambda: object())
    assert drc.deep_research_report("q", endpoint="http://x") == ""


def test_deep_research_failed_status(monkeypatch) -> None:
    def fake_request(opener, url, **kwargs):  # type: ignore[no-untyped-def]
        if url.endswith("/api/start_research"):
            return {"research_id": "r1"}
        if "/status" in url:
            return {"status": "failed"}
        return {"csrf_token": "c"}

    monkeypatch.setattr(drc, "_request", fake_request)
    monkeypatch.setattr(drc, "_opener", lambda: object())
    assert drc.deep_research_report("q", endpoint="http://x") == ""


def test_select_search_engine_routes_by_domain() -> None:
    assert drc.select_search_engine(("biology", "immunology")) == "pubmed"
    assert (
        drc.select_search_engine(
            (
                "machine-learning",
                "computational-social-science",
                "behavioral-science",
                "environmental-behavior",
            )
        )
        == "openalex"
    )
    assert drc.select_search_engine(("quantum-physics",)) == "arxiv"
    assert drc.select_search_engine(()) == "openalex"
    assert drc.select_search_engine(("misc-topic",)) == "openalex"


def _capture_start_payload(monkeypatch, **kwargs):  # type: ignore[no-untyped-def]
    import json as _json

    payloads: list[dict] = []

    def fake_request(opener, url, **kw):  # type: ignore[no-untyped-def]
        if url.endswith("/api/start_research"):
            payloads.append(_json.loads(kw["data"].decode()))
            return {"research_id": "r1"}
        if url.endswith("/auth/csrf-token"):
            return {"csrf_token": "c"}
        if "/status" in url:
            return {"status": "completed"}
        if "/api/report/r1" in url:
            return {"content": "ok"}
        return {}

    monkeypatch.setattr(drc, "_request", fake_request)
    monkeypatch.setattr(drc, "_opener", lambda: object())
    drc.deep_research_report("q", endpoint="http://x", **kwargs)
    return payloads


def test_deep_research_report_sends_search_engine(monkeypatch) -> None:
    payloads = _capture_start_payload(monkeypatch, engine="openalex")
    assert payloads and payloads[0].get("search_engine") == "openalex"


def test_deep_research_report_omits_blank_engine(monkeypatch) -> None:
    payloads = _capture_start_payload(monkeypatch)
    assert payloads and "search_engine" not in payloads[0]


_REPORT = """\
# Report

Some synthesis with a citation [[1]](https://doi.org/10.1371/journal.pone.0226071).

## Sources

[1] Elevation, an emotion for prosocial contagion. [Q1 ★★★★] (source nr: 1)
   URL: https://doi.org/10.1371/journal.pone.0226071

[2] Vaccination as a social contract. [Q2 ★★★★★] (source nr: 2)
   URL: https://pubmed.ncbi.nlm.nih.gov/32576113/

[3] Same paper again. [Q1 ★★★★] (source nr: 1)
   URL: https://doi.org/10.1371/journal.pone.0226071
"""


def test_parse_report_sources_extracts_and_dedupes() -> None:
    papers = drc.parse_report_sources(_REPORT)
    assert len(papers) == 2
    first = papers[0]
    assert first.doi == "10.1371/journal.pone.0226071"
    assert first.url == "https://doi.org/10.1371/journal.pone.0226071"
    assert first.source == "ldr"
    assert "prosocial contagion" in first.title
    second = papers[1]
    assert second.doi == ""
    assert second.url == "https://pubmed.ncbi.nlm.nih.gov/32576113/"


def test_parse_report_sources_empty() -> None:
    assert drc.parse_report_sources("") == []
