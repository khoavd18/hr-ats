# Retrieval Design

## Retrieval test set

```yaml
- id: q001
  question: "What is the refund window for online orders?"     # real user wording when possible
  relevant: ["policy-2025-03#sec-4.2"]                          # chunk or section ids that answer it
  answer_must_contain: ["30 days"]                              # optional, for end-to-end checks
  notes: "Old policy (14 days) must NOT be cited"
```

Metrics: **recall@k** (share of questions with at least one relevant chunk in the top k), **MRR** (mean reciprocal rank of the first relevant chunk), and for answers, citation support rate.

## Chunking

| Content | Approach |
|---|---|
| Structured docs (headings) | Split by section, then by paragraph to the size limit; prepend the section title path |
| Tables | Keep whole, or one row per chunk with headers repeated |
| Slides | One slide per chunk with title |
| Code | Split by function or class |
| Long unstructured text | Fixed size with overlap (for example 10–20%) |

Store `doc_id`, `version`, `section`, `page`, `acl`, `updated_at` with every chunk.

## Retrieval stack

| Stage | Default | Tune when |
|---|---|---|
| Lexical | BM25 | Exact codes, names, part numbers matter |
| Dense | Embedding model suited to the language(s) | Paraphrased questions; check multilingual support for Vietnamese or mixed text |
| Fusion | Reciprocal rank fusion | — |
| Rerank | Cross-encoder on top 20–50 | Relevant chunk is retrieved but ranked low |
| Filters | Metadata + ACL in the query | Always for permissions |

## Failure analysis

| Symptom | Likely cause | Check |
|---|---|---|
| Relevant doc never retrieved | Parsing failure, not indexed, ACL filter too strict | Search the index for the doc id |
| Retrieved but ranked low | Chunk too large or noisy, weak embeddings | Reranker, smaller chunks, hybrid |
| Answer contradicts the source | Generation, not retrieval | Grounding prompt, citation check |
| Outdated answer | Old versions still indexed | Version filter, deletion handling |
