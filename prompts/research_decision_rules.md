The pipeline parses your reply with a strict rule: it looks for a `## Decision` heading and reads the
next non-empty line as the decision. If that section is missing, the stage pauses.

You MUST start your reply with this exact structure:

## Decision
PROCEED

…where the second line is EXACTLY one of these three words, alone on its line:
- PROCEED — the results are good enough to write up as-is
- PIVOT   — the hypothesis/experiment direction must change
- REFINE  — the same experiment should be re-run with fixes

Rules:
- The `## Decision` heading MUST be the FIRST line of your reply.
- The keyword MUST be the very next non-empty line, alone, in capitals, with no punctuation or bold markers.
- Do NOT put Justification/Evidence before the Decision section.
- Do NOT write the keyword inside a sentence ("criteria for PROCEED" does NOT count as a decision).
- After the Decision section you may add `## Justification`, `## Evidence`, `## Next Actions`.

Example:

## Decision
REFINE

## Justification
The primary metric is undefined and two conditions produce identical outputs.

DECISION RIGOR (mandatory — an independent review flagged these as failure modes):
- Do NOT conflate invalid data with a null result. If the evidence is degenerate (n=1, zero variance,
  aliased variables, missing/undefined metrics), the data are INVALID, not "no effect". Say so explicitly.
- If the evidence is invalid, prefer REFINE or PIVOT (repair the design and metrics) over PROCEED.
  Only PROCEED to write-up when the report's purpose is explicitly a methodological failure analysis,
  and then label the output an invalid/inconclusive pilot rather than substantive findings.
- Do NOT use causal or mechanistic language ("generosity is infectious", "social mechanisms are more
  efficient") when the design cannot support it; downgrade to correlational or descriptive language.
- In `## Justification`, state the concrete decision rule you applied. In `## Evidence`, cite exact
  metric names and values from the supplied data (or state that no valid metrics exist).
