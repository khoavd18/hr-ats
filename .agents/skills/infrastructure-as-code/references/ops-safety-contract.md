# Ops Safety Contract

Shared by the DevOps skills (`infrastructure-as-code`, `ci-cd-engineer`, `container-platform-engineer`, `observability-sre`). It complements the engineering quality contract used by the software skills. Apply the subset that matches the risk tier.

## 1. Principles

1. **Dry-run first**: plan, diff, `--dry-run=server`, preview or what-if before every change.
2. **Explicit confirmation** for anything destructive or production-facing: apply, destroy, delete, scale to zero, rollout to production, credential rotation, force-push, history rewrite.
3. **Reversible by default**: know the rollback before the rollout; keep the previous artifact or version.
4. **Least privilege**: the narrowest role, the shortest-lived credential.
5. **Everything in code**: manual changes are drift and must be reconciled.

## 2. Risk tiers

| Tier | Example | Minimum |
|---|---|---|
| Low | Dev sandbox, personal namespace | Dry-run read; change in code |
| Medium | Shared staging, internal service | Low + reviewed plan/diff + rollback note + monitoring check after change |
| High | Production, data stores, networking, IAM, DNS, secrets | Medium + explicit approval + change window or progressive rollout + verified backup + second reviewer |

## 3. Evidence vocabulary

**VERIFIED** (plan/diff/command output shown), **INFERRED**, **ASSUMED**, **UNKNOWN** (owners, SLOs, maintenance windows, budgets), **NOT TESTED** (for example rollback not rehearsed). "The pipeline is green" is not evidence that production is healthy.

## 4. Coordination

| Task | Chain |
|---|---|
| New service | container-platform-engineer (image, manifests) → infrastructure-as-code (cloud resources) → ci-cd-engineer (build, deploy) → observability-sre (SLOs, alerts) |
| Incident | observability-sre (detect, mitigate) → owning skill (fix) → postmortem |
| Security finding in pipeline or infra | secure-code-review → owning DevOps skill |

## 5. Secrets baseline

- Secrets live in a secret manager or the platform's secret store; never in git, images, logs, plan outputs or chat.
- Prefer workload identity / OIDC federation over long-lived keys.
- A secret seen in a log or commit is compromised: report its location (not its value) and rotate.
