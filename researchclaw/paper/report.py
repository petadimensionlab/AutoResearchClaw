"""Tolerant markdown parsing of a user-supplied analysis-results report.

The ``researchclaw paper`` workflow starts from a free-form markdown report
(findings + metrics) instead of a fresh literature search and experiment run.
This module extracts the structured pieces the paper-construction stages need
(title, abstract, sections, keywords, metrics, numeric values, embedded
BibTeX) without ever failing on missing sections — everything degrades to an
empty value rather than raising.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches a plain integer/float/decimal token, optional sign and exponent.
_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])")
# `# Title` (exactly one leading '#', so '## ...' never matches).
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
# `## Heading` or `### Heading`.
_SECTION_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
# `Abstract` heading (any level).
_ABSTRACT_RE = re.compile(r"^#{1,6}\s+abstract\b", re.IGNORECASE)
# `Keywords:` / `*Keywords*:` / `**Keywords:**` — value on the same line.
_KEYWORDS_RE = re.compile(
    r"^\s*\*{0,2}keywords\*{0,2}\s*:\s*(.+?)\s*$", re.IGNORECASE
)
# Fenced ```bibtex / ```bib block.
_BIB_RE = re.compile(r"```(?:bibtex|bib)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
# A markdown table row: starts and ends with a pipe.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
# A table alignment separator row such as |---|---|:---|
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")

_EMPTY_REPORT_TITLE = "Untitled Analysis Report"


@dataclass(frozen=True)
class AnalysisReport:
    """Structured view over a markdown analysis-results report."""

    source_path: Path
    title: str
    abstract: str
    body: str
    sections: tuple[tuple[str, str], ...]
    keywords: tuple[str, ...]
    metrics: tuple[tuple[str, float], ...]
    numeric_values: tuple[float, ...]
    embedded_bib: str


def _clean_inline(text: str) -> str:
    """Strip common markdown emphasis/code markers from an inline value."""
    cleaned = text.strip()
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = re.sub(r"`(.+?)`", r"\1", cleaned)
    return cleaned.strip()


def _parse_float(cell: str) -> float | None:
    """Parse a table cell into a float, tolerating %, commas and currency."""
    candidate = _clean_inline(cell)
    if not candidate:
        return None
    candidate = candidate.replace(",", "").replace("%", "").replace("$", "")
    candidate = candidate.strip()
    # Reject cells that contain no digit at all (e.g. labels, em-dashes).
    if not re.search(r"\d", candidate):
        return None
    try:
        return float(candidate)
    except (ValueError, OverflowError):
        return None


def _extract_title(lines: list[str]) -> str:
    for line in lines:
        match = _H1_RE.match(line)
        if match:
            title = _clean_inline(match.group(1))
            if title:
                return title
    return _EMPTY_REPORT_TITLE


def _heading_level(line: str) -> int:
    match = re.match(r"^(#{1,6})\s+", line)
    return len(match.group(1)) if match else 0


def _extract_abstract(lines: list[str]) -> str:
    """Return the Abstract section, else the first non-heading paragraph."""
    for idx, line in enumerate(lines):
        if _ABSTRACT_RE.match(line):
            collected: list[str] = []
            for following in lines[idx + 1 :]:
                if _heading_level(following) or _KEYWORDS_RE.match(following):
                    break
                collected.append(following)
            abstract = "\n".join(collected).strip()
            if abstract:
                return abstract

    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _heading_level(line):
            if paragraph:
                break
            continue
        if not stripped:
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    return "\n".join(paragraph).strip()


def _extract_sections(lines: list[str]) -> tuple[tuple[str, str], ...]:
    """Collect (heading, content) pairs for all ``##``/``###`` headings."""
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        if current_heading is not None:
            sections.append((current_heading, "\n".join(current_body).strip()))

    for line in lines:
        match = _SECTION_RE.match(line)
        if match:
            flush()
            current_heading = _clean_inline(match.group(2))
            current_body = []
            continue
        if current_heading is not None:
            current_body.append(line)
    flush()
    return tuple(sections)


def _extract_keywords(text: str) -> tuple[str, ...]:
    for raw_line in text.splitlines():
        match = _KEYWORDS_RE.match(raw_line)
        if not match:
            continue
        raw = _clean_inline(match.group(1))
        parts = [p.strip() for p in re.split(r"[,;]", raw) if p.strip()]
        if parts:
            return tuple(parts)
    return ()


def _extract_metrics(lines: list[str]) -> tuple[tuple[str, float], ...]:
    """Parse markdown pipe tables: first column label, first later numeric col."""
    metrics: list[tuple[str, float]] = []
    index = 0
    total = len(lines)
    while index < total:
        if not _TABLE_ROW_RE.match(lines[index]):
            index += 1
            continue
        # Gather the contiguous table block.
        block: list[str] = []
        while index < total and _TABLE_ROW_RE.match(lines[index]):
            block.append(lines[index])
            index += 1
        if len(block) < 2:
            continue
        header_cells = _split_row(block[0])
        if not header_cells:
            continue
        # Skip the alignment separator directly under the header.
        data_rows = block[1:]
        if data_rows and _TABLE_SEP_RE.match(data_rows[0]):
            data_rows = data_rows[1:]
        for row in data_rows:
            cells = _split_row(row)
            if len(cells) < 2:
                continue
            label = _clean_inline(cells[0])
            if not label:
                continue
            for cell in cells[1:]:
                value = _parse_float(cell)
                if value is not None:
                    metrics.append((label, value))
                    break
    return tuple(metrics)


def _split_row(row: str) -> list[str]:
    stripped = row.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _extract_numeric_values(text: str) -> tuple[float, ...]:
    """Every int/float token in the report, deduped, order-preserving."""
    seen: set[float] = set()
    values: list[float] = []
    for token in _NUMBER_RE.findall(text):
        try:
            value = float(token)
        except (ValueError, OverflowError):
            continue
        if value not in seen:
            seen.add(value)
            values.append(value)
    return tuple(values)


def _extract_embedded_bib(text: str) -> str:
    match = _BIB_RE.search(text)
    if match is None:
        return ""
    return match.group(1).strip()


def load_analysis_report(path: Path | str) -> AnalysisReport:
    """Parse a markdown analysis-results report into an :class:`AnalysisReport`.

    Raises
    ------
    FileNotFoundError
        When *path* does not point at an existing file.
    """
    report_path = Path(path).expanduser()
    if not report_path.is_file():
        raise FileNotFoundError(
            f"Analysis report not found: {report_path} "
            "(expected an existing markdown file)."
        )

    text = report_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    metrics = _extract_metrics(lines)
    # Fold metric values into numeric_values so grounding is always complete.
    numeric_values = _extract_numeric_values(text)
    known = set(numeric_values)
    extra = [value for _, value in metrics if value not in known]
    if extra:
        numeric_values = numeric_values + tuple(extra)

    return AnalysisReport(
        source_path=report_path,
        title=_extract_title(lines),
        abstract=_extract_abstract(lines),
        body=text,
        sections=_extract_sections(lines),
        keywords=_extract_keywords(text),
        metrics=metrics,
        numeric_values=numeric_values,
        embedded_bib=_extract_embedded_bib(text),
    )
