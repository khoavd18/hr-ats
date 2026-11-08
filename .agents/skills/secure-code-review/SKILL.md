---
name: secure-code-review
description: Review application and infrastructure code changes for security and quality defects, defensively, in any language the project uses. Use when reviewing a pull request or diff; checking authentication, authorization and session handling; finding injection (SQL, command, template), XSS, SSRF, path traversal and insecure deserialization; spotting hard-coded secrets and unsafe logging of personal data; reviewing file uploads, CORS, CSRF and cryptography usage; checking dependency vulnerabilities and licences; or writing a review report with severity and evidence. Not for writing tests (use software-testing) or for exploit development or attacking systems, which this skill does not do.
---

# Secure Code Review

Finds the defects that matter before they ship, explains each with evidence and a fix, and avoids noise.

## Inputs

- The diff or files, the feature's purpose, who can call it (anonymous, user, admin, internal service) and what data it touches.
- The project's security requirements and threat model: `UNKNOWN` when absent; the review states its assumptions.

## Procedure

1. **Detect the stack**: languages, frameworks and their built-in protections (ORM parameterization, template auto-escaping, CSRF middleware), auth library, dependency manifests and lockfiles.
2. **Understand the change**: entry points, trust boundaries crossed, data sensitivity, privileges used.
3. **Walk the checklist** in [review-checklist.md](references/review-checklist.md): authn/authz, input handling and injection, output encoding, secrets, crypto, files, network calls, logging, error handling, concurrency.
4. **Trace untrusted data** from each entry point to sinks (queries, shell, file paths, HTML, URLs fetched by the server, deserializers).
5. **Check dependencies**: run the ecosystem's audit tool when available (`pip-audit`, `npm audit`, `dotnet list package --vulnerable`, OSV scanners); note licences that conflict with the project.
6. **Report findings** with severity, location, evidence (code excerpt or reasoning), impact and a concrete fix; separate confirmed issues from suspicions.
7. **Verify fixes**: a test that would fail on the vulnerable code where practical (**software-testing**).

## Rules

- Defensive review only: describe the weakness and the fix; do not write working exploits or attack live systems.
- Report secrets found in code by location and type only; never repeat the secret value. Recommend rotation.
- Severity reflects impact and reachability, not the scary name of the bug class.
- Do not approve disabling a security control (TLS verification, auth, CSRF, CORS limits) as a fix.
- Label findings with the evidence vocabulary of the [engineering quality contract](../software-testing/references/engineering-quality-contract.md).

## Outputs

A review report: summary verdict, findings table (severity, file:line, issue, evidence, fix), dependency and secret scan results, assumptions and what was not reviewed.

## Hand-offs

Fix implementation → **backend-api-engineer**, **frontend-engineer** or **database-engineer**. Regression tests → **software-testing**. Pipeline and infrastructure secrets → DevOps skills.
