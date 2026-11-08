---
name: backend-api-engineer
description: Design, build and debug server-side APIs and services in the project's framework, such as FastAPI, Django, Flask, Express, NestJS, Spring Boot, ASP.NET Core or Go. Use when designing REST or GraphQL endpoints; request validation and error responses; authentication and authorization checks; pagination, filtering and sorting; idempotency keys and retries; transactions and concurrency; background jobs and queues; calling third-party APIs; API versioning and OpenAPI docs; logging and rate limiting; or diagnosing slow or failing endpoints. Not for schema and migration design (use database-engineer) or UI code (use frontend-engineer).
---

# Backend API Engineer

Builds endpoints with a clear contract: validated input, checked permissions, predictable errors, and safe behaviour under retries and concurrency.

## Inputs

- The use case, callers (UI, other services, partners), the data it reads and writes, and existing API conventions.
- Non-functional needs (latency, throughput, availability, compliance): `UNKNOWN` until stated.

## Procedure

1. **Detect the stack**: framework and version, project layout, ORM or query layer, auth mechanism, error format, API docs generation, config and secret loading. Follow the codebase's patterns.
2. **Contract first**: method, path, request and response schemas, status codes, error body, pagination; update the OpenAPI/GraphQL schema with the change. Conventions in [api-design.md](references/api-design.md).
3. **Validate input** at the boundary with the framework's schema tools; reject unknown or out-of-range values with a clear error.
4. **Authorize every operation** on the specific resource (object-level), not only "is logged in".
5. **Business logic** in a service layer, kept out of controllers and database models where the codebase separates them.
6. **Persistence**: transactions around multi-step writes; idempotency keys for operations clients may retry (payments, orders); optimistic locking where concurrent edits matter.
7. **External calls**: timeouts, retries with backoff for safe operations, circuit breaking or fallbacks; never block request threads on slow work — use background jobs.
8. **Observability**: structured logs with request id, no secrets or full personal data; metrics for latency and errors.
9. **Test** handlers with integration tests against a real database where feasible (**software-testing**), and get a security review for auth or sensitive data (**secure-code-review**).

## Rules

- Never build SQL, shell commands or file paths by string concatenation of user input.
- Secrets come from environment or a secret store; never committed, logged or returned in responses.
- Breaking API changes need versioning or a migration path for existing clients.
- Error responses do not leak stack traces, SQL or internal hostnames.
- Pick the review depth from the risk tiers in the [engineering quality contract](../software-testing/references/engineering-quality-contract.md).

## Outputs

Endpoint code, updated API schema, tests, notes on auth and data access, and any migration or rollout steps.

## Hand-offs

Schema, indexes and migrations → **database-engineer**. Tests → **software-testing**. Security review → **secure-code-review**. Deployment → DevOps skills.
