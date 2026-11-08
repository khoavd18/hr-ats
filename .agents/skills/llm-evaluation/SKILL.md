---
name: llm-evaluation
description: Evaluate generative AI and LLM outputs (chatbots, RAG answers, summaries, extraction, agents) and catch regressions when prompts, models or retrieval change. Use when building golden evaluation sets from real traffic; scoring with exact match, F1, rubric grading, LLM-as-judge or human review; checking faithfulness and groundedness of answers against sources; measuring hallucination, refusal and safety behaviour; comparing prompts or models across repeated runs with variance; tracking cost and latency; or setting up an evaluation gate in CI. Not for classical model metrics such as mAP, ROC-AUC or RMSE (use ml-model-evaluation) or for building the retrieval index (use rag-pipeline-engineer).
---

# LLM Evaluation

Replaces "it looked good in a few tries" with a repeatable measurement that can block a bad prompt or model change.

## Inputs

- The task, the output contract, examples of good and bad outputs, and who is harmed by which failure.
- Acceptance criteria per metric: `UNKNOWN` until the owner states them; the library never invents pass marks.

## Procedure

1. **Detect the stack**: existing eval scripts or frameworks (promptfoo, Ragas, DeepEval, OpenAI evals, custom pytest), logging/tracing of real traffic, the model and prompt versions under test.
2. **Build the eval set**: real or realistic inputs covering common cases, hard cases, adversarial inputs (injection, out-of-scope) and known past failures; fixed ids; kept out of prompt few-shot examples. See [eval-design.md](references/eval-design.md).
3. **Choose metrics per output type**: deterministic checks first (schema valid, exact match, contains/excludes, citation exists), then rubric scores for open text, then human review for what matters most.
4. **LLM-as-judge with care**: explicit rubric, a different or stronger model where possible, position/length bias controls, and agreement measured against human labels on a sample before trusting it.
5. **Groundedness** for RAG: each claim supported by a cited passage; separate retrieval failures from generation failures.
6. **Run repeatedly**: outputs are stochastic; run each case several times (or fix temperature/seed where supported) and report mean and spread.
7. **Compare variants** on the identical set: per-case wins/losses, not only averages; paired comparison for significance when the set is small.
8. **Cost and latency**: tokens, cost and p95 latency per variant next to quality.
9. **Gate**: a CI job that fails on regressions against the current baseline; store results with prompt and model versions.

## Rules

- An eval set used to tune prompts becomes a training set; keep a held-out portion.
- A judge model's score is a measurement with error; report its agreement with humans.
- Never claim "no hallucinations"; report a measured rate on a stated set.
- Eval data may contain personal or confidential text; store and share it like production data.
- Size the evaluation to the risk tier in the [ML quality contract](../ml-model-evaluation/references/ml-quality-contract.md).

## Outputs

The eval set (versioned), metric definitions and judge rubrics, a results table per variant with spread, cost and latency, a list of regressions with example ids, and a CI gate configuration.

## Hand-offs

Prompt or tool fixes → **llm-app-engineer**. Retrieval fixes → **rag-pipeline-engineer**. Fine-tuning data from failures → **nlp-model-finetuning**. Statistical comparison details → **statistics-experimentation**.
