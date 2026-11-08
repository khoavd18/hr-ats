# Evaluation Report Template

```
Model: <name>  weights: <file + hash>  code: <commit>  framework: <name version>
Data: test <dataset version, split file>  images <n>  instances <n>
Evaluator: <tool + version>  image size <px>  IoU <thresholds>  NMS IoU <x>  max det <n>

Evaluation contract
- Primary metric: <e.g. mAP50-95> (reason: <decision it supports>)
- Operating point rule: <e.g. max F1 on val> -> threshold <t>
- Acceptance criteria: <values or UNKNOWN>
- Test set used for tuning: <no / yes -> this is a validation score>

Results                      value     95% CI          label
mAP50                        ...       [.., ..]        VERIFIED
mAP50-95                     ...
P / R / F1 @ t               ...

Per class   images  instances  AP50  AP50-95  P@t  R@t
<class>     ...

Confusion matrix (incl. background): <table or file>
Top errors: <type, count, example image ids>
Slices: <slice, n, metric, CI>
Comparison with <baseline>: difference <x> [CI]  -> <demonstrated / not demonstrated>

Limitations: <data coverage, unknown thresholds, untested conditions>
Assumptions: <list>
Recommendation: <ship / iterate on X / collect data Y>
```

## Model card (short form)

- Intended use and out-of-scope use.
- Training data: source, period, version, known gaps.
- Evaluation data and results (link the report).
- Known failure modes and slices.
- Deployment format, runtime, input preprocessing.
- Owner, date, how to reproduce.
