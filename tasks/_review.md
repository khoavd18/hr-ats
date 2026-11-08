# Workflow: review a task

The user names one task id (e.g. "Review T05"). Below, `TASK` means that id.

You are an independent senior reviewer. Find real problems before merge; do not praise or rewrite.
Do NOT modify source code, tests, or specs. The ONLY file you may write is the report
`tasks/reviews/TASK.md`. You may run read-only commands (tests, lint, typecheck, git).

## Step 0 — Context
1. Read AGENTS.md, tasks/README.md, tasks/TASK-*.md, and every spec listed on its "Spec" line.
   Specs are written in Vietnamese; read them carefully.
2. Find the changes: run `git status` and `git diff main` (this includes both committed and
   uncommitted work on the current branch; if the default branch is `master`, use that).
   Read the full diff, and surrounding code where needed.
3. Read the implementer's entry for TASK in tasks/PROGRESS.md, but verify every claim.

## Step 1 — Verify, don't assume
- Run the test, lint, typecheck, and migration commands from docs/specs/08-testing-quality.md
  for the affected parts. Record exact commands and results.
- For EACH acceptance criterion: met / partial / not met / not proven, with the test or code that
  proves it. A criterion without a test that would fail if the behavior broke is "not proven".

## Step 2 — Checklist
1. Spec conformance: data model, API contract, error format, stage rules, KPI formulas match
   docs/specs/. Flag silent deviations.
2. Correctness: logic errors; edge cases (empty input, duplicates, Asia/Ho_Chi_Minh day
   boundaries, Vietnamese diacritics / Unicode NFC, large files); error handling; idempotent
   background jobs; race conditions.
3. Scope: changes outside the task, new dependencies or services not in the spec, unrelated
   refactors.
4. Privacy and security (highest priority): personal data (CV text, emails, phones, names) in logs,
   fixtures, tests, or error messages; raw PII sent to the LLM or embedder instead of
   redacted/anonymized text; missing permission checks per docs/specs/07-security-privacy.md;
   missing audit logging; unsafe file handling; injection; unsandboxed templates; secrets in code.
5. Human-in-the-loop: any path where the system rejects a candidate, changes a stage, or sends
   interview / rejection / offer / submitted emails without explicit user confirmation.
6. Database: migration upgrades and downgrades cleanly; indexes and constraints present.
7. Tests: meaningful assertions, no network calls, no skipped or weakened tests, no tests edited
   to fit wrong behavior.
8. UI (if touched): strings in frontend/src/i18n/vi.ts; no technical terms shown to HR users
   ("LLM", "embedding", "prompt", "JSON"); clear Vietnamese error messages; undo where required.
9. Maintainability: structure per docs/specs/01-architecture.md; logic in services, not routers;
   no dead code or debug leftovers.

## Step 3 — Report
Report only real issues; skip style nitpicks that lint catches or that do not affect behavior.
Each finding: file:line, what is wrong, why it matters, concrete fix.

Write the report to `tasks/reviews/TASK.md` (overwrite if it exists) AND print it, in exactly
this format:
**Verdict:** APPROVE / APPROVE WITH NITS / CHANGES REQUIRED
**Checks run:** command — result
**Acceptance criteria:** each criterion — met / partial / not met / not proven — evidence
**Findings:**
- [BLOCKER] F1 ... (must fix: bugs, spec violations, PII/security issues, unmet criteria)
- [MAJOR] F2 ... (should fix now: missing tests, risky edge cases, scope creep)
- [MINOR] F3 ... (can follow up)
**Out-of-scope changes:** list or "none"
**Questions for the author:** if any
