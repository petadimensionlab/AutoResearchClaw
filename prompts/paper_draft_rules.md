CITATION REQUIREMENTS — the pipeline verifies every inline citation against the supplied bibliography.

- Cite ONLY with the exact `cite_key` values provided in the literature / knowledge base, in square brackets,
  e.g. `[vanvalkengoed2022]`. Do NOT use author-year citations such as `[Sparkman and Walton, 2020]` or `[2020]`.
- Use ONLY keys that appear VERBATIM in the provided literature list. Do NOT construct a key from an author
  name + year (e.g. `[centola2010spread]` is invalid unless that exact string is in the list). Citations whose
  key is not in the list are deleted by the pipeline and count as fabrication risk.
- Use AT LEAST 12 distinct cite_keys across the Introduction and Related Work (use all provided keys if fewer
  than 12 are available). A paper with only one or two citations is unacceptable.
- Every factual claim about prior work MUST carry an inline citation.
- End the paper with a `## References` section listing every cited key.
- NEVER invent a cite_key, author, title, or year. If no supplied key supports a claim, drop the claim instead of
  fabricating a reference.

NUMERICAL INTEGRITY (mandatory — the quality gate rejects fabricated numbers):
- Use ONLY numeric values that appear VERBATIM in the supplied experiment data / metrics.
- Do NOT invent or estimate: percentage improvements, effect sizes (Cohen's d, η², r), p-values,
  confidence intervals, correlations, or per-condition means/stds that are not in the supplied data.
- If a statistic is not available, write `not measured` / `not computed` instead of a number.
- Do NOT describe a result as an improvement (or claim superiority of a method) unless the supplied
  metrics actually show one. A null result MUST be reported as a null result.
- Tables and figure captions MUST reproduce supplied values exactly; never fill cells with plausible
  placeholders or aspirational numbers.

LENGTH & DEPTH (mandatory — write a full manuscript, not a summary):
- Target 5,000–6,500 words of body text (excluding references, tables, captions).
- Section budgets: Abstract 180–250; Introduction 800–1,000; Related Work 800–1,000;
  Method 1,000–1,500; Experiments 800–1,200; Results 800–1,200; Discussion 500–800;
  Limitations 250–400; Conclusion 200–350.
- Develop every claim (claim + mechanism + evidence); describe the method reproducibly;
  report per-condition numbers in tables; discuss confounds and alternative explanations.
- Expand with substance (definitions, rationale, examples, comparisons), never with repetition.
- Output ONLY the manuscript: no meta-commentary, planning notes, or self-corrections.

SCIENTIFIC RIGOR CHECKLIST (mandatory — distilled from an independent methodological review):
- Define every construct and metric operationally (name, computation, unit, range) before using it.
  Do NOT introduce metrics/indices/acronyms absent from the supplied evidence; if one is needed,
  define it AND label it as a novel, unvalidated proxy.
- Do NOT attach mechanistic labels (moral licensing, virtue signaling, extractive loops, selection
  bias, ...) unless the evidence measures the mechanism; otherwise list it as an open hypothesis.
- Separate association from causation: use causal language only with a stated identification
  strategy; otherwise downgrade. Do NOT treat observational differences as evidence of a mechanism.
- Every quantitative claim must trace to a value in the supplied evidence; distinguish "not measured"
  from "measured as zero". Do NOT report inference (significance, p-values, CIs) when the sample is
  degenerate (n=1, zero variance); call such data an invalid/inconclusive pilot, never a "null result".
- Falsification criteria must be concrete (comparison, direction, decision rule/equivalence bounds),
  never merely "no significant difference".
- State provenance/independence of any review; give a claim-evidence trace for major claims; discuss
  threats to validity and alternative explanations; cover consent/power where people are involved.
