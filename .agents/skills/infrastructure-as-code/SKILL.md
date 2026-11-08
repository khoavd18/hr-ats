---
name: infrastructure-as-code
description: Write, review and safely change cloud and server infrastructure as code with the project's tool, such as Terraform, OpenTofu, Pulumi, Bicep, ARM, CloudFormation, CDK or Ansible, on AWS, Azure, GCP or on-premises. Use when creating or refactoring modules; managing remote state, locking and workspaces or environments; reading and reviewing plans; importing existing resources; detecting drift; designing least-privilege IAM, networking and security groups; tagging and cost control; or protecting resources from accidental destroy. Not for container images and Kubernetes manifests (use container-platform-engineer) or CI pipelines (use ci-cd-engineer).
---

# Infrastructure as Code

Changes infrastructure only through reviewed code and reviewed plans, so that nothing is created, replaced or destroyed by surprise.

## Inputs

- The desired change, target environment(s), cloud account/subscription/project and existing IaC layout.
- Compliance, network, cost and availability constraints: `UNKNOWN` until the owner states them.

## Procedure

1. **Detect the stack**: tool and version (`required_version`, lock files), providers and versions, state backend and locking, environment layout (workspaces, folders, stacks), CI integration. Follow existing modules and naming.
2. **Write the change** in the smallest scope: reuse modules, variables with types and validation, no hard-coded account IDs or secrets.
3. **Plan, never apply blind**: run `plan` (or `preview` / what-if) and read every create, update in place, **replace** and **destroy**. Planning guide in [iac-practices.md](references/iac-practices.md).
4. **Review security**: least-privilege IAM, no public exposure by default (`0.0.0.0/0`, public buckets), encryption at rest and in transit, secrets from a secret manager.
5. **Protect stateful resources**: deletion protection / `prevent_destroy` / resource locks on databases, buckets with data, key vaults.
6. **State hygiene**: remote state with locking; `import` and `moved` blocks instead of manual state surgery; never edit state files by hand.
7. **Apply through the agreed path** (usually CI with approval) only after the plan is approved; record the plan output with the change.
8. **Verify and detect drift**: post-apply checks, scheduled drift detection, and fixes made in code rather than the console.

## Rules

- Never run `apply`, `destroy`, `state rm` or equivalent against shared or production environments without explicit confirmation of the reviewed plan.
- A plan that replaces or destroys a stateful resource stops the change until a human approves it explicitly.
- No credentials in code, variables files committed to git, state outputs or logs; prefer short-lived credentials (OIDC, managed identity).
- Changes made by hand in the console are drift; bring them into code or revert them.
- Apply the [ops safety contract](references/ops-safety-contract.md).

## Outputs

IaC code changes, the reviewed plan summary (create/update/replace/destroy counts and the risky items), security notes, and a rollout and rollback note.

## Hand-offs

Pipeline that runs plan/apply → **ci-cd-engineer**. Workloads on clusters → **container-platform-engineer**. Monitoring of the new resources → **observability-sre**. Code-level security review → **secure-code-review**.
