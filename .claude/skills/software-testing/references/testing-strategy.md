# Testing Strategy

## Stack detection

| Evidence | Runner | Notes |
|---|---|---|
| `pytest.ini`, `conftest.py`, `pyproject [tool.pytest]` | pytest | Fixtures in `conftest.py`; markers for slow/integration |
| `jest.config.*`, `vitest.config.*` | Jest / Vitest | Check environment (`jsdom` vs `node`) |
| `playwright.config.*`, `cypress.config.*` | E2E | Base URL, test users, CI browsers |
| `*Test.java`, `*.Tests.csproj` | JUnit / xUnit | Testcontainers availability |

## What goes where

| Level | Scope | Speed | Use for |
|---|---|---|---|
| Unit | One function/class, no I/O | ms | Business rules, parsing, calculations, edge cases |
| Integration | Real DB/queue/HTTP in a container | s | Queries, migrations, repositories, API handlers with persistence |
| Contract | Consumer–provider API shape | s | Services that evolve independently |
| End-to-end | Real UI through the stack | 10s+ | A handful of critical journeys (login, checkout) |

## Flaky test causes

| Cause | Fix |
|---|---|
| Real clock / time zones | Inject or freeze the clock; use UTC |
| Randomness | Seed or inject the generator |
| Async waits with sleeps | Wait for a condition or event |
| Shared state between tests | Isolate data per test; transactions rolled back per test |
| Test order dependence | Run in random order locally to expose it |
| External network | Fake the service at the HTTP boundary |

## Regression test for a bug

```
1. Write a test that reproduces the reported behaviour -> it fails for the stated reason.
2. Fix the code.
3. The test passes; the rest of the suite still passes.
4. Name the test after the behaviour, link the issue id in a comment.
```

## Coverage

Use coverage to find untested changed lines and branches. A global percentage target encourages trivial tests; prefer "changed code is covered by a meaningful assertion".
