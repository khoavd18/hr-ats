# API Design Conventions (defaults when the project has none)

## REST

| Operation | Method | Success | Common errors |
|---|---|---|---|
| List | GET /orders?status=open&limit=50&cursor=… | 200 | 400 invalid filter |
| Read | GET /orders/{id} | 200 | 404 (also when the caller may not see it) |
| Create | POST /orders (Idempotency-Key header) | 201 + Location | 400, 409 conflict, 422 validation |
| Replace / update | PUT / PATCH /orders/{id} | 200 / 204 | 404, 409 version conflict |
| Delete | DELETE /orders/{id} | 204 | 404 |

## Error body

```json
{"error": {"code": "validation_error", "message": "quantity must be > 0",
           "details": [{"field": "items[0].quantity", "issue": "must be greater than 0"}],
           "request_id": "req_123"}}
```

## Pagination

Prefer cursor pagination for large or changing collections; offset pagination only for small, stable lists. Always cap `limit`.

## Idempotency

For retried writes, store `(idempotency_key, request hash) -> response` for a retention window; a repeated key with the same request returns the stored response, a different request returns 409.

## Authorization checklist

- Every handler checks the caller's right to this specific object (tenant, owner, role).
- List endpoints filter by the caller's scope in the query, not after fetching.
- Admin-only operations are enforced server-side, never by hiding UI buttons.

## Background work

Move work that is slow, retryable or not needed for the response (emails, reports, webhooks) to a queue; jobs are idempotent and record their outcome.
