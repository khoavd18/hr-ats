---
name: software-testing
description: Plan, write and fix automated tests for application code in the project's framework, such as pytest, unittest, Jest, Vitest, Testing Library, Playwright, Cypress, JUnit or xUnit. Use when choosing what to test at unit, integration and end-to-end level; writing fixtures, factories and test data; mocking external services at the right boundary; testing APIs and database code against real dependencies in containers; fixing flaky or slow tests; reading coverage; adding regression tests for a bug; or wiring tests into CI. Not for validating data contents or pipelines (use data-quality-auditor) or for evaluating ML models (use ml-model-evaluation).
---

# Software Testing

Builds a test suite that catches real regressions quickly and does not cry wolf.

## Inputs

- The code under change, its behaviour contract (requirements, API spec, bug report) and the existing test setup.
- Quality bars (coverage targets, required test types, CI time budget): `UNKNOWN` unless the project defines them.

## Procedure

1. **Detect the stack**: test runners and versions, config files, fixtures and factories already in use, how tests run in CI, test databases or containers. Extend the existing style.
2. **Decide the level** per behaviour: pure logic → unit; code that talks to a database, queue or HTTP API → integration against a real instance (container) where feasible; critical user journeys → a few end-to-end tests. See [testing-strategy.md](references/testing-strategy.md).
3. **Write the failing test first** for bugs: reproduce, then fix, and keep the test as a regression guard.
4. **Arrange data explicitly**: factories or builders with only the fields that matter; no dependence on test order or shared mutable state.
5. **Mock at the boundary you do not own** (third-party HTTP, payment provider, clock, randomness); do not mock the code under test or your own database layer in integration tests.
6. **Assert behaviour**: outputs, state changes, emitted events, error types and messages; not private implementation details.
7. **Fix flakiness at the root**: time, randomness, ordering, async waits, shared resources. Quarantine only with an owner and a date.
8. **Run and report**: the exact command, the result, and coverage of the changed lines (not a global percentage target).

## Rules

- Never claim tests pass without running them; show the command and output.
- Never delete or weaken a failing test to make CI green without explaining why the expectation was wrong.
- Test data is synthetic; no production personal data in fixtures or snapshots.
- No real credentials in tests; use test keys, fakes or environment variables.
- Apply the [engineering quality contract](references/engineering-quality-contract.md).

## Outputs

Tests in the project's framework, the command to run them with its output, notes on what is not covered and why, and CI changes if needed.

## Hand-offs

Security-focused review → **secure-code-review**. API behaviour → **backend-api-engineer**. UI behaviour → **frontend-engineer**. Database migrations → **database-engineer**.
