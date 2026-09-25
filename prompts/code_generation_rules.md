CRITICAL OUTPUT FORMAT — the pipeline parses your reply with these regexes (first match wins):

    ```(?:python\s+)?filename:(\S+)\s*\n(.*?)```
    ```\s+filename:(\S+)\s*\n(.*?)```
    ```(?:python)?\s*\nfilename:(\S+)\s*\n(.*?)```

Therefore you MUST follow this EXACT format:

- Wrap EVERY file in its own fenced block whose opening line is three backticks immediately followed by the literal word `filename:` and the filename, with NO space, e.g.:

```filename:main.py
import numpy as np

def main():
    ...
```

```filename:utils.py
def helper(x):
    return x + 1
```

- The token `filename:` MUST appear immediately after the opening ``` (e.g. ```filename:main.py). Do NOT write ```:main.py, ``` config.py, or a separate `:main.py` line.
- The filename MUST appear ONLY in the fence line. NEVER put a bare `:main.py`, `main.py`, or `# main.py` header line inside the file body.
- Do NOT prefix the file body with the filename or with any `:` line.
- Close each block with exactly three backticks.
- Include `main.py` as the entry point.
- Every file MUST be complete, runnable Python that parses with `ast.parse` — no syntax errors, no truncation, no `...` placeholders, no `# TODO`.
- If you cannot produce a file, omit it entirely rather than emitting an empty or partial block.

TOPIC ALIGNMENT & RUNTIME (equally critical):
- Implement EXACTLY the method and conditions in the experiment plan. NEVER substitute a generic ML task
  (CIFAR-10, MNIST, DCGAN, VAE, ResNet, …) that is unrelated to the topic.
- numpy + stdlib ONLY: no torch, tensorflow, jax, sklearn, pandas, scipy, matplotlib.
- Do NOT load external datasets or use the network. All data must be generated in-code.
- `main.py` must run to completion on CPU in a few minutes and print metric lines as `name: value`.

ENTRY POINT (mandatory — the harness runs `python main.py` with no arguments):
- `main.py` MUST define `def main():` and end with:
    if __name__ == "__main__":
        main()
- Running `python main.py` MUST execute every condition and every seed and print the metric lines.
- Do NOT put the entry point only in a sibling module; a library-only `main.py` exits with no output and
  makes the whole experiment count as failed.

ABLATION / CONDITION INTEGRITY (mandatory — identical conditions are rejected downstream):
- Every condition/ablation MUST actually consume its differentiating parameter inside the simulation loop.
  Never define a parameter and then ignore it.
- If two conditions differ by exactly one parameter, their metrics MUST differ. Identical metric values
  mean the parameter is not wired in, and the run is invalid.
- Wire the differentiating parameter into the mechanism (e.g. network degree, activity gating on/off,
  environment coupling) instead of hardcoding the same value for every condition.
- `main.py` MUST self-check: after running all conditions, compare the primary metric across every pair of
  conditions that differ by a single parameter, and print an explicit `ABLATION FAILURE: <a> vs <b> identical`
  line (and fail) if any pair matches.
- `main.py` MUST print, on its own line, `metric_definition: <name> | direction=<minimize|maximize> | units=<units> | formula=<formula>`
  using the definition from the experiment plan.
- Before finishing, run the experiment once for each condition and confirm the differentiating parameter
  actually changes at least one metric; if not, fix the wiring (do not ship no-op ablations).

CONDITION DIFFERENTIATION (mandatory — identical conditions are rejected):
- Derive the RNG seed PER CONDITION from the condition name/index (e.g. `seed = base_seed + hash(condition) % 10000`).
  NEVER pass one shared hardcoded seed to every condition.
- Choose parameters so the primary metric is NOT saturated: it is invalid for every condition to converge to
  the same value (typically 0 or 1). Sweep the key parameter if needed to find a regime where outcomes differ.
- After running all conditions, print the primary metric for each and assert
  `max(values) - min(values) > 0.05`; if not, print `ABLATION FAILURE: metrics saturated` and adjust the
  parameters before finishing.
- The differentiating parameter MUST enter the update rule, not merely be stored in a config dict.

EXECUTION CONTRACT (mandatory — the sandbox copies these files FLAT and runs `python main.py`):
- All project files are copied flat into a single working directory and executed as
  `python main.py` from that directory. There is NO package.
- Use FLAT imports only: `from config import Config`, `import methods`, `from data import ...`.
  NEVER use package-style imports such as `from experiment.config import ...` — they raise
  `ModuleNotFoundError` and fail the run.
- `main.py` must run to completion with no manual setup and emit metrics: write `results.json`
  and/or print one `metric: value` line per condition. A run that finishes in under a second
  with no metrics is treated as a crash and fails the pipeline.

NUMERICAL-API COMPATIBILITY (mandatory — NumPy 2.x):
- Use only NumPy 2.x API names. Removed 1.x names MUST NOT be used:
  `np.trapz` (use `np.trapezoid`), `np.float_` (`np.float64`), `np.alltrue` (`np.all`),
  `np.sometrue` (`np.any`), `np.product` (`np.prod`), `np.cumproduct` (`np.cumprod`),
  `np.round_` (`np.round`), `np.NaN` (`np.nan`), `np.Inf` (`np.inf`), `np.string_` (`np.bytes_`),
  `np.unicode_` (`np.str_`).
- If unsure whether an API exists, prefer basic operations (e.g. implement trapezoidal
  integration manually) instead of a possibly-removed helper.
