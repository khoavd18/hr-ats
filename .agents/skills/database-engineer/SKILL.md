---
name: database-engineer
description: Design and evolve application (OLTP) databases in the project's engine and tooling, such as PostgreSQL, MySQL, SQL Server, SQLite or MongoDB with Alembic, Django migrations, Prisma, Flyway, Liquibase or EF Core. Use when designing tables, keys and constraints; normalizing or denormalizing; choosing indexes for application queries; writing safe, zero-downtime migrations and data backfills; fixing N+1 queries, slow queries and lock contention; choosing transaction isolation; or planning backups and restores. Not for analytical queries and reporting SQL (use sql-analytics-expert) or warehouse transformation layers (use warehouse-modeling).
---

# Database Engineer

Keeps the application's data correct by construction (constraints), fast for the queries the app actually runs, and safe to change while the app is live.

## Inputs

- Entities, relationships and the application's read/write patterns (the queries, not just the tables).
- Data volume, growth, availability and recovery requirements: `UNKNOWN` until stated.

## Procedure

1. **Detect the stack**: engine and version, ORM, migration tool and history, environments, how migrations run in deployment.
2. **Model with constraints**: primary keys, foreign keys, `NOT NULL`, `UNIQUE`, `CHECK`; the database enforces invariants the application assumes.
3. **Index for real queries**: list the top queries with their filters and sort; add composite indexes in the right column order; verify with `EXPLAIN` on realistic data. See [schema-and-migrations.md](references/schema-and-migrations.md).
4. **Migrations are code**: one reviewed migration per change, reversible where possible, tested on a copy of production-sized data for duration and locks.
5. **Zero-downtime changes**: expand → migrate data → switch code → contract; never rename or drop a column that running code still uses.
6. **Backfills**: batched, resumable, throttled, with progress logging and a verification query.
7. **Transactions**: choose isolation deliberately; keep transactions short; handle deadlocks with retries.
8. **Performance fixes**: N+1 (eager loading), missing indexes, over-fetching columns, pagination; measure before and after.
9. **Recovery**: confirm backups exist and a restore has been tested for high-risk changes.

## Rules

- Never run destructive DDL or data deletes on shared or production databases without explicit confirmation and a backup.
- No credentials in migrations, code or logs; connection strings come from configuration.
- Constraints are not optional "for performance" without measurement and a documented reason.
- Personal data: minimize columns, consider encryption at rest for sensitive fields, and respect retention rules.
- Migrations touching personal or financial data are high tier in the [engineering quality contract](../software-testing/references/engineering-quality-contract.md).

## Outputs

Schema changes as migrations, index rationale with query plans, a rollout plan for risky changes (expand/contract, backfill steps, rollback), and verification queries.

## Hand-offs

API code using the schema → **backend-api-engineer**. Reporting queries → **sql-analytics-expert**. Migration tests → **software-testing**.
