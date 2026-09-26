# pyright: reportPrivateUsage=false
"""Tests for the 'Local Deep Research Results' appendix added at export."""

from __future__ import annotations

from pathlib import Path

from researchclaw.config import ExportConfig, load_config
from researchclaw.pipeline.stage_impls._review_publish import _build_ldr_appendix

_MIN_CONFIG = """\
project:
  name: demo
research:
  topic: demo topic
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
  authors: A
  output_format: docx
"""


def test_build_ldr_appendix_absent_returns_empty(tmp_path: Path) -> None:
    assert _build_ldr_appendix(tmp_path) == ""


def test_build_ldr_appendix_wraps_run_report(tmp_path: Path) -> None:
    (tmp_path / "deep_research.md").write_text("# LDR body\nfindings", encoding="utf-8")
    out = _build_ldr_appendix(tmp_path)
    assert out.startswith("# Appendix: Local Deep Research Results")
    assert "LDR body" in out


def test_export_appendix_defaults_on() -> None:
    assert ExportConfig().include_deep_research_appendix is True


def test_export_appendix_toggle_parsed_from_config(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        _MIN_CONFIG + "  include_deep_research_appendix: false\n", encoding="utf-8"
    )
    config = load_config(path, project_root=tmp_path, check_paths=False)
    assert config.export.include_deep_research_appendix is False
