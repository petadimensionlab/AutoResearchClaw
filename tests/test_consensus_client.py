# pyright: reportPrivateUsage=false
"""Offline tests for the Consensus.app literature backend."""

from __future__ import annotations

import researchclaw.literature.consensus_client as cc
import researchclaw.literature.search as search_mod
from researchclaw.literature.models import Paper


def test_parse_consensus_paper_maps_fields() -> None:
    paper = cc._parse_consensus_paper(
        {
            "title": "Infectious Generosity",
            "authors": ["Ada Lovelace", "Alan Turing"],
            "doi": "https://doi.org/10.1234/xyz",
            "publish_year": 2024,
            "citation_count": 42,
            "abstract": "An abstract.",
            "journal_name": "Nature",
            "url": "https://consensus.app/papers/xyz",
        }
    )
    assert isinstance(paper, Paper)
    assert paper.source == "consensus"
    assert paper.title == "Infectious Generosity"
    assert paper.doi == "10.1234/xyz"
    assert paper.year == 2024
    assert paper.citation_count == 42
    assert [a.name for a in paper.authors] == ["Ada Lovelace", "Alan Turing"]


def test_parse_consensus_paper_falls_back_to_takeaway() -> None:
    paper = cc._parse_consensus_paper({"title": "T", "takeaway": "Short summary"})
    assert paper is not None
    assert paper.abstract == "Short summary"


def test_search_consensus_without_key_returns_empty(monkeypatch) -> None:
    called = {"n": 0}

    def _boom(*args: object, **kwargs: object) -> object:
        called["n"] += 1
        raise AssertionError("must not perform a network call without a key")

    monkeypatch.setattr(cc, "_request_with_retry", _boom)
    assert cc.search_consensus("query", api_key="") == []
    assert called["n"] == 0


def test_search_consensus_parses_results(monkeypatch) -> None:
    payload = {
        "results": [
            {"title": "A", "doi": "10.1/a", "publish_year": 2023},
            {"title": "B", "doi": "10.1/b", "citation_count": 3},
            {"no_title": True},
        ]
    }
    monkeypatch.setattr(cc, "_request_with_retry", lambda url, key: payload)
    papers = cc.search_consensus("q", limit=10, api_key="k")
    assert [p.title for p in papers] == ["A", "B"]
    assert all(p.source == "consensus" for p in papers)


def test_search_papers_dispatches_to_consensus(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_consensus(query: str, **kwargs: object) -> list[Paper]:
        captured["query"] = query
        captured.update(kwargs)
        return [Paper(paper_id="consensus-1", title="T", source="consensus")]

    monkeypatch.setattr(search_mod, "search_consensus", _fake_consensus)
    # Avoid cache/network side effects for the other sources.
    monkeypatch.setattr(
        search_mod,
        "_cache_api",
        lambda: (lambda *a, **k: None, lambda *a, **k: None),
    )
    papers = search_mod.search_papers(
        "q", limit=5, sources=["consensus"], consensus_api_key="secret"
    )
    assert captured["api_key"] == "secret"
    assert [p.source for p in papers] == ["consensus"]
