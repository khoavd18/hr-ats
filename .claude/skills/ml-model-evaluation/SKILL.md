---
name: ml-model-evaluation
description: Evaluate, compare and report trained machine learning models for computer vision (detection, classification, segmentation) and tabular classification or regression. Use when computing or interpreting mAP, mAP50, mAP50-95, IoU, precision, recall, F1, ROC-AUC, PR-AUC, log loss, Brier score, calibration, RMSE, MAE, R², accuracy, confusion matrices or per-class metrics; choosing a decision, confidence, IoU or NMS threshold; analyzing false positives and false negatives; checking slices such as lighting, object size, camera, region or customer segment; deciding whether one model really beats another; or drafting an evaluation report or model card. Not for generative LLM outputs (use llm-evaluation), A/B tests of business metrics (use statistics-experimentation) or for changing training settings (use cv-model-training or ml-tabular-modeling).
---

# ML Model Evaluation

Turns "the model got 0.87" into a defensible statement: which metric, on which data, at which operating point, with what uncertainty, and where it fails.

## Inputs

- Task, class list, the model(s) and the evaluation data with its version.
- Acceptance criteria. Target metric values and operating constraints (minimum recall, maximum false alarms per image, latency) are `UNKNOWN` until the owner states them. Never invent a pass threshold.

## Procedure

1. **Evaluation contract** before computing anything: primary metric, IoU threshold(s) for vision, class list, operating point rule, test-set identity and version. Template in [evaluation-report-template.md](references/evaluation-report-template.md).
2. **Test-set integrity**: confirm the test data was not used for training, augmentation, early stopping or threshold tuning, and that leakage was checked (**cv-dataset-engineer**). If it was used, call the result a validation score.
3. **Detect the evaluator** the project uses (framework `val` command, pycocotools, torchmetrics, scikit-learn, a custom script) and state its metric definition. Implementations differ; see [cv-metrics.md](references/cv-metrics.md) for vision and [tabular-metrics.md](references/tabular-metrics.md) for tabular models.
4. **Headline + per-class**: report the primary metric overall and per class, each with its support (images and instances). A good mean can hide a failing class.
5. **Operating point**: mAP and ROC-AUC are threshold-free; a deployed model is not. Choose the confidence threshold on validation data by the stated rule, then report precision, recall and F1 at that threshold on test.
6. **Confusion and errors**: confusion matrix including background (missed objects, false alarms). Sort errors by type: localization, class confusion, duplicate detection, background false positive, missed small or occluded object, label error. For tabular models: the largest residuals or confident wrong predictions, grouped by segment.
7. **Slices**: metrics by object size, lighting, camera, location or any metadata the project has. Small slices get wide intervals; say so.
8. **Uncertainty**: bootstrap over the independent unit (images, not boxes; customers, not rows of one customer) for a confidence interval. Compare two models with a paired bootstrap on the same units.
9. **Report** with evidence labels, and hand any export accuracy check to **cv-inference-deployment**.

## Rules

- Compare models only on the identical test set, image size, preprocessing and evaluator version.
- A difference inside the confidence interval is "no demonstrated difference", not an improvement.
- Report the metric the decision needs, not the best-looking one. State mAP variants exactly (mAP50 vs mAP50-95).
- Never tune on test. Never drop test images after seeing results.
- Apply the [ML quality contract](references/ml-quality-contract.md): risk tiers, reproducibility record, evidence vocabulary.

## Outputs

An evaluation report or model card: contract, data version, headline and per-class metrics with intervals, operating point, confusion matrix, error analysis with example ids, slices, limitations and recommendation, each claim labelled.

## Hand-offs

Data or label fixes → **cv-dataset-engineer**. Training changes → **cv-model-training** or **ml-tabular-modeling**. Forecast backtests → **time-series-forecasting**. Accuracy after export or quantization → **cv-inference-deployment**. Business experiments with users → **statistics-experimentation**.
