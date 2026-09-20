# pyright: reportPrivateUsage=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnusedCallResult=false, reportAttributeAccessIssue=false, reportUnknownLambdaType=false
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from researchclaw.templates.docx_exporter import (
    DocxResult,
    _preprocess_markdown,
    markdown_to_docx,
    pandoc_available,
)

PANDOC = pytest.mark.skipif(not pandoc_available(), reason="pandoc not installed")


def _document_text(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


@PANDOC
def test_pipe_table_markdown_roundtrip(tmp_path: Path) -> None:
    # Given a markdown draft with a pipe table
    markdown = (
        "# Title\n\n"
        "| Method | Score |\n"
        "| --- | --- |\n"
        "| Baseline | 0.81 |\n"
        "| Ours | 0.94 |\n"
    )
    out_path = tmp_path / "paper.docx"

    # When converting to docx
    result = markdown_to_docx(markdown, out_path)

    # Then conversion succeeds and cell values survive into the document
    assert isinstance(result, DocxResult)
    assert result.success is True
    assert result.output_path == out_path
    assert out_path.exists()
    text = _document_text(out_path)
    assert "Baseline" in text
    assert "0.94" in text


@PANDOC
def test_raw_latex_table_converted(tmp_path: Path) -> None:
    # Given a raw LaTeX table pandoc would otherwise drop
    markdown = (
        "# Title\n\n"
        "\\begin{table}[ht]\n"
        "\\centering\n"
        "\\caption{Accuracy across methods}\n"
        "\\begin{tabular}{lcc}\n"
        "\\toprule\n"
        "Method & Acc\\_1 & Acc\\_2 \\\\\n"
        "\\midrule\n"
        "Baseline & 0.81 & 0.82 \\\\\n"
        "Ours & 0.93 & 0.94 \\\\\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )
    out_path = tmp_path / "latex_table.docx"

    # When converting to docx
    result = markdown_to_docx(markdown, out_path)

    # Then the caption and cell values survive and underscores are unescaped
    assert result.success is True
    text = _document_text(out_path)
    assert "Accuracy across methods" in text
    assert "Baseline" in text
    assert "0.93" in text
    assert "Acc_1" in text


@PANDOC
def test_cite_becomes_readable_marker(tmp_path: Path) -> None:
    # Given a draft citing keys without a bibliography
    markdown = "# Title\n\nPrior work \\cite{smith2020,jones2019} shows gains.\n"
    out_path = tmp_path / "cite.docx"

    # When converting to docx
    result = markdown_to_docx(markdown, out_path)

    # Then the citation is a readable marker pandoc keeps
    assert result.success is True
    assert "[smith2020; jones2019]" in _document_text(out_path)


@PANDOC
def test_cite_with_bibliography_resolves(tmp_path: Path) -> None:
    # Given a bibliography bib that resolves the citation
    bib_path = tmp_path / "references.bib"
    bib_path.write_text(
        "@article{smith2020,\n"
        "  author = {Smith, John},\n"
        "  title = {A Paper},\n"
        "  year = {2020},\n"
        "  journal = {J}\n"
        "}\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "cite_bib.docx"

    # When converting with citeproc enabled
    result = markdown_to_docx(
        "# Title\n\nSee \\cite{smith2020}.\n", out_path, bib_path=bib_path
    )

    # Then the author-year text is rendered
    assert result.success is True
    text = _document_text(out_path)
    assert "Smith" in text
    assert "2020" in text


def test_missing_pandoc_returns_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given pandas is not on PATH
    monkeypatch.setattr(
        "researchclaw.templates.docx_exporter.shutil.which", lambda _name: None
    )

    # When converting
    result = markdown_to_docx("# Title\n\ncontent\n", tmp_path / "paper.docx")

    # Then the result advertises the missing dependency without raising
    assert result.success is False
    assert result.pandoc_available is False
    assert result.output_path is None
    assert "pandoc not installed" in result.error


def test_pandoc_nonzero_exit_returns_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given pandoc exists but exits non-zero
    monkeypatch.setattr(
        "researchclaw.templates.docx_exporter.shutil.which",
        lambda _name: "/usr/bin/pandoc",
    )

    class _FailedProcess:
        returncode = 1
        stderr = "pandoc: something went wrong"
        stdout = ""

    monkeypatch.setattr(
        "researchclaw.templates.docx_exporter.subprocess.run",
        lambda *args, **kwargs: _FailedProcess(),
    )

    # When converting
    result = markdown_to_docx("# Title\n\ncontent\n", tmp_path / "paper.docx")

    # Then the stderr excerpt is surfaced without raising
    assert result.success is False
    assert result.pandoc_available is True
    assert "something went wrong" in result.error


def test_pandoc_exception_returns_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given invoking pandoc raises
    monkeypatch.setattr(
        "researchclaw.templates.docx_exporter.shutil.which",
        lambda _name: "/usr/bin/pandoc",
    )

    def _boom(*args: object, **kwargs: object) -> object:
        raise OSError("pandoc exploded")

    monkeypatch.setattr(
        "researchclaw.templates.docx_exporter.subprocess.run", _boom
    )

    # When converting
    result = markdown_to_docx("# Title\n\ncontent\n", tmp_path / "paper.docx")

    # Then the failure is reported without raising
    assert result.success is False
    assert result.pandoc_available is True
    assert "pandoc invocation failed" in result.error


def test_display_math_normalised_and_inline_math_preserved() -> None:
    # Given display and inline math in the draft
    markdown = "Inline $x^2$ stays.\n\n\\[\nE = mc^2\n\\]\n"

    # When pre-processing
    body, warnings = _preprocess_markdown(markdown, has_bib=False)

    # Then display math uses $$ and inline math is untouched
    assert "$$\nE = mc^2\n$$" in body
    assert "$x^2$" in body
    assert warnings == []


def test_stray_table_commands_stripped() -> None:
    # Given leftover LaTeX rule commands and a label
    markdown = "# Title\n\n\\hline\n\\toprule\n\\label{tab:1}\nBody text.\n"

    # When pre-processing
    body, _ = _preprocess_markdown(markdown, has_bib=False)

    # Then the stray commands are gone
    assert "\\hline" not in body
    assert "\\toprule" not in body
    assert "\\label" not in body
    assert "Body text." in body


@PANDOC
def test_title_injected_when_missing(tmp_path: Path) -> None:
    # Given a draft with no top-level heading
    out_path = tmp_path / "titled.docx"

    # When a title is supplied
    result = markdown_to_docx("Some body text.\n", out_path, title="My Paper")

    # Then the title appears in the document
    assert result.success is True
    assert "My Paper" in _document_text(out_path)


@PANDOC
def test_relative_out_path_does_not_nest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given a relative output path, as the pipeline passes to the exporter
    monkeypatch.chdir(tmp_path)
    out_rel = Path("stage-22/paper.docx")
    out_rel.parent.mkdir(parents=True, exist_ok=True)

    # When converting
    result = markdown_to_docx("# Title\n\nBody text.\n", out_rel)

    # Then the document lands at the relative path and pandoc does not nest it
    # under a second copy of the path inside its own working directory
    assert result.success is True
    assert (tmp_path / "stage-22" / "paper.docx").is_file()
    assert not (tmp_path / "stage-22" / "stage-22").exists()
    assert not (tmp_path / "stage-22" / "artifacts").exists()

