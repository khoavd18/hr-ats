# Tabular Metrics

## Classification

| Metric | Answers | Watch out |
|---|---|---|
| ROC-AUC | How well scores rank positives above negatives | Optimistic under heavy imbalance; says nothing about calibration |
| PR-AUC (average precision) | Ranking quality for the positive class | Baseline equals the positive rate; report it next to the value |
| Log loss | Quality of predicted probabilities | Punishes confident mistakes; sensitive to label noise |
| Brier score | Mean squared error of probabilities | Compare with the Brier score of predicting the base rate |
| Precision / recall / F1 at threshold t | Behaviour at the operating point | Depends on t; state how t was chosen |
| Accuracy | Share correct | Misleading with imbalance; use balanced accuracy or per-class recall |
| Calibration (reliability curve, ECE) | Do 0.7 predictions happen 70% of the time? | Needs enough data per bin |

## Choosing the threshold

```
On out-of-fold or validation predictions:
  cost(t) = C_FP * FP(t) + C_FN * FN(t)        # costs are UNKNOWN until the owner states them
  or: highest precision with recall >= R, or top-K capacity (e.g. 500 calls per day)
Freeze t, then report precision, recall and the confusion matrix at t on test.
```

## Regression

| Metric | Use | Watch out |
|---|---|---|
| MAE | Typical error in target units | — |
| RMSE | Large errors matter more | Dominated by outliers |
| MAPE | Relative error | Undefined at zero; asymmetric |
| R² | Variance explained vs predicting the mean | Can be high with useless absolute errors; negative is possible on test |
| Residual plots | Bias by range or segment | — |

Always show the baseline's value (mean or median prediction) next to the model's.

## Uncertainty and comparison

- Cross-validation: report mean ± standard deviation across folds, with the folds identical for every model.
- Test set: bootstrap by the independent unit (customer, store), paired between models.
- A difference inside the interval is "no demonstrated difference".

```python
import numpy as np

def paired_bootstrap(units, y, p_a, p_b, metric, n=1000, seed=0):
    """units: array of unit ids per row; resample units, keep all their rows."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(units)
    idx_by_unit = {u: np.flatnonzero(units == u) for u in uniq}
    diffs = []
    for _ in range(n):
        pick = np.concatenate([idx_by_unit[u] for u in rng.choice(uniq, size=len(uniq), replace=True)])
        diffs.append(metric(y[pick], p_b[pick]) - metric(y[pick], p_a[pick]))
    return np.quantile(diffs, [0.025, 0.975])
```

## Slices and fairness

Report metrics per segment the decision cares about (region, product, customer type) with support counts. Small slices get wide intervals. When a protected attribute is involved, report the gap and escalate; do not tune it away silently.
