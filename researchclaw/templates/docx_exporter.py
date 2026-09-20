"""Pandoc-backed Markdown → Word (``.docx``) exporter.

Pandoc renders most Markdown natively but silently drops raw LaTeX
``\\begin{table}...\\end{table}`` blocks and ``\\cite{key}`` citations.  The
pre-processor here rewrites them into GitHub-style pipe tables and readable
citation markers before pandoc runs.  Conversion never raises — failures are
reported through :class:`DocxResult`.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_TABLE_ENV_RE = re.compile(
    r"\\begin\{table\*?\}(?:\[[^\]]*\])?(.*?)\\end\{table\*?\}", re.DOTALL
)
_TABULAR_RE = re.compile(
    r"\\begin\{tabular\*?\}\{[^{}]*\}(.*?)\\end\{tabular\*?\}", re.DOTALL
)
_CAPTION_RE = re.compile(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}")
_ROW_SPLIT_RE = re.compile(r"\\\\")
_CITE_RE = re.compile(r"\\cite[pt]?\{([^}]*)\}")
_DISPLAY_MATH_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
_H1_RE = re.compile(r"^#\s+\S", re.MULTILINE)
_INLINE_MATH_RE = re.compile(r"\$[^$]+\$")
_CELL_TOKEN = "\x00DOCX_CELL{}"
_STRAY_LINE_RE = re.compile(
    r"^\s*\\(?:hline|toprule|midrule|bottomrule|centering)\s*$", re.MULTILINE
)
_STRAY_LABEL_RE = re.compile(r"^\s*\\label\{[^}]*\}\s*$", re.MULTILINE)

_ESCAPES = (
    ("\\_", "_"), ("\\%", "%"), ("\\&", "&"), ("\\#", "#"),
    ("\\$", "$"), ("\\{", "{"), ("\\}", "}"),
)


@dataclass(frozen=True)
class DocxResult:
    """Outcome of a Markdown → DOCX conversion."""

    success: bool
    output_path: Path | None
    error: str = ""
    pandoc_available: bool = True
    warnings: tuple[str, ...] = ()


def pandoc_available() -> bool:
    """Return ``True`` when a ``pandoc`` executable is on ``PATH``."""
    return shutil.which("pandoc") is not None


def markdown_to_docx(
    markdown: str,
    out_path: Path,
    *,
    title: str | None = None,
    authors: str | None = None,
    bib_path: Path | None = None,
    reference_doc: Path | None = None,
    timeout: int = 120,
) -> DocxResult:
    """Convert *markdown* to a Word document at *out_path* via pandoc.

    When *bib_path* exists, ``--citeproc`` resolves ``\\cite{...}`` into
    author-year text; otherwise citations become plain ``[key; key]`` markers.
    *reference_doc* applies a Word style template.  All failures (missing
    pandoc, non-zero exit, timeout) are returned, never raised.

    Paths are resolved to absolute before pandoc runs so that passing a
    relative ``out_path`` (as the pipeline does) cannot make pandoc resolve
    ``-o`` against the working directory it is given.
    """
    out_path = Path(out_path).expanduser().resolve()
    bib_source = Path(bib_path).expanduser().resolve() if bib_path is not None else None
    reference_doc = (
        Path(reference_doc).expanduser().resolve() if reference_doc is not None else None
    )

    if not pandoc_available():
        logger.warning("DOCX export skipped — pandoc not installed")
        return DocxResult(
            False, None,
            "pandoc not installed; install pandoc to enable Word (.docx) export",
            False,
        )

    has_bib = bib_source is not None and bib_source.exists()
    body, warnings = _preprocess_markdown(markdown, has_bib=has_bib)
    body = _prepend_front_matter(body, title=title, authors=authors)
    command = _build_command(
        out_path, bib_source=bib_source if has_bib else None,
        reference_doc=reference_doc,
    )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            command, input=body, capture_output=True, text=True,
            timeout=timeout, cwd=str(out_path.parent),
        )
    except subprocess.TimeoutExpired:
        logger.warning("pandoc timed out after %ss", timeout)
        return DocxResult(False, None, f"pandoc timed out after {timeout}s")
    except Exception as exc:  # noqa: BLE001 — pandoc can fail in many ways
        logger.warning("pandoc invocation failed: %s", exc)
        return DocxResult(False, None, f"pandoc invocation failed: {exc}")

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        error = stderr[:1000] if stderr else f"pandoc exited with code {proc.returncode}"
        logger.warning("pandoc exited with code %s: %s", proc.returncode, error)
        return DocxResult(False, None, error)
    if not out_path.exists():
        return DocxResult(False, None, "pandoc reported success but produced no output")
    return DocxResult(True, out_path, warnings=tuple(warnings))


def _build_command(
    out_path: Path, *, bib_source: Path | None, reference_doc: Path | None
) -> list[str]:
    """Assemble the pandoc argv for a DOCX conversion."""
    command = [
        "pandoc", "--from", "markdown+tex_math_dollars+pipe_tables",
        "--to", "docx", "--standalone", "-o", str(out_path),
    ]
    if bib_source is not None:
        command += ["--citeproc", "--bibliography", str(bib_source)]
    if reference_doc is not None and reference_doc.exists():
        command += ["--reference-doc", str(reference_doc)]
    return command


def _preprocess_markdown(markdown: str, *, has_bib: bool) -> tuple[str, list[str]]:
    """Rewrite pandoc-dropped constructs into pandoc-friendly Markdown."""
    warnings: list[str] = []
    text = _DISPLAY_MATH_RE.sub(
        lambda m: f"$$\n{m.group(1).strip()}\n$$", markdown
    )
    text = _convert_citations(text, has_bib=has_bib, warnings=warnings)
    text = _TABLE_ENV_RE.sub(lambda m: _latex_table_to_pipe(m.group(0)), text)
    text = _TABULAR_RE.sub(
        lambda m: _rows_to_pipe_table(_parse_tabular_rows(m.group(1))), text
    )
    text = _STRAY_LINE_RE.sub("", text)
    text = _STRAY_LABEL_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text), warnings


def _convert_citations(text: str, *, has_bib: bool, warnings: list[str]) -> str:
    """Turn ``\\cite{a,b}`` into a readable marker pandoc keeps."""

    def _replace(match: re.Match[str]) -> str:
        keys = [key.strip() for key in match.group(1).split(",") if key.strip()]
        if not keys:
            warnings.append("Dropped an empty \\cite{} with no keys")
            return ""
        if has_bib:
            return "[" + "; ".join(f"@{key}" for key in keys) + "]"
        return "[" + "; ".join(keys) + "]"

    return _CITE_RE.sub(_replace, text)


def _latex_table_to_pipe(block: str) -> str:
    """Convert a raw LaTeX ``table`` environment into a Markdown pipe table."""
    caption_match = _CAPTION_RE.search(block)
    caption = (
        _clean_cell(caption_match.group(1)).replace("\\|", "|")
        if caption_match else ""
    )
    tabular_match = _TABULAR_RE.search(block)
    if not tabular_match:
        return f"**{caption}**" if caption else ""
    table = _rows_to_pipe_table(_parse_tabular_rows(tabular_match.group(1)))
    return f"**{caption}**\n\n{table}" if caption else table


def _parse_tabular_rows(body: str) -> list[list[str]]:
    """Split tabular body text into cleaned cell rows."""
    body = re.sub(r"\\\\(?:hline|toprule|midrule|bottomrule)\b", "", body)
    body = re.sub(r"\\hline|\\toprule|\\midrule|\\bottomrule", "", body)
    body = re.sub(r"\\cmidrule(?:\([^)]*\))?\{[^}]*\}", "", body)
    rows: list[list[str]] = []
    for raw_row in _ROW_SPLIT_RE.split(body):
        if not raw_row.strip():
            continue
        cells = [_clean_cell(cell) for cell in raw_row.split("&")]
        if any(cells):
            rows.append(cells)
    return rows


def _clean_cell(cell: str) -> str:
    """Strip LaTeX wrappers from a single table cell / caption."""
    protected: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return _CELL_TOKEN.format(len(protected) - 1)

    text = _INLINE_MATH_RE.sub(_stash, cell)
    text = re.sub(
        r"\\multicolumn\{\d+\}\{[^{}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", text
    )
    text = re.sub(
        r"\\multirow\{\d+\}\{[^{}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", text
    )
    text = re.sub(
        r"\\(?:textbf|textit|emph|texttt|mathrm|mathbf|text)\{([^{}]*)\}", r"\1", text
    )
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(
        r"\\(?:hline|toprule|midrule|bottomrule|centering|resizebox"
        r"|small|footnotesize|scriptsize|tiny|large|Large|bfseries|itshape|ttfamily)\b",
        "", text,
    )
    for escaped, plain in _ESCAPES:
        text = text.replace(escaped, plain)
    text = re.sub(r"\\[a-zA-Z]+\{[^{}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    for index, value in enumerate(protected):
        text = text.replace(_CELL_TOKEN.format(index), value)
    return re.sub(r"\s+", " ", text.replace("|", "\\|")).strip()


def _rows_to_pipe_table(rows: list[list[str]]) -> str:
    """Render parsed rows as a GitHub-style pipe table."""
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalised = [(row + [""] * width)[:width] for row in rows]
    lines = [
        "| " + " | ".join(normalised[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in normalised[1:])
    return "\n".join(lines)


def _prepend_front_matter(
    body: str, *, title: str | None, authors: str | None
) -> str:
    """Prepend a title block only when the draft has no top-level heading."""
    if not title or _H1_RE.search(body):
        return body
    parts = [f"# {title}"]
    if authors:
        parts.append(f"*{authors}*")
    return "\n\n".join(parts) + "\n\n" + body
