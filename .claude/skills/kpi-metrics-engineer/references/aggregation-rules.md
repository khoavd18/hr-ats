# KPI Aggregation Rules

## Additivity

| Measure kind | Across entities | Across time | Store as |
|---|---|---|---|
| Count, amount (flow) | Sum | Sum | Value |
| Balance, headcount (stock) | Sum | **Not** sum. Use the period-end or average | Snapshot |
| Ratio / % | Recompute from components | Recompute from components | Numerator + denominator |
| Average | Recompute from sum and count | Recompute | Sum + count |
| Distinct count | Recompute | Recompute | Keys |
| Score with cap/threshold | Per contract (usually aggregate the underlying values, then score) | Per contract | Components + parameters |

## Ratio of sums vs mean of ratios

```
Employee A: 90 / 100 = 90%
Employee B: 10 /  50 = 20%
Ratio of sums: 100 / 150 = 66.7%   ← weights by target size
Mean of ratios: (90% + 20%) / 2 = 55%   ← each employee counts equally
```

Both are legitimate, and they answer different questions. The contract must name one. If it does not, the rule is UNKNOWN, so ask.

## Weighted scores

```
score = Σ (weight_k × completion_k) / Σ weight_k   (over KPIs k present)
```

Decide, with the owner:

- Do missing KPIs re-normalize the weights, or count as 0?
- Is completion capped before weighting?
- Do weights differ by role or period? Where are they stored and versioned?
- Is the team score computed from the team's components, or by averaging member scores?

## Thresholds and rating bands

- Boundaries need inclusive/exclusive notation: `[0.9, 1.0)` = meets.
- Apply bands to the *unrounded* value, and state this.
- Test exactly at every boundary.

## Hierarchies

- Use the hierarchy as of the reporting period, not today's.
- An employee who moved mid-period: allocate by days, or assign by period-end rule. This is a contract decision.
- Count unmapped records, and report them under an explicit "Unassigned" member, never drop them.
- Manager KPIs: do they include only direct reports, or the whole subtree? Does the manager's own row count?

## Missing vs zero

| Situation | Typical representation |
|---|---|
| Entity not expected to report (not applicable) | Excluded from the population |
| Expected but no data received | BLANK / NULL, flagged as missing |
| Reported zero | 0 |
| Zero target | Completion BLANK (undefined), never ∞ |

## Period comparison

- Compare like with like: partial current month vs the same days of the prior period, or flag the comparison as partial.
- Definition changes break comparability, so annotate the period where the version changed.
