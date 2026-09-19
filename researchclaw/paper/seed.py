"""Seed a run directory with the artifacts the paper stages (16-23) require.

Only paper-construction stages run in this workflow, so there is no upstream
literature search or experiment execution to produce ``analysis.md``,
``decision.md`` and ``experiment_summary.json``.  This module writes minimal,
faithful stand-ins derived from the user's markdown report so that:

* Stage 16's contract (``analysis.md`` + ``decision.md``) is satisfied.
* Stage 20's anti-fabrication ground truth (``condition_summaries`` and
  ``metrics_summary``) is non-empty, so its numbers are never blanked.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from researchclaw.paper.report import AnalysisReport

logger = logging.getLogger(__name__)

_MAX_SYNTHETIC_METRICS = 20


@dataclass(frozen=True)
class SeedResult:
    """Summary of the artifacts written by :func:`seed_run_dir`."""

    run_dir: Path
    files: tuple[str, ...]
    metrics_registered: int


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _goal_block(topic: str, report: AnalysisReport) -> str:
    abstract = report.abstract or "No abstract was provided in the source report."
    return (
        "# Research Goal\n\n"
        f"## Topic\n{topic}\n\n"
        f"## Source Report\n**{report.title}**\n\n{abstract}\n"
    )


def _hypotheses_block(report: AnalysisReport) -> str:
    for heading, content in report.sections:
        lowered = heading.lower()
        if "hypothes" in lowered or "finding" in lowered:
            body = content.strip() or "(no content in the source section)"
            return f"# Hypotheses\n\n## {heading}\n{body}\n"
    return (
        "# Hypotheses\n\n"
        f"The analysis report \u201c{report.title}\u201d documents findings "
        "that motivate the hypotheses investigated in this paper.\n"
    )


def _decision_block(report: AnalysisReport, metrics_registered: int) -> str:
    if metrics_registered:
        evidence = (
            f"The supplied analysis report provides {metrics_registered} "
            "grounded metric(s) and documented quantitative evidence."
        )
    else:
        evidence = (
            "The supplied analysis report provides documented evidence "
            "supporting the stated findings."
        )
    return (
        "# Research Decision\n\n"
        "PROCEED\n\n"
        f"{evidence} The paper-construction stages should proceed and build "
        "the manuscript directly from this report.\n"
    )


def _select_metrics(report: AnalysisReport) -> dict[str, float]:
    """Report metrics, or synthetic ``metric_N`` names from numeric values."""
    if report.metrics:
        return {name: float(value) for name, value in report.metrics}
    synthetic: dict[str, float] = {}
    for index, value in enumerate(report.numeric_values[:_MAX_SYNTHETIC_METRICS]):
        synthetic[f"metric_{index + 1}"] = float(value)
    if not synthetic:
        # Guarantee a non-empty best_run.metrics so Stage 20 never treats the
        # report as a failed experiment. ``0.0`` is an explicit neutral marker.
        synthetic["metric_1"] = 0.0
    return synthetic


def _build_latex_table(metrics: dict[str, float]) -> str:
    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{Reported Metrics}",
        r"\begin{tabular}{lr}",
        r"\hline",
        r"Metric & Value \\",
        r"\hline",
    ]
    if metrics:
        for name, value in metrics.items():
            escaped = name.replace("_", r"\_")
            lines.append(f"{escaped} & {value:.4f} \\\\")
    else:
        lines.append(r"No metric data available \\")
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def _build_experiment_summary(
    report: AnalysisReport, metrics: dict[str, float]
) -> dict[str, object]:
    metrics_summary = {
        name: {"min": value, "max": value, "mean": value, "count": 1}
        for name, value in metrics.items()
    }
    best_run = {
        "run_id": "report",
        "status": "completed",
        "metrics": dict(metrics),
    }

    report_condition: dict[str, object] = {"metrics": dict(metrics)}
    report_condition.update({name: value for name, value in metrics.items()})

    report_values: dict[str, object] = {
        f"v{index}": float(value)
        for index, value in enumerate(report.numeric_values)
    }
    report_values["metrics"] = {
        f"v{index}": float(value)
        for index, value in enumerate(report.numeric_values)
    }

    condition_summaries: dict[str, object] = {
        "report": report_condition,
        "_report_values": report_values,
    }

    return {
        "metrics_summary": metrics_summary,
        "best_run": best_run,
        "condition_summaries": condition_summaries,
        "total_conditions": len(condition_summaries),
        "total_metric_keys": len(metrics),
        "generated": _utcnow_iso(),
        "latex_table": _build_latex_table(metrics),
    }


def _copy_charts(charts_dir: Path, target_dir: Path) -> list[str]:
    copied: list[str] = []
    if not charts_dir.is_dir():
        logger.warning("charts_dir does not exist or is not a directory: %s", charts_dir)
        return copied
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in sorted(charts_dir.iterdir()):
        destination = target_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
            copied.append(f"stage-14/charts/{entry.name}/")
        elif entry.is_file():
            shutil.copy2(entry, destination)
            copied.append(f"stage-14/charts/{entry.name}")
    return copied


def seed_run_dir(
    run_dir: Path,
    report: AnalysisReport,
    *,
    topic: str,
    authors: str,
    references_bib: Path | None = None,
    charts_dir: Path | None = None,
) -> SeedResult:
    """Write the paper-stage prerequisites derived from *report* into *run_dir*.

    Parameters
    ----------
    run_dir:
        Target run directory (created if missing).
    report:
        Parsed analysis report produced by :func:`load_analysis_report`.
    topic:
        Research topic used by the pipeline config and goal stage.
    authors:
        Author string recorded in the goal block (informational only).
    references_bib:
        Optional BibTeX file copied to ``stage-04/references.bib``.
    charts_dir:
        Optional directory whose contents are copied to ``stage-14/charts/``.

    Returns
    -------
    SeedResult
        The run directory, relative paths of written files, and how many
        metrics were registered for grounding.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    metrics = _select_metrics(report)
    metrics_registered = len(metrics)

    goal = _goal_block(topic, report)
    if authors:
        goal += f"\n## Authors\n{authors}\n"
    _write_text(run_dir / "stage-01" / "goal.md", goal)
    files.append("stage-01/goal.md")

    _write_text(run_dir / "stage-07" / "synthesis.md", report.body)
    files.append("stage-07/synthesis.md")

    _write_text(run_dir / "stage-08" / "hypotheses.md", _hypotheses_block(report))
    files.append("stage-08/hypotheses.md")

    _write_text(run_dir / "stage-14" / "analysis.md", report.body)
    _write_text(run_dir / "analysis_best.md", report.body)
    files.extend(["stage-14/analysis.md", "analysis_best.md"])

    decision = _decision_block(report, metrics_registered)
    _write_text(run_dir / "stage-15" / "decision.md", decision)
    files.append("stage-15/decision.md")

    summary = _build_experiment_summary(report, metrics)
    _write_json(run_dir / "stage-14" / "experiment_summary.json", summary)
    _write_json(run_dir / "experiment_summary_best.json", summary)
    files.extend(
        ["stage-14/experiment_summary.json", "experiment_summary_best.json"]
    )

    if references_bib is not None:
        bib_path = Path(references_bib)
        if bib_path.is_file():
            _write_text(
                run_dir / "stage-04" / "references.bib",
                bib_path.read_text(encoding="utf-8"),
            )
            files.append("stage-04/references.bib")
        else:
            logger.warning("references_bib not found, skipping: %s", bib_path)
    elif report.embedded_bib:
        _write_text(run_dir / "stage-04" / "references.bib", report.embedded_bib)
        files.append("stage-04/references.bib")

    if charts_dir is not None:
        files.extend(_copy_charts(Path(charts_dir), run_dir / "stage-14" / "charts"))

    logger.info(
        "Seeded run dir %s with %d files (%d metrics registered)",
        run_dir,
        len(files),
        metrics_registered,
    )
    return SeedResult(
        run_dir=run_dir,
        files=tuple(files),
        metrics_registered=metrics_registered,
    )
