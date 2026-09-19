"""Build a paper from a user-supplied markdown analysis-results report.

Public API::

    from researchclaw.paper import (
        AnalysisReport,
        load_analysis_report,
        PaperBuildResult,
        build_paper_from_report,
    )

This package is intentionally import-light: importing it never constructs an
LLM client or touches the network.
"""

from __future__ import annotations

from researchclaw.paper.builder import PaperBuildResult, build_paper_from_report
from researchclaw.paper.report import AnalysisReport, load_analysis_report
from researchclaw.paper.seed import SeedResult, seed_run_dir

__all__ = [
    "AnalysisReport",
    "PaperBuildResult",
    "SeedResult",
    "build_paper_from_report",
    "load_analysis_report",
    "seed_run_dir",
]
