# pyright: reportPrivateUsage=false
"""Offline tests for researchclaw.paper.seed."""

from __future__ import annotations

import json
from pathlib import Path

from researchclaw.paper import load_analysis_report
from researchclaw.paper.seed import SeedResult, seed_run_dir
from researchclaw.pipeline.stage_impls._review_publish import (
    _collect_real_metric_values,
)

_REPORT = """# Sparse Attention Results

## Abstract

We report accuracy improvements.

Keywords: sparse, attention

## Findings

| Metric | Baseline | Ours |
|--------|----------|------|
| accuracy | 0.81 | 0.90 |
| perplexity | 12.50 | 9.75 |

```bibtex
@article{doe2026sparse,
  title={Sparse Attention}
}
```
"""


def _seed(tmp_path: Path) -> tuple[SeedResult, Path]:
    report_path = tmp_path / "report.md"
    report_path.write_text(_REPORT, encoding="utf-8")
    report = load_analysis_report(report_path)
    run_dir = tmp_path / "run"
    result = seed_run_dir(
        run_dir, report, topic="Sparse attention", authors="Jane Doe"
    )
    return result, run_dir


def test_seed_writes_required_artifacts(tmp_path: Path) -> None:
    result, run_dir = _seed(tmp_path)
    assert (run_dir / "stage-14" / "analysis.md").is_file()
    assert (run_dir / "analysis_best.md").is_file()
    assert (run_dir / "stage-15" / "decision.md").is_file()
    assert (run_dir / "stage-14" / "experiment_summary.json").is_file()
    assert (run_dir / "experiment_summary_best.json").is_file()
    assert result.metrics_registered == 2


def test_analysis_matches_report_body_verbatim(tmp_path: Path) -> None:
    _, run_dir = _seed(tmp_path)
    analysis = (run_dir / "stage-14" / "analysis.md").read_text(encoding="utf-8")
    best = (run_dir / "analysis_best.md").read_text(encoding="utf-8")
    assert analysis == best
    assert "Sparse Attention Results" in analysis


def test_decision_contains_proceed(tmp_path: Path) -> None:
    _, run_dir = _seed(tmp_path)
    decision = (run_dir / "stage-15" / "decision.md").read_text(encoding="utf-8")
    assert "PROCEED" in decision


def test_experiment_summary_shape(tmp_path: Path) -> None:
    _, run_dir = _seed(tmp_path)
    summary = json.loads(
        (run_dir / "stage-14" / "experiment_summary.json").read_text(encoding="utf-8")
    )
    best = json.loads(
        (run_dir / "experiment_summary_best.json").read_text(encoding="utf-8")
    )
    assert summary == best
    assert summary["condition_summaries"], "condition_summaries must be non-empty"
    assert summary["metrics_summary"], "metrics_summary must be non-empty"
    assert summary["best_run"]["metrics"], "best_run.metrics must be non-empty"
    assert summary["best_run"]["status"] == "completed"
    assert summary["total_conditions"] >= 1
    assert summary["latex_table"]


def test_report_numbers_are_grounded(tmp_path: Path) -> None:
    """Stage 20's grounding helper must see the report's own numbers."""
    _, run_dir = _seed(tmp_path)
    summary = json.loads(
        (run_dir / "stage-14" / "experiment_summary.json").read_text(encoding="utf-8")
    )
    grounded = _collect_real_metric_values(summary)
    assert 0.81 in grounded
    assert 0.90 in grounded
    assert 12.50 in grounded
    assert 9.75 in grounded


def test_synthesizes_metrics_when_report_has_no_table(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    report_path.write_text(
        "# Numbers only\n\nWe measured 1.25 and 3.50 and 7.\n", encoding="utf-8"
    )
    report = load_analysis_report(report_path)
    run_dir = tmp_path / "run2"
    result = seed_run_dir(run_dir, report, topic="T", authors="A")
    assert result.metrics_registered >= 1
    summary = json.loads(
        (run_dir / "stage-14" / "experiment_summary.json").read_text(encoding="utf-8")
    )
    assert summary["metrics_summary"]
    assert summary["best_run"]["metrics"]


def test_references_bib_seeded_from_embedded_bib(tmp_path: Path) -> None:
    _, run_dir = _seed(tmp_path)
    bib = (run_dir / "stage-04" / "references.bib").read_text(encoding="utf-8")
    assert "doe2026sparse" in bib


def test_references_bib_file_takes_precedence(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    report_path.write_text(_REPORT, encoding="utf-8")
    report = load_analysis_report(report_path)
    external = tmp_path / "external.bib"
    external.write_text("@misc{external,\n  title={Ext}\n}\n", encoding="utf-8")
    run_dir = tmp_path / "run3"
    seed_run_dir(
        run_dir,
        report,
        topic="T",
        authors="A",
        references_bib=external,
    )
    bib = (run_dir / "stage-04" / "references.bib").read_text(encoding="utf-8")
    assert "external" in bib


def test_charts_dir_copied(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    report_path.write_text(_REPORT, encoding="utf-8")
    report = load_analysis_report(report_path)
    charts = tmp_path / "charts"
    charts.mkdir()
    (charts / "fig1.png").write_bytes(b"png-bytes")
    run_dir = tmp_path / "run4"
    result = seed_run_dir(
        run_dir, report, topic="T", authors="A", charts_dir=charts
    )
    assert (run_dir / "stage-14" / "charts" / "fig1.png").is_file()
    assert "stage-14/charts/fig1.png" in result.files
