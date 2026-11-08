# ML Quality Contract

Shared by the machine learning skills (`cv-dataset-engineer`, `cv-model-training`, `ml-model-evaluation`, `cv-inference-deployment`, `ml-tabular-modeling`, `time-series-forecasting`, `llm-app-engineer`, `rag-pipeline-engineer`, `llm-evaluation`, `nlp-model-finetuning`). It is the ML counterpart of the analytical quality contract used by the Data Analyst skills. Apply the subset that matches the risk tier.

## 1. Checks

| Dimension | Question | Typical evidence |
|---|---|---|
| Problem definition | What decision does the model support, and what error is worse (missed object vs false alarm)? | Written task statement and acceptance criteria (or `UNKNOWN`) |
| Data integrity | Are labels valid, classes consistent and splits leak-free? | Dataset audit report, split files, duplicate and group checks |
| Reproducibility | Can the run be repeated? | Code commit, dataset version, config file, seed, framework and driver versions, weights hash |
| Evaluation integrity | Is the score measured on untouched data with a stated definition? | Evaluation contract, evaluator name and version, test used once |
| Uncertainty | How much would the score move with other data? | Bootstrap interval; per-class support counts |
| Robustness | Where does it fail? | Per-class and slice metrics, error analysis |
| Deployment parity | Does the deployed artifact behave like the evaluated one? | Output comparison and metric re-run after export |
| Responsible use | Could images or predictions affect people or privacy? | Data permission, PII handling, intended-use statement |
| Cost | Is the compute justified? | Run time, GPU hours, budget agreed before long runs |

## 2. Risk tiers

| Tier | Example | Minimum |
|---|---|---|
| Low | Notebook exploration, learning exercise | Dataset version and metric definition stated |
| Medium | Internal demo or proof of concept | Low + dataset audit + leakage check + reproducibility record + per-class metrics on an untouched test split |
| High | Production, safety, money or decisions about people | Medium + bootstrap intervals + slice analysis + deployment parity check + model card + reviewer sign-off |

## 3. Default ML workflow

1. Define the task, users and acceptance criteria.
2. Audit and version the data; build leak-free splits.
3. Agree the evaluation contract.
4. Establish a simple pretrained baseline.
5. Iterate on data and training, one change at a time, on validation only.
6. Evaluate once on test; analyze errors and slices.
7. Export and optimize; verify parity.
8. Document: model card, limitations, how to reproduce.

For a quick question, steps 1, 3 and 6 in a few lines are enough.

## 4. Evidence vocabulary

- **VERIFIED**: produced by a run, evaluator or test whose output is shown.
- **INFERRED**: follows from evidence but not directly measured.
- **ASSUMED**: taken as given; listed in assumptions.
- **UNKNOWN**: not confirmed (thresholds, class boundaries, deployment hardware). Do not guess.
- **NOT TESTED**: a check that exists but was not run (no GPU, no data access, out of budget).

A training log that "looks good", a successful export or a passing lint is not evidence of accuracy.

## 5. Coordination

| Task | Chain |
|---|---|
| New CV model | cv-dataset-engineer → ml-model-evaluation (contract) → cv-model-training → ml-model-evaluation |
| "Accuracy dropped" | ml-model-evaluation (error analysis) → cv-dataset-engineer or cv-model-training |
| Ship to device or API | cv-inference-deployment → ml-model-evaluation (parity) |
| New tabular model | data-profiling-engineer → ml-tabular-modeling (framing, leakage, CV) → ml-model-evaluation |
| Forecast | data-profiling-engineer → time-series-forecasting (contract, backtest) → ml-model-evaluation when models are compared formally |
| LLM feature | llm-app-engineer (+ rag-pipeline-engineer) → llm-evaluation (gate) → release |
| Fine-tuned language model | nlp-model-finetuning → ml-model-evaluation (classifiers) or llm-evaluation (generative) |
| "Did the change cause it?" | statistics-experimentation (not a predictive model) |

## 6. Security and compute baseline

- No API keys, tokens or cloud credentials in code, configs, notebooks or logs.
- Do not upload private images or labels to external services (hosted labelling, model APIs) without permission.
- Ask before starting long or paid jobs (multi-hour GPU runs, cloud instances) and before deleting checkpoints or datasets.
- Keep raw data read-only; write derived datasets and runs to new, versioned locations.
