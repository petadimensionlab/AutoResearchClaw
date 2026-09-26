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
