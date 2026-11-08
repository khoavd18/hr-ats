---
name: llm-app-engineer
description: Build and debug applications that call large language models through the project's SDK or framework, such as the OpenAI or Anthropic APIs, LangChain, LlamaIndex, Semantic Kernel, Ollama, vLLM or Hugging Face transformers. Use when writing system prompts and prompt templates; getting structured JSON output; implementing tool use or function calling and agent loops; streaming responses; handling retries, timeouts, rate limits and token budgets; caching; versioning prompts; defending against prompt injection from untrusted content; or keeping API keys and personal data safe. Not for retrieval and vector search (use rag-pipeline-engineer), measuring output quality (use llm-evaluation) or training models (use nlp-model-finetuning).
---

# LLM App Engineer

Turns a prompt that worked once into a feature that keeps working: explicit contracts for inputs and outputs, bounded cost, safe handling of untrusted text.

## Inputs

- The task the model performs, the users, the inputs it sees (including untrusted text: emails, web pages, documents) and the output format consumers need.
- Model and provider constraints: allowed providers, data residency, latency and cost budgets. `UNKNOWN` until the owner states them.

## Procedure

1. **Detect the stack**: SDK or framework and version, model names in config, how keys are loaded, existing prompt files, logging and tracing. Check the provider's current documentation for parameters; APIs change often.
2. **Write the contract**: input fields, output schema (JSON schema or typed object), failure behaviour (refuse, ask, fall back). Prefer the provider's structured-output or tool-schema features over parsing free text.
3. **Prompt**: system prompt with role, task, constraints and output format; few-shot examples drawn from real cases; untrusted content clearly delimited and labelled as data. Patterns in [prompt-and-tooling.md](references/prompt-and-tooling.md).
4. **Tools and agents**: small, well-described tools with validated arguments; a step limit; confirmation before side effects (sending, paying, deleting); tool results treated as untrusted data.
5. **Reliability**: timeouts, retries with backoff on rate limits and transient errors only, idempotency for side effects, streaming where latency matters, graceful degradation.
6. **Cost and context**: count tokens, truncate or summarize long inputs deliberately, cache stable prefixes or responses where the provider supports it, log usage per request.
7. **Safety**: apply [llm-safety-checklist.md](references/llm-safety-checklist.md): injection, data leakage, PII, output validation before use.
8. **Version and evaluate**: prompts and model ids in version control; every change goes through **llm-evaluation** before release.

## Rules

- API keys come from environment variables or a secret store; never from code, notebooks, logs or prompts.
- Text from documents, web pages, emails or tool results never becomes instructions to the model or the app.
- Validate model output (schema, allowed values, length) before acting on it; the model can be wrong confidently.
- Do not send personal or confidential data to a provider unless the project has approved that provider for it.
- Pin model versions in production; "latest" aliases change behaviour silently.
- Evidence and risk tiers follow the [ML quality contract](../ml-model-evaluation/references/ml-quality-contract.md).

## Outputs

Prompt and tool definitions under version control, the calling code with error handling and limits, an output schema, a cost estimate per request, and a safety review.

## Hand-offs

Retrieval over documents → **rag-pipeline-engineer**. Quality measurement and regression tests → **llm-evaluation**. Fine-tuning → **nlp-model-finetuning**.
