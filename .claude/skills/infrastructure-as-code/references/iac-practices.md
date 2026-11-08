# IaC Practices

## Stack detection

| Evidence | Tool | Plan command |
|---|---|---|
| `*.tf`, `.terraform.lock.hcl` | Terraform / OpenTofu | `terraform plan -out=tfplan` then `terraform show tfplan` |
| `Pulumi.yaml` | Pulumi | `pulumi preview --diff` |
| `*.bicep`, ARM JSON | Azure Bicep/ARM | `az deployment group what-if` |
| CloudFormation / CDK | AWS | Change sets / `cdk diff` |
| `playbook.yml`, `inventory` | Ansible | `--check --diff` |

## Reading a plan

| Symbol / action | Meaning | Action |
|---|---|---|
| `+` create | New resource | Check naming, tags, exposure, cost |
| `~` update in-place | Attribute change | Check for downtime-causing attributes |
| `-/+` replace | Destroy then create | **Stop** for stateful resources; find the attribute forcing replacement |
| `-` destroy | Removal | **Stop** unless intended and approved |
| Unexpected changes | Drift or provider upgrade | Investigate before applying |

## Layout

- Separate state per environment and per blast-radius unit (network, data, app).
- Modules with typed, validated inputs and documented outputs; pin module and provider versions.
- `terraform fmt` / `validate` and a linter (tflint, checkov or similar) in CI.

## Safe refactoring

| Change | Use |
|---|---|
| Rename/move a resource in code | `moved` block (Terraform 1.1+) |
| Adopt an existing resource | `import` block / command |
| Split state | Documented migration with backups of state |

## Security defaults

- No `0.0.0.0/0` ingress except intentional public endpoints (and then only ports 80/443).
- Storage: block public access, encryption on, versioning for important buckets.
- IAM: no wildcard actions on wildcard resources; separate deploy and runtime roles.
- Tags: owner, environment, cost center (values `UNKNOWN` until provided).
