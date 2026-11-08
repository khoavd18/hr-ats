# Workflow: fix review findings

The user names one task id (e.g. "Fix T05"). Below, `TASK` means that id.

1. Read `tasks/reviews/TASK.md`, then tasks/TASK-*.md and the specs it lists. If the review file
   does not exist, stop and say so.
2. Stay on the task branch. Fix every BLOCKER and MAJOR finding. For each MINOR finding, fix it or
   explain why not.
3. Fix root causes. Do not edit tests to match wrong code, skip or delete tests, or weaken
   acceptance criteria. Stay within the task scope; same hard rules as tasks/_implement.md.
4. If you disagree with a finding, do not change the code for it; explain why with evidence.
5. Re-run the checks from docs/specs/08-testing-quality.md for everything affected.
6. Append a "## Fix round <n>" section to tasks/reviews/TASK.md listing each finding id —
   fixed / not fixed (reason) — evidence. Commit with message `TASK: fix review findings`.
7. End with: each finding — fixed / not fixed — evidence; commands run and results.
