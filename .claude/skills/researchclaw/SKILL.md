---
name: researchclaw
description: Run the ResearchClaw autonomous research pipeline from a topic, config, and output directory.
---

# ResearchClaw — Autonomous Research Pipeline Skill

## Description

Run ResearchClaw's 23-stage autonomous research pipeline. Given a research topic, this skill orchestrates the entire research workflow: literature review → hypothesis generation → experiment design → code generation & execution → result analysis → paper writing → peer review → final export.

## Trigger Conditions

Activate this skill when the user:
- Asks to "research [topic]", "write a paper about [topic]", or "investigate [topic]"
- Wants to run an autonomous research pipeline
- Asks to generate a research paper from scratch
- Mentions "ResearchClaw" by name

## Instructions

### Prerequisites Check

1. Verify config file exists:
   ```bash
   ls config.yaml || ls config.researchclaw.example.yaml
   ```
2. If no `config.yaml`, create one from the example:
   ```bash
   cp config.researchclaw.example.yaml config.yaml
   ```
3. Ensure the user's LLM API key is configured in `config.yaml` under `llm.api_key` or via `llm.api_key_env` environment variable.

### Running the Pipeline

**Option A: CLI (recommended)**

```bash
researchclaw run --topic "Your research topic here" --auto-approve
```

Options:
- `--topic` / `-t`: Override the research topic from config
- `--config` / `-c`: Config file path (default: `config.yaml`)
- `--output` / `-o`: Output directory (default: `artifacts/rc-YYYYMMDD-HHMMSS-HASH/`)
- `--from-stage`: Resume from a specific stage (e.g., `PAPER_OUTLINE`)
- `--auto-approve`: Auto-approve gate stages (5, 9, 20) without human input

**Option B: Python API**

```python
from researchclaw.pipeline.runner import execute_pipeline
from researchclaw.config import RCConfig
from researchclaw.adapters import AdapterBundle
from pathlib import Path

config = RCConfig.load("config.yaml", check_paths=False)
results = execute_pipeline(
    run_dir=Path("artifacts/my-run"),
    run_id="research-001",
    config=config,
    adapters=AdapterBundle(),
    auto_approve_gates=True,
)

# Check results
for r in results:
    print(f"Stage {r.stage.name}: {r.status.value}")
```

**Option C: Iterative Pipeline (multi-round improvement)**

```python
from researchclaw.pipeline.runner import execute_iterative_pipeline

results = execute_iterative_pipeline(
    run_dir=Path("artifacts/my-run"),
    run_id="research-001",
    config=config,
    adapters=AdapterBundle(),
    max_iterations=3,
    convergence_rounds=2,
)
```

**Option D: Paper-only mode (no literature search or experiments)**

Build a paper from a markdown analysis report by running only the paper-construction stages (16-23). The command seeds a run directory from the report and sets `research.project_mode = "docs-first"` so the anti-fabrication gates treat the report as the grounding source.

```bash
researchclaw paper --report analysis_report.md --output artifacts/my-paper \
    --topic "My analysis" --authors "A. Author" --output-format docx
```

```python
from researchclaw.paper import build_paper_from_report

result = build_paper_from_report("analysis_report.md", "artifacts/my-paper", output_format="docx")
print(result.paper_docx, result.ok)
```

The report may include a title (`# ...`), an optional `## Abstract`, findings, optional metric tables (pipe tables with a label column and a numeric column), and an optional fenced `bibtex` block. Missing sections degrade gracefully. On success the command prints the `paper_final.md`, `paper.docx`, `paper.tex`, and `references.bib` paths.

### Export Formats

`export.output_format` controls the primary deliverable:

| Value | Output |
|-------|--------|
| `docx` (default) | `paper.docx` via pandoc; `paper.tex` is still emitted, PDF compilation is skipped |
| `latex` | `paper.tex` + compiled `paper.pdf` |
| `both` | markdown + docx + LaTeX + compiled PDF |

`export.docx_reference` optionally points to a pandoc reference `.docx` for Word styling. If `pandoc` is missing, docx export logs a warning and the run continues; the other artifacts are still produced.

### Output Structure

After a successful run, the output directory contains:

```
artifacts/<run-id>/
├── stage-1/                # TOPIC_INIT outputs
├── stage-2/                # PROBLEM_DECOMPOSE outputs
├── ...
├── stage-10/
│   └── experiment.py       # Generated experiment code
├── stage-12/
│   └── runs/run-1.json     # Experiment execution results
├── stage-14/
│   ├── experiment_summary.json  # Aggregated metrics
│   └── results_table.tex        # LaTeX results table
├── stage-17/
│   └── paper_draft.md      # Full paper draft
├── stage-22/
│   ├── paper_final.md      # Final paper (Markdown)
│   ├── paper.docx          # Word document (default export via pandoc)
│   ├── paper.tex           # LaTeX source (PDF only with output_format: latex|both)
│   └── charts/             # Generated visualizations
│       ├── metric_trajectory.png
│       └── experiment_comparison.png
└── pipeline_summary.json   # Overall pipeline status
```

### Experiment Modes

| Mode | Description | Config |
|------|-------------|--------|
| `simulated` | LLM generates synthetic results (no code execution) | `experiment.mode: simulated` |
| `sandbox` | Execute generated code locally via subprocess | `experiment.mode: sandbox` |
| `ssh_remote` | Execute on remote GPU server via SSH | `experiment.mode: ssh_remote` |

### Resuming an existing run

Before continuing an in-flight run, read **`docs/HANDOVER.md`** (current state, exact commands,
blockers, traps) and **`docs/REPORT_GENERATION_FAILURES.md`** (symptom → root cause → commit).

Key points for this repo:

- Run from the **repo root** (`config.arc.yaml` is gitignored, so config edits are local-only).
- The ACP session model is **sticky at creation** — after changing a model, run
  `acpx --ttl 0 --cwd <repo> opencode sessions close researchclaw` then `... sessions ensure --name researchclaw`.
- Stage 20 (QUALITY_GATE) sanitizes the paper **before** judging it; if fabricated numbers appear in a
  quality report, check that `_sanitize_prose_numbers()` ran (the log line is
  `Stage 20: blanked N numbers not grounded in the experiment before quality judging`).
- Pipeline logs are block-buffered: verify liveness with the acpx stream file size, not log silence.

### Troubleshooting

Baseline checks:
- **Config validation error**: Run `researchclaw validate --config config.yaml`
- **LLM connection failure**: Check `llm.base_url` and API key
- **Sandbox execution failure**: Verify `experiment.sandbox.python_path` exists and has numpy installed
- **Gate rejection**: Use `--auto-approve` or manually approve at stages 5, 9, 20

Field notes — failures seen in real long runs (details in README "Troubleshooting (field notes)"):

**ACP backend (`llm.provider: acp`)**
- `Stage NN … ACP prompt failed (exit 1)` where stderr only shows `[acpx] session … agent connected`: the real error is in acpx's own log. Always read `~/.acpx/sessions/<id>.stream.ndjson` and look for `"error":{…}` before anything else.
- `Failed to authenticate: OAuth session expired` → re-login the ACP agent CLI (e.g. `claude` → `/login`).
- `Reached maximum number of turns (N)` → `llm.acp.max_turns` too low; the agent needed a tool call. Raise it (heavy stages need ~120).
- `ACP prompt timed out after 1800s` → raise `llm.acp.timeout_sec` (slow local models need 14400+).
- `ConnectionRefused http://<host>:8000/v1/chat/completions` retried every ~30s → the model endpoint is down, or bound to `127.0.0.1` on a remote host. Bind `0.0.0.0` and verify `curl http://<host>:8000/v1/models`; the run resumes once it is up.
- `You've hit your session limit` (`errorKind: rate_limit`) → wait for the reset or switch provider; resume with `--from-stage`.
- **No log output does not mean stuck**: opencode logs only call start/end. Check liveness by sampling the acpx stream file size twice (`wc -c ~/.acpx/sessions/<id>.stream.ndjson`); growing = alive.
- Multi-hour sessions can stall for ~20 min in **compaction** (context bloat). Prefer re-running a heavy stage over letting one session grow unbounded.

**Literature (Stage 5 pause)**
- `LITERATURE_SCREEN -- PAUSED: Model returned empty shortlist after strict screening` → the strict domain-aware screen rejects everything when `research.domains` does not match the topic's real field (e.g. a social-science topic declared as `machine-learning`). Fix `research.domains`, then resume `--from-stage LITERATURE_SCREEN` (Stage 5 re-reads Stage 4's `candidates.jsonl`; no re-search).

**Malformed model output (silent fallbacks)**
- `stage-03/queries.json: "model_queries_extracted": false` with topic n-gram queries → the model returned invalid YAML (`key:value` with no space, bad list indent) and the parser fell back silently. Fix with a `search_strategy` prompt override.
- Generated code fails `ast.parse` with `SyntaxError: invalid syntax (line 1)` on every repair → the model emitted a bare `:main.py` line instead of the required ` ```filename:main.py ` fence. Fix with a `code_generation` prompt override.

**Prompt overrides gotcha**
- `prompts.extra_prompts` with inline multi-line text fails with `OSError: File name too long` in `_load_extras`. Always point to a **file**:
  ```yaml
  prompts:
    extra_prompts:
      search_strategy: ./prompts/search_strategy_rules.md
      code_generation: ./prompts/code_generation_rules.md
  ```

**Beast Mode (OpenCode)**
- `OpenCode succeeded but no main.py found (files: [])` → `opencode run` resolved its project to the repo root instead of the temp workspace. **Fixed**: the bridge passes `--dir <workspace>`. If it recurs, verify `--dir` is present and raise `experiment.opencode.timeout_sec`.
- `TIMEOUT after 1800.0s` → raise `experiment.opencode.timeout_sec`.
- OpenRouter free models `404 ZDR violation (account settings)` → adjust `https://openrouter.ai/settings/privacy`, or use OpenCode Zen free models (`opencode/<id>-free`), which need no auth.

**Export**
- `pdflatex not installed` → install a TeX distribution and the missing `.sty` packages (`tlmgr install …`), or compile `paper.tex` on Overleaf. The pipeline degrades gracefully.
- **No `paper.docx`** → `pandoc` is not installed (or not on `PATH`). Install it, or set `export.output_format: "latex"`. Docx export degrades gracefully: the run continues with a warning and the other artifacts are still produced.

**Not wired in v0.5.0**
- `experiment.cli_agent.provider` (`claude_code` / `codex`) is implemented (`create_code_agent`) but never called; Stage 10 uses the main LLM unless Beast Mode is enabled.

## Tools Required

- File read/write (for config and artifacts)
- Bash (for CLI execution)
- No external MCP servers required for basic operation
