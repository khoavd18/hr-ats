# Workflow: implement a task

The user names one task id (e.g. "Implement T05"). Below, `TASK` means that id.

## Step 0 — Read and check (do not edit files yet)
1. Read AGENTS.md, tasks/README.md, tasks/PROGRESS.md, tasks/TASK-*.md, and every spec listed on
   the task's "Spec" line. Specs are written in Vietnamese; read them carefully.
2. If any dependency task is not marked done in PROGRESS.md: stop and report which one.
3. If the git working tree has uncommitted changes from another task: stop and report.
4. If git is available, create or switch to branch `task/TASK-<short-name>`.
5. Inspect existing related code so you don't duplicate or break what is already there.

## Step 1 — Short plan
Write a 5–10 line plan: files to create/modify, main components, and for EACH acceptance criterion
the test or command that will prove it. Then proceed without waiting.
If the task changes the DB schema beyond what the spec describes, or is clearly larger than
described: stop after the plan and wait for approval.

## Step 2 — Implement
- Stay strictly within the task scope. Do not change the stack, do not add libraries or services
  not in the spec unless the task requires it, do not refactor unrelated code.
- Work in small steps and run tests after each part.
- If the spec is unclear: choose the simplest option consistent with the spec, record it in
  docs/specs/open-questions.md (task id, question, chosen default), and continue.
- Hard rules: no real personal data in code, tests, fixtures, or logs; all UI strings live in
  frontend/src/i18n/vi.ts (Vietnamese); tests never call external networks
  (use FakeLLM / FakeEmbedder).
- Only mark a task blocked if an acceptance criterion cannot be met. Problems in optional parts
  that are not acceptance criteria go to open-questions.md and do not block the task.

## Step 3 — Verify
- Run the exact test, lint, typecheck, and migration commands from
  docs/specs/08-testing-quality.md for everything affected; fix until they pass.
  Never edit tests to match wrong code, never skip or delete tests, never weaken criteria.
- Review your own diff as a strict reviewer: matches the spec, edge cases handled, no PII leaks,
  no out-of-scope changes. Fix whatever you find.

## Step 4 — Finish
- Update tasks/PROGRESS.md (status `review` when done, or `blocked`, with notes).
- If you changed an API contract, schema, or KPI definition, update the matching spec.
- Commit all changes on the task branch with message `TASK: <short summary>`.
- End with exactly this format:
  **Result:** done / blocked (reason)
  **Acceptance criteria:** each criterion — met/not met — evidence (test or command)
  **Key files:** list
  **Commands run:** command and outcome
  **Open questions / remaining work:** if any

Stop and ask only if: a dependency task is missing, a major change outside the spec is needed,
or you need secrets (API keys, passwords).
