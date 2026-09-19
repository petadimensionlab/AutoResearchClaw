# pyright: reportPrivateUsage=false
"""Offline tests for the `researchclaw paper` CLI subcommand."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import researchclaw.paper.builder as builder_module
from researchclaw import cli as rc_cli
from researchclaw.paper import PaperBuildResult
from researchclaw.pipeline._helpers import StageResult
from researchclaw.pipeline.stages import Stage, StageStatus

_CONFIG_YAML = """project:
  name: demo
  mode: docs-first
research:
  topic: Config topic
runtime:
  timezone: UTC
notifications:
  channel: test
knowledge_base:
  backend: markdown
  root: kb
openclaw_bridge: {}
llm:
  provider: openai-compatible
  base_url: http://localhost:1234/v1
  api_key_env: TEST_KEY
"""


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(_CONFIG_YAML, encoding="utf-8")
    return path


def test_parser_exposes_paper_subcommand() -> None:
    parser = rc_cli.build_parser()
    args = parser.parse_args(
        [
            "paper",
            "--report",
            "r.md",
            "--output-format",
            "both",
            "--authors",
            "A",
            "--charts",
            "charts",
            "--references",
            "refs.bib",
            "--run-id",
            "paper-x",
        ]
    )
    assert args.command == "paper"
    assert args.report == "r.md"
    assert args.output_format == "both"
    assert args.authors == "A"
    assert args.charts == "charts"
    assert args.references == "refs.bib"
    assert args.run_id == "paper-x"


def test_report_argument_is_required() -> None:
    parser = rc_cli.build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["paper"])
    assert excinfo.value.code == 2


def test_main_dispatches_to_build_paper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    def fake(report_path: Any, output_dir: Any = None, **kwargs: Any) -> PaperBuildResult:
        captured["report_path"] = report_path
        captured["kwargs"] = kwargs
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        deliverable = run_dir / "deliverables" / "paper_final.md"
        deliverable.parent.mkdir(parents=True, exist_ok=True)
        deliverable.write_text("# paper\n", encoding="utf-8")
        return PaperBuildResult(
            run_dir=run_dir,
            run_id=kwargs.get("run_id") or "paper-x",
            results=(
                StageResult(Stage.PAPER_OUTLINE, StageStatus.DONE, ("outline.md",)),
            ),
            paper_markdown=deliverable,
            paper_docx=None,
            paper_tex=None,
            references_bib=None,
            ok=True,
        )

    monkeypatch.setattr(builder_module, "build_paper_from_report", fake)
    config_path = _write_config(tmp_path)

    code = rc_cli.main(
        ["paper", "--report", "report.md", "-c", str(config_path), "-t", "T"]
    )

    assert code == 0
    assert captured["report_path"] == "report.md"
    assert captured["kwargs"]["topic"] == "T"
    assert captured["kwargs"]["auto_approve_gates"] is True
    out = capsys.readouterr().out
    assert "paper_final.md" in out
    assert "Paper build complete." in out


def test_missing_config_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(rc_cli, "resolve_config_path", lambda explicit: None)
    code = rc_cli.main(["paper", "--report", "report.md"])
    assert code == 1
    captured = capsys.readouterr()
    assert "no config file found" in captured.err.lower()


def test_build_failure_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(*args: Any, **kwargs: Any) -> PaperBuildResult:
        raise FileNotFoundError("report missing")

    monkeypatch.setattr(builder_module, "build_paper_from_report", boom)
    config_path = _write_config(tmp_path)
    code = rc_cli.main(["paper", "--report", "missing.md", "-c", str(config_path)])
    assert code == 1
    assert "report missing" in capsys.readouterr().err
