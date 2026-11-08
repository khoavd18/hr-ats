# Schema and Migrations

## Index design

| Query pattern | Index |
|---|---|
| `WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC` | `(tenant_id, status, created_at DESC)` |
| Lookup by unique business key | `UNIQUE (tenant_id, external_id)` |
| Foreign key used in joins/deletes | Index on the FK column (PostgreSQL does not create it automatically) |
| Text search | Engine's full-text index, not `LIKE '%x%'` |

Check every new index with `EXPLAIN (ANALYZE, BUFFERS)` (PostgreSQL) or the engine's equivalent on realistic data; every index costs writes and storage.

## Zero-downtime change patterns

| Change | Safe sequence |
|---|---|
| Add column | Add nullable or with a constant default (engine-dependent cost) → backfill in batches → add NOT NULL after backfill |
| Rename column | Add new → write both → backfill → read new → stop writing old → drop old later |
| Change type | New column + backfill + switch, not in-place `ALTER TYPE` on large tables |
| Add index on large table | Online/concurrent build (`CREATE INDEX CONCURRENTLY` in PostgreSQL) |
| Drop column/table | Remove all code references and deploy first; drop in a later release |

## Batched backfill sketch

```sql
-- repeat until 0 rows updated; throttle between batches; log progress
UPDATE orders SET status_v2 = status
WHERE id IN (SELECT id FROM orders WHERE status_v2 IS NULL ORDER BY id LIMIT 5000);
```

## N+1 detection

Log the query count per request in development; a list page issuing one query per row needs eager loading (`select_related`/`prefetch_related`, `joinedload`, `include`).

## Isolation levels (typical defaults)

| Level | Prevents | Watch out |
|---|---|---|
| Read committed | Dirty reads | Lost updates without row locks or version checks |
| Repeatable read / snapshot | Non-repeatable reads | Serialization errors to retry (engine-dependent) |
| Serializable | Anomalies | More retries; keep transactions short |
