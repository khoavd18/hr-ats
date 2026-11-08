# Metric Contract Template

Copy one block per KPI into a project file, for example `docs/metrics/<kpi>.md` or a YAML catalog. Fields without an authoritative source stay `UNKNOWN`.

```yaml
metric: <machine_name>
version: 1
status: draft            # draft | approved | deprecated
display_name: <name shown in reports>
description: <one sentence in business language>
owner: UNKNOWN           # accountable business role
source_of_definition: UNKNOWN   # document / decision record + date
source_system: <system>
source_tables: [<table>, ...]
formula: "<numerator> / <denominator>"
numerator: {field: <col>, filters: [...], aggregation: sum}
denominator: {field: <col>, filters: [...], aggregation: sum}
unit: percent            # currency(VND/USD) | count | percent | score | ratio
display_precision: 1
grain: [employee_id, month]
aggregation:
  across_entities: ratio_of_sums       # ratio_of_sums | weighted_avg(<weight>) | sum_of_row_values | simple_avg | not_aggregatable
  across_time: ratio_of_sums           # or latest_snapshot | sum | avg_of_periods
filters: [<population rule>]
reporting_period: {calendar: monthly, cutoff: "<e.g., data as of day 5 of next month>", timezone: "<tz>"}
missing_rules:
  no_row: blank                        # blank | zero | exclude
  null_numerator: UNKNOWN
  zero_denominator: blank              # never Inf; blank or n/a
  not_applicable: exclude
target_rules: UNKNOWN                   # where targets come from, their grain
score_rules: UNKNOWN                    # caps, weights, rating bands, all from owner
validation_cases:
  - {name: normal, input: {...}, expected: ...}
  - {name: zero_target, input: {...}, expected: blank}
  - {name: missing_period, input: {...}, expected: blank}
known_limitations: []
change_log:
  - {version: 1, date: <YYYY-MM-DD>, change: initial draft, approved_by: UNKNOWN}
```

## Illustrative example (synthetic, NOT an authoritative definition)

```yaml
metric: target_completion_pct
version: 1
status: draft
description: Share of the period target achieved.
owner: UNKNOWN
source_of_definition: UNKNOWN
formula: "SUM(achieved) / SUM(target)"
unit: percent
grain: [employee_id, month, kpi_code]
aggregation: {across_entities: ratio_of_sums, across_time: ratio_of_sums}
missing_rules: {no_row: blank, zero_denominator: blank}
score_rules: UNKNOWN          # e.g., cap at 120%? confirm with owner
validation_cases:
  - name: two_employees
    input: [{achieved: 90, target: 100}, {achieved: 10, target: 50}]
    expected: 0.6667          # 100/150; NOT mean(0.9, 0.2) = 0.55
  - name: zero_target
    input: [{achieved: 5, target: 0}]
    expected: blank
```

## Validation-case checklist

- [ ] Normal case at row grain
- [ ] Aggregated case where ratio-of-sums ≠ mean-of-ratios
- [ ] Zero denominator
- [ ] Missing row vs reported zero
- [ ] Negative values (returns or corrections), if possible in source
- [ ] Partial period
- [ ] Entity moved between teams mid-period
- [ ] Cap or threshold boundaries (exactly at the band edge), only if bands are defined
