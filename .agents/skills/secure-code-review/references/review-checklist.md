# Security Review Checklist

## Access control

- [ ] Every endpoint/action checks authentication and object-level authorization (owner, tenant, role).
- [ ] No privilege decisions based on client-supplied fields (`role`, `is_admin`, `user_id` in body).
- [ ] Session/token: expiry, rotation on login, secure + httpOnly + SameSite cookies, logout invalidates.

## Input and injection

| Sink | Safe pattern | Red flag |
|---|---|---|
| SQL | Parameterized queries / ORM | f-strings or concatenation with input |
| Shell | Argument lists, no shell | `shell=True`, `exec`, backticks with input |
| HTML | Template auto-escaping, sanitizer for rich text | Raw HTML insertion of user content |
| File paths | Resolve and check inside an allowed root | `../` reachable, user-chosen filenames |
| Server-side fetch (SSRF) | Allowlist hosts, block internal ranges | Fetching arbitrary user URLs |
| Deserialization | JSON with schemas | `pickle`, unsafe YAML loaders, Java/.NET native serialization of input |
| Redirects | Allowlist | Open redirect to user-supplied URL |

## Secrets and data

- [ ] No keys, tokens or passwords in code, configs, tests, logs or client bundles.
- [ ] Personal data minimized in logs and error messages; masked where needed.
- [ ] Crypto from standard libraries; no custom algorithms; passwords hashed with a slow KDF (bcrypt, scrypt, Argon2).

## Files and uploads

- [ ] Size limits, type checks by content, storage outside the web root, generated filenames, malware scanning if required.

## Web specifics

- [ ] CSRF protection for cookie-authenticated state changes.
- [ ] CORS restricted to known origins; no `*` with credentials.
- [ ] Security headers per project policy (CSP, HSTS, X-Content-Type-Options).

## Report format

```
| Severity | Location | Issue | Evidence | Fix | Status |
| High | api/orders.py:88 | Missing object-level auth on GET /orders/{id} | Query filters by id only | Filter by tenant_id of caller; add test | Confirmed |
```

Severity guide: Critical (remote, unauthenticated, data/system compromise), High (authenticated access to others' data or privilege escalation), Medium (limited impact or hard to reach), Low (defence in depth).
