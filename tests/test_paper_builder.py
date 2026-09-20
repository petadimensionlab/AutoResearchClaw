# pyright: reportPrivateUsage=false
"""Offline tests for researchclaw.paper.builder (pipeline is always faked)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import researchclaw.paper.builder as builder_module
from researchclaw.paper import PaperBuildResult, build_paper_from_report
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
export:
  authors: Config Author
  output_format: docx
"""

_REPORT = """# Report Title

## Abstract

Abstract text.

## Findings

| Metric | Value |
|--------|-------|
| accuracy | 0.90 |
"""


def _write_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(_CONFIG_YAML, encoding="utf-8")
    return path


def _write_report(tmp_path: Path) -> Path:
    path = tmp_path / "report.md"
    path.write_text(_REPORT, encoding="utf-8")
    return path


class _RecordingPipeline:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def __call__(self, **kwargs: Any) -> list[StageResult]:
        self.kwargs = kwargs
        run_dir: Path = kwargs["run_dir"]
        deliverables = run_dir / "deliverables"
        deliverables.mkdir(parents=True, exist_ok=True)
        (deliverables / "paper_final.md").write_text("# Final paper\n", encoding="utf-8")
        (run_dir / "stage-22").mkdir(parents=True, exist_ok=True)
        (run_dir / "stage-22" / "paper.docx").write_bytes(b"docx-bytes")
        return [
            StageResult(Stage.PAPER_OUTLINE, StageStatus.DONE, ("outline.md",)),
            StageResult(Stage.CITATION_VERIFY, StageStatus.DONE, ("verification_report.json",)),
        ]


def test_build_reuses_paper_stages_and_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _RecordingPipeline()
    monkeypatch.setattr(builder_module, "execute_pipeline", fake)

    config_path = _write_config(tmp_path)
    report_path = _write_report(tmp_path)
    out_dir = tmp_path / "run"

    result = build_paper_from_report(
        report_path,
        out_dir,
        config_path=config_path,
        topic="Override topic",
        authors="Ada Lovelace",
        output_format="latex",
    )

    assert fake.kwargs is not None
    assert fake.kwargs["from_stage"] is Stage.PAPER_OUTLINE
    assert fake.kwargs["to_stage"] is Stage.CITATION_VERIFY
    assert fake.kwargs["auto_approve_gates"] is True
    assert fake.kwargs["stop_on_gate"] is False
    assert fake.kwargs["run_dir"] == out_dir

    config = fake.kwargs["config"]
    assert config.research.project_mode == "docs-first"
    assert config.research.topic == "Override topic"
    assert config.export.authors == "Ada Lovelace"
    assert config.export.output_format == "latex"

    assert isinstance(result, PaperBuildResult)
    assert result.run_dir == out_dir
    assert result.paper_markdown == out_dir / "deliverables" / "paper_final.md"
    assert result.paper_docx == out_dir / "stage-22" / "paper.docx"
    assert result.paper_tex is None
    assert result.references_bib is None
    assert result.ok is True


def test_topic_defaults_to_report_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _RecordingPipeline()
    monkeypatch.setattr(builder_module, "execute_pipeline", fake)
    config_path = _write_config(tmp_path)
    report_path = _write_report(tmp_path)

    build_paper_from_report(
        report_path,
        tmp_path / "run2",
        config_path=config_path,
        topic=None,
    )
    assert fake.kwargs is not None
    # Config topic is non-empty so it wins over the report title.
    assert fake.kwargs["config"].research.topic == "Config topic"


def test_default_run_dir_uses_local_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _RecordingPipeline()
    monkeypatch.setattr(builder_module, "execute_pipeline", fake)
    monkeypatch.chdir(tmp_path)
    config_path = _write_config(tmp_path)
    report_path = _write_report(tmp_path)

    result = build_paper_from_report(report_path, config_path=config_path)
    assert result.run_dir.parent == Path("artifacts")
    assert result.run_dir.name.startswith("paper-")
    assert result.run_id == result.run_dir.name


def test_ok_is_false_when_a_stage_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_valid(**kwargs: Any) -> list[StageResult]:
        return [
            StageResult(Stage.PAPER_OUTLINE, StageStatus.FAILED, (), error="boom"),
        ]

    monkeypatch.setattr(builder_module, "execute_pipeline", failing_valid)
    config_path = _write_config(tmp_path)
    report_path = _write_report(tmp_path)
    result = build_paper_from_report(report_path, tmp_path / "run4", config_path=config_path)
    assert result.ok is False


def test_missing_config_raises_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(builder_module, "resolve_config_path", lambda explicit: None)
    report_path = _write_report(tmp_path)
    with pytest.raises(FileNotFoundError):
        build_paper_from_report(report_path, tmp_path / "run5")


def test_report_grounding_prompt_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from researchclaw.prompts.manager import PromptManager

    fake = _RecordingPipeline()
    monkeypatch.setattr(builder_module, "execute_pipeline", fake)
    config_path = _write_config(tmp_path)
    report_path = _write_report(tmp_path)

    build_paper_from_report(report_path, tmp_path / "run6", config_path=config_path)

    assert fake.kwargs is not None
    extras = dict(fake.kwargs["config"].prompts.extra_prompts)
    assert "paper_draft" in extras
    assert "paper_revision" in extras
    grounded = Path(extras["paper_draft"])
    assert grounded.is_file()

    manager = PromptManager(extra_prompts=extras)
    loaded = manager.extra_prompts()
    assert "NUMERICAL INTEGRITY" in loaded["paper_draft"]
    assert "NUMERICAL INTEGRITY" in loaded["paper_revision"]


def test_report_grounding_preserves_existing_paper_draft_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _RecordingPipeline()
    monkeypatch.setattr(builder_module, "execute_pipeline", fake)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _CONFIG_YAML + "prompts:\n  extra_prompts:\n    paper_draft: CUSTOM-PAPER-DRAFT-RULE\n",
        encoding="utf-8",
    )
    report_path = _write_report(tmp_path)

    build_paper_from_report(report_path, tmp_path / "run7", config_path=config_path)

    assert fake.kwargs is not None
    extras = dict(fake.kwargs["config"].prompts.extra_prompts)
    text = Path(extras["paper_draft"]).read_text(encoding="utf-8")
    assert "CUSTOM-PAPER-DRAFT-RULE" in text
    assert "NUMERICAL INTEGRITY" in text
