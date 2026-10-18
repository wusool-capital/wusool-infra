# Human access to the shared dev/prod account.
#
# Developers read /wusool/dev/toolkit at app startup (see server/README.md), so
# they must be able to read the dev secret and never the prod one. Dev and prod
# share this account, so the only boundary available is an explicit Deny on the
# prod secret ARNs and the RDS master secrets. A Deny beats any Allow,
# including AdministratorAccess.
#
# Residual risk (docs/internal/dev/AWS_ACCESS.md): PowerUser can still run SSM
# commands on the prod instance, so this is defence in depth, not isolation.

data "aws_iam_policy_document" "deny_prod_secrets" {
  statement {
    sid    = "DenyProdToolkitSecret"
    effect = "Deny"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:BatchGetSecretValue",
    ]
    resources = [
      "arn:aws:secretsmanager:*:${data.aws_caller_identity.current.account_id}:secret:/${var.project}/prod/*",
      # RDS-managed master logins (dev and prod): only admins and the deploy
      # migration step may hold DDL rights.
      "arn:aws:secretsmanager:*:${data.aws_caller_identity.current.account_id}:secret:rds!db-*",
    ]
  }
}

# Transitional: the IAM users in these groups stay until everyone has moved to
# Identity Center. Not gated by enable_identity_center - it applies today.
resource "aws_iam_policy" "deny_prod_secrets" {
  name        = "${var.project}-deny-prod-secrets"
  description = "Developers must not read production application secrets."
  policy      = data.aws_iam_policy_document.deny_prod_secrets.json
}

resource "aws_iam_group_policy_attachment" "deny_prod_secrets" {
  for_each   = toset(["Developers", "PowerUsers"])
  group      = each.key
  policy_arn = aws_iam_policy.deny_prod_secrets.arn
}

# --- IAM Identity Center ---------------------------------------------------
# Users are created and added to groups in the console: keeping people out of
# the repo avoids committing personal data. The portal session length (7 days)
# and MFA are Identity Center settings with no Terraform resource.

data "aws_ssoadmin_instances" "this" {
  count = var.enable_identity_center ? 1 : 0
}

locals {
  sso_instance_arn  = var.enable_identity_center ? one(data.aws_ssoadmin_instances.this[0].arns) : ""
  identity_store_id = var.enable_identity_center ? one(data.aws_ssoadmin_instances.this[0].identity_store_ids) : ""

  # Permission set name -> group and managed policy. Only developers get the
  # prod-secret deny inline; admins and billing are deliberately unrestricted.
  sso_access = var.enable_identity_center ? {
    WusoolAdmin     = { group = "wusool-admins", managed_policy = "AdministratorAccess" }
    WusoolDeveloper = { group = "wusool-developers", managed_policy = "PowerUserAccess" }
    WusoolBilling   = { group = "wusool-billing", managed_policy = "job-function/Billing" }
  } : {}
}

resource "aws_identitystore_group" "access" {
  for_each          = local.sso_access
  identity_store_id = local.identity_store_id
  display_name      = each.value.group
}

resource "aws_ssoadmin_permission_set" "access" {
  for_each         = local.sso_access
  name             = each.key
  instance_arn     = local.sso_instance_arn
  session_duration = "PT8H"
}

resource "aws_ssoadmin_managed_policy_attachment" "access" {
  for_each           = local.sso_access
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.access[each.key].arn
  managed_policy_arn = "arn:aws:iam::aws:policy/${each.value.managed_policy}"
}

resource "aws_ssoadmin_permission_set_inline_policy" "developer_deny_prod_secrets" {
  count              = var.enable_identity_center ? 1 : 0
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.access["WusoolDeveloper"].arn
  inline_policy      = data.aws_iam_policy_document.deny_prod_secrets.json
}

resource "aws_ssoadmin_account_assignment" "access" {
  for_each           = local.sso_access
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.access[each.key].arn
  principal_id       = aws_identitystore_group.access[each.key].group_id
  principal_type     = "GROUP"
  target_id          = data.aws_caller_identity.current.account_id
  target_type        = "AWS_ACCOUNT"
}
