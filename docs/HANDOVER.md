# HANDOVER — read this first

Continuation notes for the AutoResearchClaw paper-generation effort.
Last updated: 2026-09-19 (session that fixed the anti-fabrication sanitization chain).

Read order for a fresh session:

1. **this file** (state, commands, blockers),
2. [`docs/REPORT_GENERATION_FAILURES.md`](REPORT_GENERATION_FAILURES.md) (B1–B23 failure
   catalogue with root causes and commits),
3. [`README.md` → Troubleshooting](../README.md#-troubleshooting-field-notes) and
   [`.claude/skills/researchclaw/SKILL.md`](../.claude/skills/researchclaw/SKILL.md)
   (infrastructure failures: ACP, providers, paths).

---

## 1. Objective and acceptance criteria

Produce a **credible end-to-end paper** on

> "What is the outcome of infectious generocity in promoting nature positive activities?"

acceptance criteria, in priority order:

1. **No fabricated numbers.** Every number in the paper must be traceable to
   `stage-12/runs/*.json` / `stage-14*/experiment_summary.json`.
2. **Real citations preserved through revision** (`references.bib` keys exist, integrity ≥ 0.9).
3. **Quality gate passes** (`stage-20/quality_report.json`, threshold from
   `research.quality_threshold`, currently **3.0**).
4. PDF ≤ 10 pages (conference limit).

Cost constraint: free/local models preferred. The only sanctioned paid model is
`opencode-go/deepseek-v4.1-flash`. Never use `opencode-go/kimi-k2.6`.

---

## 2. How to run (exact commands)

```bash
cd /Users/petadimensionlab/workspace/research/AutoResearchClaw   # MUST run from repo root
```

```bash
# reset the sticky ACP session after ANY model/config change, then run
acpx --ttl 0 --cwd /Users/petadimensionlab/workspace/research/AutoResearchClaw \
  opencode sessions close researchclaw
acpx --ttl 0 --cwd /Users/petadimensionlab/workspace/research/AutoResearchClaw \
  opencode sessions ensure --name researchclaw

R=artifacts/rc-20260914-033427-5a0aab
nohup .venv/bin/researchclaw run --config config.arc.yaml \
  --topic "What is the outcome of infectious generocity in promoting nature positive activities?" \
  --output "$R" --from-stage EXPORT_PUBLISH --auto-approve > "$R/rerun.log" 2>&1 &
```

Useful `--from-stage` values: `QUALITY_GATE` (20), `PAPER_REVISION` (19), `PAPER_DRAFT` (17),
`EXPORT_PUBLISH` (22), `CITATION_VERIFY` (23).

**Liveness** (logs are block-buffered; silence ≠ stuck):

```bash
S=$(ls -t ~/.acpx/sessions/ses_*.stream.ndjson | head -1); wc -c "$S"; sleep 20; wc -c "$S"
```

**ACP ground truth** — the pipeline only prints the last acpx line; the real error is:

```bash
grep -o '"error":{[^}]*}' ~/.acpx/sessions/<id>.stream.ndjson | tail -3
```

Rough stage costs: Stage 20 ≈ 8–14 min, Stage 22 ≈ 7–8 min, Stage 23 ≈ 1 min.

---

## 3. Environment

| Item | Value |
|---|---|
| Repo / cwd | `/Users/petadimensionlab/workspace/research/AutoResearchClaw` |
| Shared run dir | `artifacts/rc-20260914-033427-5a0aab/` (each resume creates a new `run_id`) |
| Config | `config.arc.yaml` (**gitignored** — local-only edits) |
| Project model | `opencode.json` → `opencode/mimo-v2.5-free` |
| Global default | `~/.config/opencode/opencode.json` → `opencode-go/deepseek-v4.1-flash` |
| Fallbacks | `opencode/nemotron-3-ultra-free`, `opencode/mimo-v2.5-free` |
| Deliverables | `artifacts/rc-20260914-033427-5a0aab/deliverables/` |
| Python | `.venv/bin/python` (**pytest is NOT installed**; use `ruff` globally) |
| Known-bad | `opencode/kimi-k2.6*` (forbidden), `union-alpha` (server error) |

---

## 4. What is fixed and verified

Commits (newest first) — all on the working branch:

| Commit | Fix |
|---|---|
| `fd33c83` | Quality gate sanitizes **before** judging (was: only at export, after the gate) |
| `6f644fc` | Number matching at written precision + blank ungrounded `p`/`d`/`r` claims |
| `2cf9bc5` | Prose sanitization extended to Abstract/Intro/Discussion/Conclusion |
| `a20079a` | Prose pass ran only when `numbers_replaced == 0` → never after a table fix |
| `235a3bb` | Sanitize even when the experiment is marked "successful" |
| `c8a3cb1` | Forbid fabricated statistics in prompts; scope lessons to the current run |
| `717f752` | Keep the unrevised draft when the revision is < 80 % of draft length |
| `65aeba2` | Resolve sandbox python without symlinks |

Older: `b6dba07`, `375b46d`, `0b4a2a8`, `ec9df7c`, `a9f7f63`, `81c43a6`, `dc81844`, `470d924`, `1e34a69`.

Verified evidence:

- **Prose sanitization works end-to-end**: Stage 20 logs
  `Stage 20: blanked 174 numbers not grounded in the experiment before quality judging`;
  Stage 22 logs `blanked 162 unsupported numbers`. In `deliverables/paper_final.md` the invented
  claims `34.2%`, `Cohen's d = 0.67`, `p < 0.001`, `p = 0.03`, `d = 0.21` now all count **0**.
- The shared helper `_sanitize_prose_numbers(text, real_values)` in
  `researchclaw/pipeline/stage_impls/_review_publish.py` was unit-checked: real values survive
  (`0.2472`), Method/Setup is untouched (`lr=0.001`), narrative sections are blanked.
- `ruff check` clean on the modified file.

The sanitization design (do not "simplify" this away — each rule fixed a real bug):

1. It runs whenever real values are known (`has_real_data`), **not** only when
   `fabrication_suspected` (that flag is true only when the experiment failed *and* had no data).
2. Numbers are compared **at the precision the author wrote**. A 1-decimal match made every value
   below 0.05 equal to a real `0.0` metric.
3. `p`, `d`, `r` claims are blanked outright: a real `0.001` metric does not license `p < 0.001`.
4. Method/Setup is excluded so hyperparameters survive.

---

## 5. Current state / last measurements (2026-09-19 22:18)

| Metric | Value |
|---|---|
| Fabrication (invented decimals) | **eliminated** |
| Quality gate | **2.8 / 10**, verdict `REJECT` (threshold 3.0) |
| Gate reason | "extensive placeholder values (`--`) … template rather than a completed manuscript" |
| PDF visual review | 3/10 — "catastrophically insufficient empirical validation" |
| Verified citations | 19 (18 verified, score 0.947) |
| Pages | 22 (limit 10) |
| Experiment | **degenerate**: `adoption_rate 0.0`, only 1 of 18 claimed conditions ran |

**The bottleneck moved.** Fabrication is fixed; the paper is now rejected for being *hollow* and
because the underlying experiment is degenerate. Further sanitization will not raise the score —
the experiment must produce differentiated, non-degenerate conditions.

---

## 6. Open blockers (ordered)

1. **Degenerate experiment** (B11/B17). Only 1 condition runs; `adoption_rate: 0.0`.
   Stage 22 reports `Paper claims 18 conditions/methods but only 1 ran`. Fix here first —
   everything else is downstream.
2. **Quality gate threshold** (B15). 2.8 vs 3.0. Once the experiment is real, re-run Stage 20.
3. **Page count** (B5). 22 pages vs 10. Stage 22 already warns (`BUG-27`).
4. **Unsanitized integer percentages** (B23). `62%`, `8-12%` in the Abstract are still unverified;
   only decimal tokens are sanitized today.
5. **Truncated section** — `Field experiment description is truncated mid-sentence at section 4.1`.
6. **Unreferenced figures** — 7 figures defined but never referenced.
7. **Docker figure image** missing (`researchclaw/experiment:latest`) — FigureAgent falls back; harmless.

---

## 7. Traps and gotchas

- **Never** print or repeat a plan without executing; the repo owner's global rules
  (`~/.config/opencode/AGENTS.md`) forbid paid-API calls without per-occurrence approval.
- The ACP session model is **sticky at creation**. After changing the model you must close and
  re-ensure the session (see §2), otherwise the old model keeps serving requests.
- `_read_prior_artifact` returns the first match in **reverse-sorted** order — a stale file in a
  higher-numbered stage shadows the real one.
- `stage-20/fabrication_flags.json` (mechanical) and `stage-20/quality_report.json` (LLM judge)
  **disagree by design**. Trust the mechanical flags for numbers; the judge is the gate.
- `config.arc.yaml` is gitignored, so config changes never appear in a diff — record them in the PR
  description or here instead.
- Time is not a liveness signal; always verify with the acpx stream file (§2).

---

## 8. Next actions (suggested order)

1. Fix the degenerate experiment: regenerate Stage 10 with the differentiation rules, confirm
   ≥ 2 conditions produce **different** metrics, then re-run 12 → 14.
2. Re-run Stage 20 (`--from-stage QUALITY_GATE`) and read
   `stage-20/quality_report.json` → `score_1_to_10`, `weaknesses`.
3. Extend `_sanitize_prose_numbers` to integer percentages (B23) if the abstract still asserts them.
4. Compress to ≤ 10 pages (B5) — reduce figures/tables rather than prose.
5. Re-verify citations after any regeneration (`stage-23/verification_report.json`).

## 9. Verification commands

```bash
R=artifacts/rc-20260914-033427-5a0aab
grep -aE "blanked|Sanitizing|REJECTED" "$(ls -t "$R"/rerun*.log | head -1)"   # sanitization trace
python - <<'PY'
import json
d = json.load(open("artifacts/rc-20260914-033427-5a0aab/stage-20/quality_report.json"))
print(d.get("score_1_to_10"), "|", str(d.get("verdict"))[:120])
PY
.venv/bin/python -c "
from researchclaw.pipeline.stage_impls._review_publish import _sanitize_prose_numbers
print(_sanitize_prose_numbers('## Abstract\nn=0.67 (p < 0.001)', [0.2472]))"
```
