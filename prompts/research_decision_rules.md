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
