---
name: sync-terraform-docs
description: Synchronize README files, architecture documentation, and network diagrams with the repository's current Terraform configuration. Use after changing Terraform resources, modules, variables, outputs, regions, instance sizes, networking, security controls, state backends, or operational services, and whenever asked to refresh, regenerate, verify, or reconcile infrastructure documentation.
---

# Sync Terraform Docs

Keep infrastructure documentation factual and reviewable. Treat Terraform as
the source of truth and never infer deployed state that the code cannot prove.

## Workflow

1. Run the inventory script from the repository root:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/sync-terraform-docs/scripts/inspect-terraform.ps1
   ```
2. Read all relevant `.tf`, committed `.tfvars.example`, backend, provider,
   module, output, bootstrap, and user-data/template files.
3. Compare the inventory with:
   - `README.md`
   - environment README files
   - `workflows/n8n/docs/*architecture*.md`, `workflows/n8n/docs/infrastructure-overview.md`
   - architecture SVG files referenced by those documents
4. Correct stale statements, diagrams, commands, paths, regions, CIDRs,
   instance types, ports, services, and state-management details.
5. Preserve hand-written rationale and operational guidance unless Terraform
   directly contradicts it.
6. Prefer bounded generated sections when replacing structured summaries. Use
   the marker policy in `references/documentation-policy.md`.
7. Update both the diagram source and its Markdown reference when topology
   changes. Keep diagrams deterministic, editable SVG or Mermaid; do not use
   generative images for architecture diagrams.
8. Run:

   ```powershell
   terraform fmt -check -recursive
   # From each affected, initialized environment:
   terraform validate
   git diff --check
   ```

   Run `terraform validate` from each initialized environment affected by the
   change. Do not run `terraform apply`.
9. Review `git diff`. Report changed documentation, validation results, and
   any uncertainty that requires live AWS state or credentials.

## Source-of-truth rules

- Use environment variables and committed examples for documented defaults.
- Never publish secrets or values from ignored local `terraform.tfvars`.
- A local ignored value may be used to verify the current workspace only; do
  not copy emails, IP addresses, credentials, account tokens, or key names into
  documentation.
- Distinguish code-defined architecture from confirmed deployed state.
- Do not claim CI, staging, production, NAT, databases, Kubernetes, or DNS
  resources exist unless present in the repository.
- Derive runtime components such as Caddy, Docker, n8n, ports, and volumes from
  user-data/templates as well as Terraform resources.
- Preserve unrelated user edits and existing documentation style.
- Never delete a document merely because it is stale; reconcile it.

## Expected outputs

Update only files justified by architecture changes. Typical outputs are:

- Root architecture/status summary and repository tree in `README.md`
- Environment-specific architecture and workflow README
- Mermaid request/operations flow
- Editable SVG network architecture diagram
- Inputs, outputs, security controls, monitoring, and state-backend summaries

If no documentation change is needed, say so and provide the checks performed.
