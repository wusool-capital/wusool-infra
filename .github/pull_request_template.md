## Summary

Describe the infrastructure change and why it is needed.

## Target environment

- [ ] Development
- [ ] Production template
- [ ] Shared module or bootstrap
- [ ] Documentation only

## Validation

- [ ] `terraform fmt -check -recursive`
- [ ] `terraform validate` passed for every affected root module
- [ ] Terraform plan reviewed when AWS access was required
- [ ] Architecture documentation synchronized with `$sync-terraform-docs`
- [ ] No credentials, state files, plan files, private keys, or local
      `terraform.tfvars` are included

## Risk and rollback

Describe replacements, deletions, downtime, cost impact, and rollback steps.

## Reviewer notes

Call out the files and plan changes that require particular attention.
