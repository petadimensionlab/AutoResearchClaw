REPORT-GROUNDED NUMERICAL INTEGRITY (mandatory — the quality gate blanks fabricated numbers).

Authoritative source of numbers
- The ONLY numbers you may state are those that appear VERBATIM in the supplied source
  material for this paper: the analysis report body, its metric tables, and the experiment
  summary / metrics provided in this prompt. Treat that material as the single source of truth.
- When the paper is written from an existing analysis report (report-only / docs-first mode),
  "the supplied experiment data" means that report and its metrics tables.

Forbidden
- Do NOT invent, estimate, interpolate, or extrapolate numbers.
- Do NOT derive new statistics from reported values (for example, computing a percentage
  change, a ratio, or an average from two reported numbers).
- Do NOT introduce percentages, relative improvements, effect sizes (Cohen's d, eta^2, r),
  p-values, confidence intervals, correlations, seed counts, runtimes, or per-condition
  means/stds that are not present in the source.
- Do NOT change a reported value's precision (for example, writing 0.25 when the source
  says 0.247).

Required
- Quote reported numbers exactly, with the same precision and sign.
- If a claim needs a number that is absent from the source, write `not reported` or state
  the result qualitatively instead of supplying a number.
- Report null, equivalent, or negative results as such; do NOT claim an improvement or
  superiority unless the reported metrics actually show one.
- Tables and figure captions MUST reproduce the source values exactly; never fill cells
  with plausible placeholders or aspirational numbers.
