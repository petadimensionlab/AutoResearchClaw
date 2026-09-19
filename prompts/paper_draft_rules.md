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
