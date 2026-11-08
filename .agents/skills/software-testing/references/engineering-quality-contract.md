# Engineering Quality Contract

Shared by the software engineering skills (`frontend-engineer`, `backend-api-engineer`, `database-engineer`, `software-testing`, `secure-code-review`, and the DevOps skills). It is the software counterpart of the analytical and ML quality contracts. Apply the subset that matches the risk tier.

## 1. Checks

| Dimension | Question | Typical evidence |
|---|---|---|
| Requirements | What exactly should change, and what must not? | Issue or spec reference; acceptance criteria (or `UNKNOWN`) |
| Correctness | Does it work, including edge and error cases? | Tests run with output shown |
| Security | Are inputs validated, access checked, secrets protected? | Review against the security checklist; dependency scan |
| Compatibility | Do existing clients, data and APIs keep working? | Contract tests, migration plan, versioning |
| Performance | Is it fast enough for the expected load? | Measurement on realistic data, not intuition |
| Operability | Can it be observed, configured and rolled back? | Logs, metrics, feature flags, rollback steps |
| Maintainability | Is it consistent with the codebase? | Follows existing patterns, lint/format pass |

## 2. Risk tiers

| Tier | Example | Minimum |
|---|---|---|
| Low | Internal script, copy change | Runs; lint passes |
| Medium | Feature in an internal app | Low + tests for new behaviour + review |
| High | Auth, payments, personal data, public API, data migration | Medium + security review + migration/rollback plan + integration tests + second reviewer |

## 3. Evidence vocabulary

**VERIFIED** (command output or test result shown), **INFERRED**, **ASSUMED**, **UNKNOWN** (requirements, SLAs, owners), **NOT TESTED**. Code that compiles or a passing lint is not evidence that behaviour is correct.

## 4. Coordination

| Task | Chain |
|---|---|
| New feature | backend-api-engineer / frontend-engineer (+ database-engineer for schema) → software-testing → secure-code-review |
| Bug | software-testing (reproduce) → fix in the owning skill → regression test |
| Release | software-testing in CI → DevOps skills (ci-cd-engineer) → observability |

## 5. Safety baseline

- No secrets in code, tests, logs or client bundles.
- Ask before destructive or irreversible actions: dropping tables, deleting data, force-pushing, rotating credentials, production deploys.
- Do not disable security controls (auth, CSRF, TLS verification, CORS restrictions) to make something work.
