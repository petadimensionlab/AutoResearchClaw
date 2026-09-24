ANALYSIS RIGOR (mandatory — an independent review flagged these as failure modes).

Data validity
- First state whether the data support ANY statistical inference. If the sample is degenerate
  (n = 1, zero variance, a single aggregate, aliased/identical conditions, undefined metrics),
  say the data are INVALID for inference and do NOT report significance, p-values, or confidence
  intervals as if valid.
- Distinguish "not measured" from "measured as zero". Never report an unmeasured quantity as a result.
- Do NOT derive new statistics from reported values (percentage changes, ratios, averages) unless you
  label them as derived and the inputs are valid.

Reporting
- Report the actual metric names and values from the supplied data; every number must trace to the source.
- Report per-condition values and variability, and state the sample size (N vs n — population vs runs/seeds).
- Separate observation from interpretation: state what the numbers show, then what you infer, and flag
  the inference as uncertain when the design or sample does not support it.

Claims
- Use causal/mechanistic language ONLY when the design supports it; otherwise describe associations.
- Do NOT label invalid or degenerate results a "null result"; call them invalid/inconclusive.
- List confounds, threats to validity, and alternative explanations explicitly.

Output hygiene
- Output ONLY the analysis report. No meta-commentary, planning notes, or self-corrections.
