# Eval Design

## Eval case format

```yaml
- id: refund-007
  input: {question: "Can I return a sale item after 20 days?", user_tier: "standard"}
  tags: [policy, edge-case]
  checks:
    - type: schema            # output parses and matches the schema
    - type: contains
      value: "30 days"
    - type: not_contains
      value: "14 days"
    - type: cites_source
      source: "policy-2025-03"
    - type: rubric
      rubric: "Answers yes/no clearly, cites the policy section, no invented conditions (score 1-5)"
```

## Metric menu

| Output | Deterministic | Model- or human-graded |
|---|---|---|
| Extraction / classification | Exact match, field-level precision/recall, schema validity | — |
| Short answers | Exact match, token F1, contains/excludes | Correctness rubric |
| RAG answers | Citation present, cited id exists | Groundedness per claim, completeness |
| Summaries | Length, required entities present | Faithfulness, coverage rubric |
| Agents | Task success, steps, tool errors, forbidden actions | Trajectory review |
| Safety | Refusal on disallowed inputs, injection resistance | Harm rubric |

## LLM-as-judge protocol

1. Write the rubric with anchored score descriptions (what a 1, 3 and 5 look like).
2. Ask for the reasoning before the score; parse the score strictly.
3. Randomize order in pairwise comparisons; check for length and position bias.
4. Label 50–100 cases by humans; report judge–human agreement (accuracy or Cohen's kappa). Low agreement means the judge is not a valid metric yet.

## Comparing two variants

- Same cases, same number of runs per case, same temperature.
- Report per-case win/tie/loss and the mean difference with a bootstrap interval over cases.
- Inspect every new failure before shipping; averages hide regressions on critical cases.

## CI gate sketch

```
on change to prompts/ or model config:
  run eval set (N runs per case) -> results.json
  fail if: schema validity < baseline, any critical-tag case regresses, or mean score drops beyond tolerance (UNKNOWN until set)
  attach: diff of failing cases, cost and latency deltas
```
