"""Build a paper from a user-supplied markdown analysis report.

Seeds a run directory from the report and then runs only the existing
paper-construction stages (16-23) through ``execute_pipeline``.  Nothing is
re-implemented: outline, draft, review, revision, quality gate, archive,
export and citation verification are the real pipeline stages.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from researchclaw.adapters import AdapterBundle
from researchclaw.config import (
    RCConfig,
    _normalize_export_format,
    resolve_config_path,
)
from researchclaw.paper.report import AnalysisReport, load_analysis_report
from researchclaw.paper.seed import seed_run_dir
from researchclaw.pipeline._helpers import StageResult
from researchclaw.pipeline.runner import execute_pipeline
from researchclaw.pipeline.stages import Stage, StageStatus

logger = logging.getLogger(__name__)

# A stage result is considered successful when it reached DONE (gates may
# surface APPROVED when a human/HITL approval transitioned them).
_SUCCESS_STATUSES: frozenset[StageStatus] = frozenset(
    {StageStatus.DONE, StageStatus.APPROVED}
)

_GROUNDING_STAGES: tuple[str, ...] = ("paper_draft", "paper_revision")
_GROUNDING_RULE_FILE = (
    Path(__file__).resolve().parents[2] / "prompts" / "report_grounded_numbers.md"
)
_GROUNDING_RULE_INLINE = (
    "NUMERICAL INTEGRITY: use ONLY numbers present verbatim in the supplied analysis "
    "report / experiment metrics; never invent or derive percentages, effect sizes, "
    "p-values, CIs or per-condition stats."
)


def _grounding_rule_text() -> str:
    if _GROUNDING_RULE_FILE.is_file():
        try:
            return _GROUNDING_RULE_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            logger.warning("Could not read grounding rule: %s", _GROUNDING_RULE_FILE)
    return _GROUNDING_RULE_INLINE


def _resolve_extra_text(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.exists() and candidate.is_file():
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return value.strip()


def _with_report_grounding(config: RCConfig, run_dir: Path) -> RCConfig:
    """Force report-grounded number guidance on the paper-writing stages.

    Existing ``extra_prompts`` for those stages are preserved and concatenated
    with the grounding rule; the merged text is written into the run directory
    and referenced as a file so ``PromptManager`` never sees an over-long inline
    string.
    """
    rule = _grounding_rule_text()
    if not rule:
        return config
    existing = tuple(config.prompts.extra_prompts)
    kept = [(stage, value) for stage, value in existing if stage not in _GROUNDING_STAGES]
    prior_parts: list[str] = []
    for stage, value in existing:
        if stage in _GROUNDING_STAGES:
            text = _resolve_extra_text(value)
            if text:
                prior_parts.append(text)
    prior = "\n\n".join(prior_parts)
    combined = f"{prior}\n\n{rule}" if prior else rule

    target = run_dir / "prompts" / "report_grounded_extra.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(combined, encoding="utf-8")

    merged = kept + [(stage, str(target)) for stage in _GROUNDING_STAGES]
    prompts = dataclasses.replace(config.prompts, extra_prompts=tuple(merged))
    logger.info(
        "Injected report-grounding prompt for stages: %s", ", ".join(_GROUNDING_STAGES)
    )
    return dataclasses.replace(config, prompts=prompts)


@dataclass(frozen=True)
class PaperBuildResult:
    """Outcome of :func:`build_paper_from_report`."""

    run_dir: Path
    run_id: str
    results: tuple[StageResult, ...]
    paper_markdown: Path | None
    paper_docx: Path | None
    paper_tex: Path | None
    references_bib: Path | None
    ok: bool


def _make_run_id(topic: str, report_path: Path) -> str:
    """Local run-id helper (kept out of ``researchclaw.cli`` to avoid cycles)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha1(f"{topic}\0{report_path}".encode("utf-8")).hexdigest()[:6]
    return f"paper-{stamp}-{digest}"


def _resolve_config(
    config: RCConfig | None,
    config_path: str | Path | None,
) -> RCConfig:
    if config is not None:
        return config
    resolved: Path | None
    if config_path is not None:
        resolved = resolve_config_path(str(config_path))
    else:
        resolved = resolve_config_path(None)
    if resolved is None:
        raise FileNotFoundError(
            "No config file found. Pass config=..., config_path=..., or create "
            "a config.arc.yaml / config.yaml (run 'researchclaw init')."
        )
    return RCConfig.load(resolved, check_paths=False)


def _with_overrides(
    config: RCConfig,
    *,
    topic: str,
    authors: str | None,
    output_format: str | None,
) -> RCConfig:
    research = dataclasses.replace(config.research, project_mode="docs-first", topic=topic)
    export_kwargs: dict[str, str] = {}
    if authors is not None:
        export_kwargs["authors"] = authors
    if output_format is not None:
        export_kwargs["output_format"] = _normalize_export_format(output_format)
    export = (
        dataclasses.replace(config.export, **export_kwargs)
        if export_kwargs
        else config.export
    )
    return dataclasses.replace(config, research=research, export=export)


def _first_file(*candidates: Path) -> Path | None:
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def _resolve_outputs(run_dir: Path) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    paper_markdown = _first_file(
        run_dir / "deliverables" / "paper_final.md",
        run_dir / "stage-23" / "paper_final_verified.md",
        run_dir / "stage-22" / "paper_final.md",
    )
    paper_docx = _first_file(
        run_dir / "deliverables" / "paper.docx",
        run_dir / "stage-22" / "paper.docx",
    )
    paper_tex = _first_file(
        run_dir / "deliverables" / "paper.tex",
        run_dir / "stage-22" / "paper.tex",
    )
    references_bib = _first_file(
        run_dir / "deliverables" / "references.bib",
        run_dir / "stage-23" / "references_verified.bib",
        run_dir / "stage-22" / "references.bib",
    )
    return paper_markdown, paper_docx, paper_tex, references_bib


def build_paper_from_report(
    report_path: Path | str,
    output_dir: Path | str | None = None,
    *,
    config: RCConfig | None = None,
    config_path: str | Path | None = None,
    topic: str | None = None,
    authors: str | None = None,
    output_format: str | None = None,
    charts_dir: Path | str | None = None,
    references_bib: Path | str | None = None,
    run_id: str | None = None,
    auto_approve_gates: bool = True,
) -> PaperBuildResult:
    """Build a paper from *report_path* using pipeline stages 16-23.

    Resolution order for the base config: explicit ``config``, else
    ``RCConfig.load(config_path)``, else ``RCConfig.load(resolve_config_path(None))``.
    A :class:`FileNotFoundError` is raised when no config file can be found.

    ``research.project_mode`` is forced to ``"docs-first"`` so the paper stages
    treat the supplied report as the grounding source instead of demanding a
    fresh sandbox experiment.
    """
    cfg = _resolve_config(config, config_path)
    report: AnalysisReport = load_analysis_report(report_path)

    chosen_topic = topic or cfg.research.topic or report.title
    chosen_authors = authors if authors is not None else cfg.export.authors
    cfg = _with_overrides(
        cfg,
        topic=chosen_topic,
        authors=chosen_authors,
        output_format=output_format,
    )

    report_file = Path(report_path)
    resolved_run_id = run_id or _make_run_id(chosen_topic, report_file)
    if output_dir is None:
        run_dir = Path("artifacts") / resolved_run_id
    else:
        run_dir = Path(output_dir)

    seed_run_dir(
        run_dir,
        report,
        topic=chosen_topic,
        authors=chosen_authors,
        references_bib=Path(references_bib) if references_bib is not None else None,
        charts_dir=Path(charts_dir) if charts_dir is not None else None,
    )
    cfg = _with_report_grounding(cfg, run_dir)

    logger.info(
        "Building paper from report %s → run_dir=%s (run_id=%s)",
        report_path,
        run_dir,
        resolved_run_id,
    )
    results = execute_pipeline(
        run_dir=run_dir,
        run_id=resolved_run_id,
        config=cfg,
        adapters=AdapterBundle(),
        from_stage=Stage.PAPER_OUTLINE,
        to_stage=Stage.CITATION_VERIFY,
        auto_approve_gates=auto_approve_gates,
        stop_on_gate=False,
    )

    paper_markdown, paper_docx, paper_tex, bib_out = _resolve_outputs(run_dir)
    ok = bool(results) and all(r.status in _SUCCESS_STATUSES for r in results)

    return PaperBuildResult(
        run_dir=run_dir,
        run_id=resolved_run_id,
        results=tuple(results),
        paper_markdown=paper_markdown,
        paper_docx=paper_docx,
        paper_tex=paper_tex,
        references_bib=bib_out,
        ok=ok,
    )
