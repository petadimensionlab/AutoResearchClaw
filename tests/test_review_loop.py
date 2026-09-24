# pyright: reportPrivateUsage=false, reportArgumentType=false
"""Offline tests for the cross-model review loop and draft-section dedup."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import researchclaw.pipeline.executor as executor
import researchclaw.pipeline.runner as pipeline_runner
from researchclaw.pipeline._helpers import StageResult
from researchclaw.pipeline.stage_impls._paper_writing import _dedupe_sections
from researchclaw.pipeline.stages import Stage, StageStatus


class _FakeLLM:
    """Returns queued contents in order (review call, then revise call)."""

    def __init__(self, *contents: str) -> None:
        self.contents = list(contents)
        self.calls: list[dict[str, object]] = []

    def chat(self, messages: list[dict[str, str]], **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(content=self.contents.pop(0) if self.contents else "")


def _cfg(
    reviewer_model: str = "qwen3.8-flash-next",
    stages: tuple[int, ...] = (17,),
    reviser: str = "reviewer",
) -> SimpleNamespace:
    return SimpleNamespace(
        llm=SimpleNamespace(
            reviewer_model=reviewer_model,
            review_loop_enabled=True,
            review_loop_stages=stages,
            review_loop_reviser=reviser,
            reviewer_max_tokens=65536,
        ),
        research=SimpleNamespace(topic="topic"),
    )


def _seed_stage(tmp_path: Path) -> Path:
    stage_dir = tmp_path / "stage-17"
    stage_dir.mkdir()
    (stage_dir / "paper_draft.md").write_text("## Intro\nold", encoding="utf-8")
    return stage_dir


def test_review_loop_base_revises(tmp_path: Path, monkeypatch) -> None:
    stage_dir = _seed_stage(tmp_path)
    reviewer = _FakeLLM("## Critical weaknesses\n- x", "## Intro\nrevised by base")
    author = _FakeLLM("unused")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    result = executor._apply_cross_model_review(
        Stage.PAPER_DRAFT,
        stage_dir,
        _cfg(reviser="reviewer"),
        author,
        StageResult(Stage.PAPER_DRAFT, StageStatus.DONE, ("paper_draft.md",)),
    )
    assert (stage_dir / "paper_draft.md").read_text(encoding="utf-8") == "## Intro\nrevised by base"
    assert (stage_dir / "cross_review.md").is_file()
    assert "cross_review.md" in result.artifacts
    assert reviewer.calls[0]["max_tokens"] == 65536
    assert reviewer.calls[1]["max_tokens"] == 65536
    assert author.calls == []


def test_review_loop_author_revises_when_configured(tmp_path: Path, monkeypatch) -> None:
    stage_dir = _seed_stage(tmp_path)
    reviewer = _FakeLLM("## Critical weaknesses\n- x")
    author = _FakeLLM("## Intro\nrevised by chat")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    executor._apply_cross_model_review(
        Stage.PAPER_DRAFT,
        stage_dir,
        _cfg(reviser="author"),
        author,
        StageResult(Stage.PAPER_DRAFT, StageStatus.DONE, ("paper_draft.md",)),
    )
    assert (stage_dir / "paper_draft.md").read_text(encoding="utf-8") == "## Intro\nrevised by chat"
    assert author.calls


def test_review_loop_falls_back_to_author_when_base_revise_empty(
    tmp_path: Path, monkeypatch
) -> None:
    stage_dir = _seed_stage(tmp_path)
    reviewer = _FakeLLM("## Critical weaknesses\n- x", "")
    author = _FakeLLM("## Intro\nfallback by chat")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    executor._apply_cross_model_review(
        Stage.PAPER_DRAFT,
        stage_dir,
        _cfg(reviser="reviewer"),
        author,
        StageResult(Stage.PAPER_DRAFT, StageStatus.DONE, ("paper_draft.md",)),
    )
    assert (stage_dir / "paper_draft.md").read_text(encoding="utf-8") == "## Intro\nfallback by chat"
    assert author.calls


def test_review_loop_skips_when_reviewer_empty(tmp_path: Path, monkeypatch) -> None:
    stage_dir = _seed_stage(tmp_path)
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: _FakeLLM(""))
    )
    executor._apply_cross_model_review(
        Stage.PAPER_DRAFT,
        stage_dir,
        _cfg(),
        _FakeLLM("## Intro\nrevised"),
        StageResult(Stage.PAPER_DRAFT, StageStatus.DONE, ("paper_draft.md",)),
    )
    assert (stage_dir / "paper_draft.md").read_text(encoding="utf-8") == "## Intro\nold"
    assert not (stage_dir / "cross_review.md").exists()


def test_review_loop_disabled_without_reviewer_model() -> None:
    enabled, stages, max_tokens = executor._review_loop_settings(_cfg(reviewer_model=""))
    assert enabled is False
    assert stages == {17}
    assert max_tokens == 65536


def test_review_loop_skips_unmapped_stage(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-02"
    stage_dir.mkdir()
    (stage_dir / "problem_tree.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: _FakeLLM("r"))
    )
    result = executor._apply_cross_model_review(
        Stage.PROBLEM_DECOMPOSE,
        stage_dir,
        _cfg(stages=(2,)),
        _FakeLLM("y"),
        StageResult(Stage.PROBLEM_DECOMPOSE, StageStatus.DONE, ("problem_tree.md",)),
    )
    assert (stage_dir / "problem_tree.md").read_text(encoding="utf-8") == "x"
    assert result.artifacts == ("problem_tree.md",)


def test_review_loop_review_only_for_structured_artifact(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-09"
    stage_dir.mkdir()
    (stage_dir / "exp_plan.yaml").write_text("conditions: 1\n", encoding="utf-8")
    reviewer = _FakeLLM("## Critical weaknesses\n- weak plan")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    result = executor._apply_cross_model_review(
        Stage.EXPERIMENT_DESIGN,
        stage_dir,
        _cfg(stages=(9,)),
        _FakeLLM("unused"),
        StageResult(Stage.EXPERIMENT_DESIGN, StageStatus.DONE, ("exp_plan.yaml",)),
    )
    assert (stage_dir / "exp_plan.yaml").read_text(encoding="utf-8") == "conditions: 1\n"
    assert (stage_dir / "cross_review.md").is_file()
    assert "cross_review.md" in result.artifacts
    assert len(reviewer.calls) == 1


def test_review_loop_review_only_for_stage_22(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-22"
    stage_dir.mkdir()
    (stage_dir / "paper_final.md").write_text("## Final\ncontent", encoding="utf-8")
    reviewer = _FakeLLM("## Critical weaknesses\n- x")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    executor._apply_cross_model_review(
        Stage.EXPORT_PUBLISH,
        stage_dir,
        _cfg(stages=(22,)),
        _FakeLLM("unused"),
        StageResult(Stage.EXPORT_PUBLISH, StageStatus.DONE, ("paper_final.md",)),
    )
    assert (stage_dir / "paper_final.md").read_text(encoding="utf-8") == "## Final\ncontent"
    assert (stage_dir / "cross_review.md").is_file()


def test_review_loop_revises_synthesis_markdown(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-07"
    stage_dir.mkdir()
    (stage_dir / "synthesis.md").write_text("## Synthesis\nold", encoding="utf-8")
    reviewer = _FakeLLM("## Critical weaknesses\n- x", "## Synthesis\nrevised synthesis")
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    executor._apply_cross_model_review(
        Stage.SYNTHESIS,
        stage_dir,
        _cfg(stages=(7,)),
        _FakeLLM("unused"),
        StageResult(Stage.SYNTHESIS, StageStatus.DONE, ("synthesis.md",)),
    )
    assert (stage_dir / "synthesis.md").read_text(encoding="utf-8") == "## Synthesis\nrevised synthesis"


def test_code_review_fixes_files(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-10"
    (stage_dir / "experiment").mkdir(parents=True)
    (stage_dir / "experiment" / "main.py").write_text("print('broken')\n", encoding="utf-8")
    fixed = "```filename:experiment/main.py\nprint('fixed')\n```"
    reviewer = _FakeLLM("## Critical weaknesses\n- no metrics", fixed)
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    result = executor._apply_cross_model_review(
        Stage.CODE_GENERATION,
        stage_dir,
        _cfg(stages=(10,)),
        _FakeLLM("unused"),
        StageResult(Stage.CODE_GENERATION, StageStatus.DONE, ("experiment_spec.md",)),
    )
    assert (stage_dir / "experiment" / "main.py").read_text(encoding="utf-8") == "print('fixed')\n"
    assert (stage_dir / "cross_review.md").is_file()
    assert "cross_review.md" in result.artifacts


def test_code_review_rejects_invalid_syntax(tmp_path: Path, monkeypatch) -> None:
    stage_dir = tmp_path / "stage-10"
    (stage_dir / "experiment").mkdir(parents=True)
    (stage_dir / "experiment" / "main.py").write_text("print('original')\n", encoding="utf-8")
    broken = "```filename:experiment/main.py\ndef broken(:\n```"
    reviewer = _FakeLLM("## Critical weaknesses\n- x", broken)
    monkeypatch.setattr(
        executor.LLMClient, "reviewer_from_rc_config", staticmethod(lambda config: reviewer)
    )
    executor._apply_cross_model_review(
        Stage.CODE_GENERATION,
        stage_dir,
        _cfg(stages=(10,)),
        _FakeLLM("unused"),
        StageResult(Stage.CODE_GENERATION, StageStatus.DONE, ("experiment_spec.md",)),
    )
    assert (stage_dir / "experiment" / "main.py").read_text(encoding="utf-8") == "print('original')\n"


def test_zero_metric_failure_detector() -> None:
    assert pipeline_runner._is_zero_metric_failure(
        "Experiment 'completed' in 0.0s with zero real metrics"
    )
    assert not pipeline_runner._is_zero_metric_failure("some other error")
    assert not pipeline_runner._is_zero_metric_failure(None)


def test_dedupe_sections_collapses_duplicates() -> None:
    draft = (
        "## Abstract\nA\n\n## Introduction\nI1\n\n"
        "## Method\nshort\n\n## Results\nR1\n\n"
        "## Introduction\nI2 longer intro\n\n## Method\nlonger method body\n\n"
        "## Results\nR2 much longer results body here\n"
    )
    out, dropped = _dedupe_sections(draft)
    assert sorted(dropped) == ["Introduction", "Method", "Results"]
    assert out.count("## Introduction") == 1
    assert out.count("## Method") == 1
    assert "I2 longer intro" in out
    assert "longer method body" in out
    assert "R2 much longer results body here" in out
    assert "R1" not in out


def test_dedupe_sections_noop_without_duplicates() -> None:
    draft = "## Abstract\nA\n\n## Introduction\nI\n"
    out, dropped = _dedupe_sections(draft)
    assert dropped == []
    assert out == draft
