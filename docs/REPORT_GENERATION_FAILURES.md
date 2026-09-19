# Report-Generation Failures — Analysis and Resolutions

Recorded from a multi-day autonomous run of the pipeline on the topic
**"What is the outcome of infectious generocity in promoting nature positive activities?"**
(run `rc-20260914-033427-5a0aab`, resumed many times across 2026-09-12 → 2026-09-18).

This document covers **Category B failures**: the pipeline ran, but the *report/paper did not come
out as expected* (wrong content, lost citations, degenerate text, no-op experiments). Pure
infrastructure failures (auth, endpoints, timeouts, client versions) are documented separately in
[README → Troubleshooting](../README.md#-troubleshooting-field-notes) and
[`.claude/skills/researchclaw/SKILL.md`](../.claude/skills/researchclaw/SKILL.md).

---

## Summary

| ID | Failure (symptom) | Root cause | Resolution | Status |
|----|-------------------|------------|------------|--------|
| B1 | `Stage 05 LITERATURE_SCREEN — PAUSED: Model returned empty shortlist after strict screening` | `research.domains: [machine-learning]` did not match a social-science topic; the strict cross-domain screen rejected every candidate | Set `research.domains` to 4 matching disciplines; resume `--from-stage LITERATURE_SCREEN` (no re-search needed) | ✅ Fixed |
| B2 | Experiment generated was CIFAR-10 image classification, unrelated to the topic | BenchmarkAgent auto-selected an ML dataset | `experiment.benchmark_agent.enabled: false` | ✅ Fixed |
| B3 | `experiment_spec.md` claimed `Topic-Experiment Alignment: ALIGNED` while the code was off-topic | Alignment check is cosmetic (string only) | Not fixed (display only) | ⚠️ Open |
| B4 | Stage 3 queries were topic n-grams (`"what outcome"`), `queries.json: model_queries_extracted: false` | Model returned invalid/truncated JSON+YAML; parser silently fell back | Parser made tolerant (`strategies` key, direct-YAML response); prompt switched to "return YAML only"; the model output was applied directly once | ✅ Mitigated |
| B5 | Generated code began with `:main.py` → `SyntaxError: invalid syntax (line 1)` survived 5 repairs | Model ignored the required ` ```filename:xxx.py ` fence | `prompts/code_generation_rules.md` enforces the exact fence + `ast.parse`-able Python | ✅ Fixed |
| B6 | `Stage 15 RESEARCH_DECISION -- PAUSED: Model decision response contained no PROCEED/PIVOT/REFINE keyword` (twice) | Model omitted the decision keyword | `prompts/research_decision_rules.md` requires a `## Decision` heading followed by the keyword on its own line | ✅ Fixed |
| B7 | Paper had only **2 citations** | Draft used author-year cites (`[Sparkman and Walton, 2020]`) instead of `[cite_key]` | `prompts/paper_draft_rules.md` requires `[cite_key]` form; export resolves keys against `references.bib` | ✅ Fixed |
| B8 | 14 of 37 cited keys did not exist in the bibliography | Model fabricated plausible author-year keys | Stricter prompt ("only keys verbatim in the supplied list"); 4 keys still fabricated in the last run | ⚠️ Partial |
| B9 | Citations shrank through revision: 71 (draft) → 37 (revised) → 12 (final) | Revision condensed the paper (6,026 words vs 14,436-word draft) and dropped content | Length retry exists but still shortens; not yet resolved | ⚠️ Open |
| B10 | Only 233 literature candidates with off-topic hits | n-gram queries from B4 | Fixed queries → **2,086** candidates, shortlist 15 → 30 | ✅ Fixed |
| B11 | Ablation trivial: `without_activity_gating` = 0.5028 vs baseline 0.5026 (0.0002 pp); metric range 0.0033 | Generated code did not consume the differentiating parameter | Prompts require per-condition seeds + non-saturated metrics; **plus a Stage-10 gate** that runs the experiment and fails when all conditions agree within 0.05 (`_check_condition_differentiation`) | 🔄 Gate added, re-run in progress |
| B12 | Repeated `metric saturation detected` → 6 refine iterations until the wall-clock cap | Consequence of B11 | Follows B11 | 🔄 In progress |
| B13 | `Stage 17: Primary metric is undefined (direction/units/formula unknown)` even though the plan defines it | Detector only looked for the literal phrase in the analysis text, and only for a top-level `primary_metric` key | `_paper_writing.py` suppresses the warning when `exp_plan.yaml` defines a metric with `direction` + `formula` (top-level **or** inside `metrics[]`) | ✅ **Verified fixed** (warning gone in run `rc-20260918-042856`) |
| B14 | Final result was a null result (all methods statistically indistinguishable) | Consequence of B11/B12 | P10 guard now instructs the writer to frame it as a null result rather than claim superiority | ✅ Handled |
| B15 | Quality gate **1/10 "REJECT - FABRICATED RESULTS + CORRUPTED TEXT"**; later 2.8 → 3.0 | Corrupted text (B16) + invalid experiment (B11) + unsupported numbers (fabrication_rate 34.2 %) | Text corruption fixed (see A-class); quality remains below target | ⚠️ Partial |
| B16 | Revision degenerated into repetition — `"the key finding"` ×1,329 → unreadable paper | Model repetition loop in Stage 19 | `_review_publish.py` collapses consecutive duplicate lines and falls back to the unrevised draft when >25 % of lines are duplicated | ✅ Fixed |
| B17 | Repeated forced `REFINE` → rollback to Stage 13 (`Max pivot attempts (2) reached`) | B11/B12 metrics do not move | Follows B11 | 🔄 In progress |
| B18 | Many hours lost to repeated restarts | Alternating A-class and B-class failures | Partially mitigated by the fixes above | ⚠️ Open |
| B19 | Fabricated numbers survived sanitization even though tables had been cleaned | The prose pass was gated on `numbers_replaced` (the **table** counter), so any run that sanitized a table skipped prose entirely — `prose_numbers_replaced` stayed `0` | Gate the prose pass on `prose_numbers_replaced` instead | ✅ Fixed (`a20079a`) |
| B20 | Sanitization never ran on a "successful" but degenerate experiment | `fabrication_suspected = (experiment failed AND no real data)`. A degenerate *success* is neither, so the flag stayed `False` and the guard was skipped | Sanitize whenever `has_real_data` is true | ✅ Fixed (`235a3bb`) |
| B21 | `p < 0.001`, `p = 0.03` and `d = 0.21` survived while `34.2%` was blanked | Two defects: the keep-check accepted a **1-decimal** match, so every value below 0.05 equalled a real `0.0` metric; and p-values were only checked as bare numbers, so a real `0.001` metric licensed the *claim* `p < 0.001` | Compare numbers at the precision the author wrote; blank the number of `p`/`d`/`r` claims outright | ✅ Fixed (`6f644fc`) |
| B22 | The quality gate judged the **pre-sanitization** draft | Stage 20 runs before Stage 22, so the judge always saw the fabricated numbers — the gate could never pass however good the export-time sanitizer was | Extract the sanitizer into `_sanitize_prose_numbers()` and run it at the start of Stage 20 | ✅ Fixed (`fd33c83`) |
| B23 | Integer percentages (`62%`, `8-12%`) remain unverified in the Abstract | The sanitizer only matches decimal tokens (`\b\d+\.\d{1,6}\b`) | Not fixed — extend to integer percentages | ⚠️ Open |

---

## Detail by area

### B-1. Topic vs. ML-centric pipeline
- The topic is behavioural/environmental science, but the pipeline assumes ML (datasets, GPU hints).
- **B1** was fixed by declaring the real disciplines; **B2** by disabling the BenchmarkAgent.
- **B3**: the "alignment" string in `experiment_spec.md` is not validated — treat it as informational only.

### B-2. Structured-output non-compliance (silent fallbacks)
- The most damaging class: the model returns plausible prose with malformed structured payloads, and the
  pipeline **falls back silently** (`model_queries_extracted: false`, n-gram queries), so quality drops
  without any error.
- Fixes: tolerant parsers (`strategies` key, direct-YAML fallback), strict-format prompt overrides for
  `search_strategy`, `code_generation`, `research_decision`.
- Recommendation: whenever a fallback fires, emit an explicit warning (the n-gram fallback currently logs
  nothing actionable).

### B-3. Literature and citations
- Two independent defects: the model used **author-year** citations (B7), then **fabricated keys** (B8).
- The export step now resolves keys missing from `references.bib` against arXiv/Semantic Scholar and drops
  the unresolvable ones (`resolved_citations.json` / `invalid_citations.json`).
- Best measured result so far: **12 verified citations, integrity score 1.0** (was 2).
- B9 (revision shortening) still loses citations between draft and final.

### B-4. Experiment quality (current focus)
- The generated simulation saturates (mean 0.9989) and hardcodes one seed, so every condition lands on the
  same metric → the ablation is a no-op and Stage 15 keeps requesting REFINE.
- Applied so far:
  - `prompts/experiment_design_rules.md`: conditions must enter a **non-saturated** regime and state where
    the differentiating parameter is consumed.
  - `prompts/code_generation_rules.md`: **per-condition RNG seed**, no saturation, explicit
    `max-min > 0.05` check, parameters wired into the update rule.
  - `prompts/code_generation_rules.md` + Beast Mode mega-prompt: `main.py` MUST define `def main()` and end
    with `if __name__ == "__main__": main()` — a library-only `main.py` previously made Stage 12 exit with
    zero output (0.0 s) and fail.
  - `_paper_writing.py` (B13): metric-defined-in-plan suppression.
- **Current state**: Stage 10 is being re-run with all of the above to verify that
  (a) `main.py` is runnable, (b) Stage 12 produces real metrics, (c) the ablation is no longer trivial.

### B-5. Final quality and process
- **B16** (repetition) was the single worst artefact defect and is fixed by the repetition guard.
- **B15/B9**: quality gate and PDF review still score low (3–4/10) and the paper exceeds the 10-page limit
  (16–20 pages in practice).
- **B18**: the long feedback loop is inherent to running a 23-stage pipeline on a slow/free model; each fix
  requires a partial re-run.

### B-6. Anti-fabrication sanitization chain (B19–B23)

The pipeline's mechanical guard removes numbers the experiment never produced. Four independent defects
had made it silently useless; all four are fixed and were verified together.

```
Stage 20 (QUALITY_GATE)              Stage 22 (EXPORT_PUBLISH)
  _collect_real_metric_values()        _sanitize_prose_numbers()
  _sanitize_prose_numbers()   ───►     (same shared helper, re-run on any
  ↓ writes paper_revised.md            rewrite between gate and export)
  judge scores the GROUNDED text
```

- **B19** — the prose pass was gated on `numbers_replaced`, which counts **table** replacements, so
  `0 != 0` was false and prose was never cleaned (`prose_numbers_replaced` stayed `0` in
  `sanitization_report.json`). Gate on the prose counter.
- **B20** — `fabrication_suspected` is true only when the experiment *failed* **and** had no data.
  The observed run was a degenerate *success* (`adoption_rate: 0.0`), so the flag was `False` and the
  guard never ran. Sanitize whenever real values are known.
- **B21** — `_sanitize_number` kept a number when its **1-decimal** rounding matched a real value.
  Every value below 0.05 rounds to `0.0`, and real `0.0` metrics exist, so `p < 0.001`, `p = 0.03`
  and `d = 0.21` were all treated as verified. Compare at the written precision, and blank `p`/`d`/`r`
  claim numbers regardless of metric coincidences.
- **B22** — the judge ran before the sanitizer, so it always scored fabricated text. The gate now
  sanitizes first.
- Coverage: the section allowlist is Abstract / Introduction / Results / Experiments / Evaluation /
  Ablation / Discussion / Conclusion / Limitations. **Method/Setup is deliberately excluded** so
  hyperparameters survive.
- **B23** — only decimal tokens are matched, so integer percentages (`62%`, `8-12%`) are unaffected.
  This is the remaining gap.

Measured effect on the shared run: `34.2%`, `Cohen's d = 0.67`, `p < 0.001`, `p = 0.03`, `d = 0.21`
all went from a combined 37 occurrences to **0**; Stage 20 blanked 174 numbers, Stage 22 another 162.
The quality gate rose 2.1 → **2.8**, and its objection changed from *"critical data fabrication
detected"* to *"extensive placeholder values (`--`) … a template rather than a completed manuscript"*.

---

## Evidence — best completed run so far

Run `rc-20260918-014503` (resumed from Stage 10) finished `14/14 stages, 0 failed`:

| Metric | First attempt | Best result |
|---|---|---|
| Verified citations | 2 | **21** (integrity 1.0) |
| Text corruption (`the key finding`) | 1,329 | **0** |
| `degraded` | true | false (last two runs differ) |
| Literature candidates | 233 | 2,086 |
| PDF pages | 13 | 16 |
| Quality-gate score | 1.0 | 3.0 (verdict FAIL) |
| Ablation | trivial | gate added; re-run in progress |
| `Primary metric is undefined` warning | present | **gone** (B13 fixed) |

Latest resumed run `rc-20260919-130241-5a0aab` (from Stage 20, 2026-09-19):

| Metric | Earlier runs | Latest |
|---|---|---|
| Invented decimals (`34.2%`, `d = 0.67`, `p < 0.001`) | 37 occurrences | **0** |
| Numbers blanked | 0 (guard never ran) | **174** (Stage 20) + **162** (Stage 22) |
| Quality gate | 1.0 → 2.1 (verdict "fabrication detected") | **2.8** (verdict: "template — placeholders") |
| Verified citations | 2 → 21 | 19 (18 verified, score 0.947) |
| PDF pages | 13 → 16 | 22 |
| Experiment | saturated (all conditions equal) | degenerate (`adoption_rate: 0.0`, 1/18 conditions ran) |

---

## Fixes committed

| Commit | Change |
|---|---|
| `b6dba07` | Beast Mode `--dir`; per-model fallback; `force_numpy_only`; literature parser tolerance; ACP timeout 30 → 120 s; revision repetition guard; strict prompt rules; docs |
| `375b46d` | `_read_prior_artifact` skips empty files (a stale 0-byte `references.bib` had deleted every citation) |
| `0b4a2a8` | Condition-differentiation requirements; trust plan-defined metrics |
| `ec9df7c` | Honour `metrics[]` when deciding whether the primary metric is defined |
| `a9f7f63` | Require a runnable `main.py` entry point (Beast Mode prompt + code-generation rules) |
| `81c43a6` | Stage-10 gate: run the generated experiment and fail when all conditions report the same metric (no-op ablation) |
| `dc81844` | This document |
| `717f752` | Keep the unrevised draft when the revision is still < 80 % of the draft length |
| `c8a3cb1` | Forbid fabricated statistics in prompts; scope evolution lessons to the current `run_id` |
| `235a3bb` | B20: sanitize invented result numbers even when the experiment is marked "successful" |
| `a20079a` | B19: run the prose pass even when tables were sanitized (gate on `prose_numbers_replaced`) |
| `2cf9bc5` | Prose sanitization extended to the narrative sections (Abstract/Intro/Discussion/Conclusion) |
| `6f644fc` | B21: match numbers at written precision; blank ungrounded `p`/`d`/`r` claims |
| `fd33c83` | B22: ground the paper before the quality gate judges it (shared `_sanitize_prose_numbers`) |

See [`docs/HANDOVER.md`](HANDOVER.md) for run commands, environment, and the current blocker list.

---

## Open items

1. **B11/B17 (top priority)** — the experiment is still degenerate: only 1 of the 18 claimed conditions
   ran and `adoption_rate: 0.0`. The anti-fabrication guard now blanks every ungrounded number, so the
   paper is rejected as a *template* rather than as a *fabrication*: the remaining work is upstream, in
   Stage 10–12, not in sanitization.
2. **B23** — blank integer percentages (`62%`, `8-12%`) in the narrative sections; only decimals are
   matched today.
3. **B9** — stop the revision from shortening the paper (enforce a minimum word count more aggressively or
   merge rather than regenerate).
4. **B8** — eliminate the remaining fabricated citation keys (4 in the last run).
5. **B15/B3** — quality gate at 2.8 vs the 3.0 threshold; the "alignment" check is cosmetic.
6. **B5-page limit** — 22-page paper vs. the 10-page conference limit; also 7 defined-but-unreferenced figures.
