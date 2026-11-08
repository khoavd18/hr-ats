---
name: container-platform-engineer
description: Build container images and run workloads on Docker Compose or Kubernetes with the project's tooling, such as Docker, Podman, Helm, Kustomize, Argo CD, Flux, EKS, AKS or GKE. Use when writing or slimming Dockerfiles; multi-stage builds; running as non-root; health checks; Kubernetes Deployments, Services, Ingress, ConfigMaps and Secrets; resource requests and limits; liveness, readiness and startup probes; rollouts and autoscaling; network policies; Helm charts and GitOps; or debugging CrashLoopBackOff, OOMKilled, image pull errors and pending pods. Not for cloud resources outside the cluster (use infrastructure-as-code) or pipeline definitions (use ci-cd-engineer).
---

# Container Platform Engineer

Produces small, non-root, reproducible images and workloads that start, scale and fail predictably.

## Inputs

- The application, its runtime, ports, configuration, state and dependencies; the target platform (Compose, Kubernetes distribution, managed service).
- Capacity, availability and security requirements (resource budgets, replicas, policies): `UNKNOWN` until stated.

## Procedure

1. **Detect the stack**: Dockerfiles, compose files, charts, kustomizations, GitOps repos, cluster version, registry, existing labels and conventions.
2. **Image**: pinned base image (digest or exact tag), multi-stage build, minimal runtime layer, non-root user, no secrets in layers or build args, `.dockerignore`. Checklist in [container-checklist.md](references/container-checklist.md).
3. **Configuration**: environment-specific values through ConfigMaps/values files; secrets through the platform's secret mechanism or an external secret operator.
4. **Workload spec**: requests and limits from measured usage, readiness/liveness/startup probes that reflect real health, graceful shutdown, `PodDisruptionBudget` and anti-affinity for availability.
5. **Security context**: `runAsNonRoot`, read-only root filesystem where possible, dropped capabilities, network policies limiting traffic.
6. **Rollout**: rolling update parameters or progressive delivery; image tag = commit SHA; verify with `kubectl rollout status` and health checks.
7. **Validate before applying**: render templates, `kubectl diff` or `--dry-run=server`, policy checks.
8. **Debug systematically**: `describe` events, logs (including previous container), resource usage, probes, image pull credentials.

## Rules

- Never apply, delete or scale workloads in shared or production clusters without confirmation of the diff.
- No secrets baked into images, committed in manifests or printed in logs.
- No `latest` tags or privileged containers in production without a documented exception.
- Probes must not depend on downstream services in a way that cascades restarts.
- Cluster changes follow the risk tiers of the [ops safety contract](../infrastructure-as-code/references/ops-safety-contract.md).

## Outputs

Dockerfile and manifests/charts, the rendered diff, resource and probe rationale, rollout and rollback commands, and debugging findings.

## Hand-offs

Cluster and cloud provisioning → **infrastructure-as-code**. Build and deploy pipeline → **ci-cd-engineer**. Dashboards and alerts → **observability-sre**.
