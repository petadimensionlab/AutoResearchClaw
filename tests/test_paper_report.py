# pyright: reportPrivateUsage=false
"""Offline tests for researchclaw.paper.report parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from researchclaw.paper import AnalysisReport, load_analysis_report

_SAMPLE = """# Scaling Laws for Sparse Attention

## Abstract

We study sparse attention and report consistent accuracy gains across scales.

Keywords: sparse attention, scaling laws, transformers

## Introduction

Sparse attention reduces cost while accuracy remains high.

## Findings

Results improve monotonically with scale.

| Metric | Baseline | Sparse |
|--------|----------|--------|
| accuracy | 0.81 | 0.90 |
| perplexity | 12.50 | 9.75 |
| speedup | n/a | 2.40 |

```bibtex
@article{doe2026sparse,
  title={Sparse Attention},
  author={Doe, Jane},
  year={2026}
}
```

## Conclusion

Sparse attention is effective.
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "report.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_title_is_first_h1(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    assert report.title == "Scaling Laws for Sparse Attention"


def test_title_defaults_when_no_h1(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, "## Only a section\n\ntext\n"))
    assert report.title == "Untitled Analysis Report"


def test_abstract_from_abstract_heading(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    assert report.abstract.startswith("We study sparse attention")
    assert "Keywords" not in report.abstract


def test_abstract_falls_back_to_first_paragraph(tmp_path: Path) -> None:
    text = "# T\n\nThis is the lead paragraph.\n\nSecond paragraph.\n"
    report = load_analysis_report(_write(tmp_path, text))
    assert report.abstract == "This is the lead paragraph."


def test_sections_collected_from_headings(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    headings = [heading for heading, _ in report.sections]
    assert headings == ["Abstract", "Introduction", "Findings", "Conclusion"]
    findings = dict(report.sections)["Findings"]
    assert "monotonically" in findings


def test_keywords_parsed(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    assert report.keywords == ("sparse attention", "scaling laws", "transformers")


def test_metrics_from_pipe_table_first_numeric_column(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    metrics = dict(report.metrics)
    assert metrics["accuracy"] == pytest.approx(0.81)
    assert metrics["perplexity"] == pytest.approx(12.50)
    # "speedup" row has no numeric value in the first value column ("n/a").
    assert metrics["speedup"] == pytest.approx(2.40)


def test_numeric_values_include_metric_values_and_dedupe(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    values = list(report.numeric_values)
    assert 0.81 in values
    assert 12.50 in values
    assert 2.40 in values
    # Deduplicated.
    assert len(values) == len(set(values))


def test_numeric_values_ignore_word_embedded_tokens(tmp_path: Path) -> None:
    report = load_analysis_report(
        _write(tmp_path, "# T\n\nmodel v2alpha123beta is referenced.\n")
    )
    assert 2.0 not in report.numeric_values
    assert 123.0 not in report.numeric_values


def test_embedded_bib_extracted(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    assert "doe2026sparse" in report.embedded_bib
    assert report.embedded_bib.startswith("@article")


def test_body_is_full_markdown(tmp_path: Path) -> None:
    report = load_analysis_report(_write(tmp_path, _SAMPLE))
    assert report.body.startswith("# Scaling Laws")
    assert "## Conclusion" in report.body


def test_source_path_is_path_instance(tmp_path: Path) -> None:
    path = _write(tmp_path, _SAMPLE)
    report = load_analysis_report(path)
    assert isinstance(report, AnalysisReport)
    assert report.source_path == path


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_analysis_report(tmp_path / "does-not-exist.md")
