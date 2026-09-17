CRITICAL — the `search_plan_yaml` value MUST parse with PyYAML (`yaml.safe_load`). Follow these rules EXACTLY:

- Use 2-space indentation consistently; never use tabs.
- ALWAYS put a space after every colon: write `key: value`, NEVER `key:value`.
- Under `search_strategies:`, indent each list item by 2 spaces, and align every sibling key under `- name:` by exactly 2 more spaces, e.g.:

    search_strategies:
      - name: core_topic
        queries:
          - generosity contagion nature positive behavior
          - prosocial spillover environmental behavior
      - name: methods
        queries:
          - agent based model behavioral contagion

- At least 3 strategies, each with 3-5 queries; at least 8 total queries.
- Each query MUST be a plain string of 3-6 words (not a dict).
- Return ONLY the YAML document itself. Do NOT wrap it in a JSON object and do NOT use markdown code fences.
  (If you do use JSON, the only accepted shape is {"search_plan_yaml": "<yaml string>", "sources": [...]}.)
- Keep the reply compact: no long prose before or after the YAML.
