The experiment MUST be a self-contained numerical simulation that directly operationalizes the research topic.

- `datasets:` MUST be empty (or list only synthetic data generated in-code). Do NOT reference CIFAR-10, MNIST,
  ImageNet, HuggingFace datasets, `torchvision`, `datasets.load_dataset`, or any download / network access.
- numpy + stdlib ONLY: no torch, tensorflow, jax, sklearn, pandas, scipy, matplotlib; must run on CPU without a GPU.
- Design an agent-based or numerical simulation whose conditions operationalize the topic. For a behavioral /
  social topic this means: simulate a population/network of agents, model how the behaviour spreads, and compare
  conditions (e.g. with vs. without the "infectious" trigger, different network structures or exposure levels).
- Name concrete, meaningful conditions and baselines. Do NOT emit placeholders such as `What_baseline_1`,
  `What_proposed`, or `simplified_version`.
- The primary metric MUST be produced by the simulation itself (adoption rate, cascade size, treated-vs-control
  uplift, time-to-half-adoption, …), never hardcoded or drawn from a random number generator.
- Keep it small: it must run in seconds-to-minutes on CPU with numpy only.

OUTPUT FORMAT (MANDATORY — the pipeline parses this with PyYAML):
- Return ONE valid YAML document that `yaml.safe_load` accepts. Do NOT wrap it in a ```yaml code fence.
- Write `key: value` with a space after every colon (never `key:value`); use 2-space indentation; never tabs.
- Quote any value that contains `:` `[` `]` `(` `)` or a leading `-`.
- Do not leave a list item as a bare mapping start with a trailing `[`/`(` fragment.
- Required top-level keys: `topic`, `objectives`, `datasets`, `baselines`, `proposed_methods`,
  `ablations`, `metrics`, `compute_budget`, `risks`.
- `datasets` MUST be an empty list `[]` or synthetic-only entries.

ABLATION INTEGRITY:
- Every condition/ablation MUST differ from its counterpart by exactly one, named parameter, and the
  implementation spec MUST state where that parameter is consumed in the simulation loop.
- Conditions that differ only in a parameter MUST produce different metrics; if the plan cannot specify how
  the parameter changes the mechanism, drop that ablation instead of shipping a no-op condition.

PRIMARY METRIC (mandatory):
- Define the primary metric explicitly and unambiguously: `name`, `direction` (minimize|maximize),
  `units`, and `formula`. Write it into the plan as:
    primary_metric:
      name: <metric name>
      direction: minimize | maximize
      units: <units>
      formula: <how it is computed from the simulation>
- The metric MUST be computable by the simulation (not a placeholder), and must differ between conditions
  that differ by one parameter.

CONDITION DIFFERENTIATION:
- Design the conditions so at least one parameter value drives the primary metric into a NON-saturated regime;
  avoid plans where every condition converges to the same value (0 or 1).
- Specify, per condition, the parameter value that differs and the mechanism step where it is consumed.
