#!/usr/bin/env python3
"""Review-only pass with a reasoning model over key pipeline artifacts.

Runs the base reasoning model (default ``qwen3.8-flash-next``) as an independent
reviewer over the artifacts produced by a completed run, WITHOUT touching the
pipeline outputs. Results are written to ``<run_dir>/base_review/`` so the
reasoning critique can be integrated by hand or a separate path. This keeps the
reasoning model out of the pipeline, where it can return empty content under a
fixed token budget and fail stages.

Usage:
    python scripts/base_review.py <run_dir> [--model NAME] [--base-url URL]
        [--out DIR] [--max-tokens N] [--stages 8,14,15,18,20]

The default endpoint is the ds4.c server; override with --base-url.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "http://100.86.6.79:8000/v1"
DEFAULT_MODEL = "qwen3.8-flash-next"

# (stage number, artifact filename, short purpose used in the review prompt)
TARGETS: tuple[tuple[int, str, str], ...] = (
    (8, "hypotheses.md", "the generated research hypotheses"),
    (14, "analysis.md", "the result-analysis report"),
    (15, "decision.md", "the PROCEED/PIVOT research decision"),
    (17, "paper_draft.md", "the paper draft"),
    (18, "reviews.md", "the peer-review report"),
    (20, "quality_report.json", "the quality-gate report"),
)

SYSTEM = (
    "You are a rigorous, skeptical senior researcher reviewing another agent's work. "
    "Be specific and concise. Do not invent facts about the work; base every criticism "
    "on the provided artifact."
)

USER_TEMPLATE = (
    "Artifact: {name} (pipeline stage {stage}) — {purpose}.\n"
    "Research topic: {topic}\n\n"
    "----- BEGIN ARTIFACT -----\n{content}\n----- END ARTIFACT -----\n\n"
    "Critically review it. Return markdown with exactly these sections:\n"
    "## Strengths\n## Critical weaknesses\n## Unsupported or unverifiable claims\n"
    "## Concrete improvements\n"
)


def _chat(base_url: str, model: str, system: str, user: str, max_tokens: int, timeout: int) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        obj = json.loads(resp.read().decode("utf-8", "replace"))
    choice = obj["choices"][0]
    message = choice.get("message", {})
    return {
        "content": message.get("content") or "",
        "reasoning": message.get("reasoning_content") or "",
        "finish": choice.get("finish_reason"),
        "usage": obj.get("usage", {}),
        "seconds": time.time() - t0,
    }


def _find_artifact(run_dir: Path, filename: str) -> Path | None:
    candidates = sorted(run_dir.glob(f"stage-*/{filename}"), reverse=True)
    for candidate in candidates:
        if "_v" not in candidate.parent.name and candidate.is_file():
            return candidate
    return candidates[0] if candidates else None


def _topic(run_dir: Path) -> str:
    goal = run_dir / "stage-01" / "goal.md"
    if goal.is_file():
        for line in goal.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                return line.strip()
    return "(unknown)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--out", default=None, help="Output dir (default: <run_dir>/base_review)")
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--stages", default="", help="Comma-separated stage numbers to review")
    args = parser.parse_args()

    run_dir: Path = args.run_dir
    if not run_dir.is_dir():
        print(f"ERROR: run dir not found: {run_dir}")
        return 1
    out_dir = Path(args.out) if args.out else run_dir / "base_review"
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = {int(s) for s in args.stages.split(",") if s.strip()} if args.stages else None
    topic = _topic(run_dir)
    index: list[dict[str, object]] = []

    for stage, filename, purpose in TARGETS:
        if wanted is not None and stage not in wanted:
            continue
        artifact = _find_artifact(run_dir, filename)
        if artifact is None:
            print(f"skip stage {stage:>2}: {filename} not found")
            continue
        content = artifact.read_text(encoding="utf-8", errors="replace")
        if len(content) > 60000:
            content = content[:60000] + "\n\n[...truncated for review...]"
        user = USER_TEMPLATE.format(
            name=filename, stage=stage, purpose=purpose, topic=topic, content=content
        )
        print(f"reviewing stage {stage:>2} ({filename}, {len(content)} chars) with {args.model} ...")
        result = _chat(args.base_url, args.model, SYSTEM, user, args.max_tokens, args.timeout)
        # The reasoning model can return empty content under budget pressure; retry bigger.
        if not result["content"].strip():
            print("  empty content — retrying with 2x tokens")
            result = _chat(args.base_url, args.model, SYSTEM, user, args.max_tokens * 2, args.timeout)
        target = out_dir / f"stage-{stage:02d}_{filename.replace('.', '_')}_base_review.md"
        target.write_text(
            f"# Base review — stage {stage} ({filename})\n"
            f"model={args.model} finish={result['finish']} seconds={result['seconds']:.1f} "
            f"usage={result['usage']}\n\n"
            "## Review\n\n" + (result["content"] or "(EMPTY — model returned no content)") +
            ("\n\n## Reasoning trace\n\n" + result["reasoning"] if result["reasoning"] else ""),
            encoding="utf-8",
        )
        index.append({
            "stage": stage,
            "artifact": str(artifact.relative_to(run_dir)),
            "review": target.name,
            "content_chars": len(result["content"]),
            "reasoning_chars": len(result["reasoning"]),
            "finish": result["finish"],
            "seconds": round(result["seconds"], 1),
        })
        print(f"  -> {target.name} ({len(result['content'])}c, finish={result['finish']})")

    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nDone. {len(index)} review(s) written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
