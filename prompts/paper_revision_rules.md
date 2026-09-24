REPORT-GROUNDED NUMERICAL INTEGRITY (mandatory — the quality gate blanks fabricated numbers).

Authoritative source of numbers
- The ONLY numbers you may state are those that appear VERBATIM in the supplied source
  material: the analysis report, its metric tables, and the experiment summary / metrics
  provided in this prompt. Treat that material as the single source of truth.
- Do NOT invent, estimate, interpolate, or extrapolate numbers, and do NOT derive new
  statistics from reported values (e.g. computing a percentage change from two means).
- Do NOT introduce percentages, effect sizes, p-values, confidence intervals, correlations,
  seed counts, or per-condition means/stds that are not present in the source.
- If a claim needs a number that is absent from the source, write `not reported`.
- Report null/negative results as such; do not claim an improvement unless the metrics show one.

LENGTH & DEPTH REQUIREMENTS (mandatory — write a full manuscript, not a summary).

Target length: 5,000–6,500 words of body text (excluding references, tables, and figure captions).

Section budgets (approximate; stay within ±20%):
- Abstract: 180–250 words
- Introduction: 800–1,000 words
- Related Work: 800–1,000 words
- Method: 1,000–1,500 words
- Experiments / Experimental Setup: 800–1,200 words
- Results: 800–1,200 words
- Discussion: 500–800 words
- Limitations: 250–400 words
- Conclusion: 200–350 words

Depth requirements
- Develop every claim: state the claim, the mechanism, and the supporting evidence.
- Describe the method in enough detail to reproduce it: conditions, parameters, metrics, procedure.
- Report results per condition with concrete numbers and their interpretation, and present tables.
- Discuss threats to validity, confounds, and alternative explanations explicitly.
- Expand by adding substance (definitions, rationale, examples, comparisons), never by repetition.

Output hygiene
- Output ONLY the manuscript. Do NOT include meta-commentary, planning notes, or self-corrections
  (for example: "Let's final", "Need to include", "Ensure not too terse").

SCIENTIFIC RIGOR CHECKLIST (mandatory — distilled from an independent methodological review):
- Define every construct and metric operationally before using it; do NOT use metrics/indices/acronyms
  absent from the supplied evidence unless you define them and label them as unvalidated proxies.
- Do NOT attach mechanistic labels unless the evidence measures the mechanism; list them as hypotheses.
- Separate association from causation; state identification assumptions and threats (endogeneity,
  self-selection, confounding); downgrade causal language when they cannot be ruled out.
- Ensure every number traces to the supplied evidence; distinguish "not measured" from zero; do NOT
  report inference when the sample is degenerate (n=1, zero variance), and never label invalid data a
  "null result".
- Make falsification criteria concrete (comparison, direction, decision rule), not "no difference".
- In REVISION specifically: remove or explicitly qualify any claim the evidence does not support,
  replace invented metrics with defined ones (or delete them), and do not shorten sections that are
  already below their target length — expand them with substance instead.
