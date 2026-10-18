# AWS access for developers

> Internal execution detail retained outside the client-facing GitBook
> navigation.

Developers run the Toolkit locally against the **dev** secret
(`/wusool/dev/toolkit`) using their own AWS sign-in; there is no `.env` with
secrets. Dev and prod share account `030179310793`, so the only boundary is an
explicit Deny on `/wusool/prod/*` secrets, defined in
`infrastructure/terraform/stacks/account/access.tf`.

## What Terraform manages

| Piece | Where | Notes |
| --- | --- | --- |
| `wusool-deny-prod-secrets` IAM policy | attached to IAM groups `Developers` and `PowerUsers` | Applies as soon as `stacks/account` is applied. Transitional, until the IAM users are retired. |
| Identity Center groups `wusool-admins`, `wusool-developers`, `wusool-billing` | `access.tf`, gated by `enable_identity_center` | Users are added in the console, so no personal data lives in the repo. |
| Permission sets `WusoolAdmin`, `WusoolDeveloper`, `WusoolBilling` | same | `WusoolDeveloper` is PowerUserAccess plus the prod-secret Deny inline. |

A Deny beats any Allow, including `AdministratorAccess`. A user who is in
`Developers` *and* `Administrators` is therefore blocked from the prod secret
too: move such users out of `Developers` first.

## One-time admin steps (before `enable_identity_center = true`)

None of these are in Terraform. Status as of 2026-10-18: steps 1, 2, 3, 5 and 6 and the
IAM deny are done; only step 4 (creating users) is open. The instance is
Single-Region in `eu-central-1`; the portal is
`https://d-9967b18774.awsapps.com/start`.

1. **Create the AWS Organization** from this account (done: `o-p22vgvr7jc`;
   verify the management account's email address within 7 days, or AWS
   suspends the account). This account becomes the
   management account, and service control policies never apply to a
   management account.
2. **Enable IAM Identity Center** in `eu-central-1` (same region as the
   provider in `stacks/account`), from the console: the `CreateInstance` API
   is rejected in a management account. Identity Center and its portal are
   free. Choose the Single-Region instance: Multi-Region adds a paid KMS key.
3. **Set the session duration to 7 days** (Identity Center → Settings →
   Authentication → Session settings) and **require MFA**. Longer sessions
   leave a lost laptop signed in for longer, so the Identity Center admin
   signs this off.
4. **Create users** and add them to the groups. Groups are created by
   Terraform in the next step, so run step 5 first and add users after.
5. **Apply `stacks/account`** (done; `enable_identity_center` now defaults to
   `true`). Disable background and Kiro sessions in the session settings, since
   nothing here uses them.
6. **Move `abhay.krishna` out of `Developers` and `PowerUsers`** (done; he stays
   in `Administrators`). Both groups carry the deny.

Retiring IAM users' console access is a follow-up once everyone has signed in
through Identity Center.

## Developer setup

See `server/README.md` → Setup. In short: an `sso-session` profile in
`~/.aws/config` with `sso_role_name = WusoolDeveloper`, then `aws sso login`
about once a week. The CLI refreshes role credentials from the SSO session
automatically, so the session duration is the real limit. The app reads the
secret only at startup, so an expired session blocks starting or restarting
the app, never a running one.

## Verify

```bash
export AWS_PROFILE=wusool-sso
aws secretsmanager get-secret-value --secret-id /wusool/dev/toolkit --query Name   # works
aws secretsmanager get-secret-value --secret-id /wusool/prod/toolkit --query Name  # AccessDenied
```

## Residual risk

The Deny is defence in depth, not isolation. `PowerUserAccess` can still read
the RDS-managed master password secrets (`rds!db-*`), and can run
`ssm:SendCommand` against the prod toolkit instance and act with its role.
Real isolation needs a separate prod account. `ATTIO_API_KEY` is also the same
SOURCE key in both environments (separated only by `ATTIO_IS_TEST`), so every
developer who can read the dev secret can read it. That is an accepted risk.
