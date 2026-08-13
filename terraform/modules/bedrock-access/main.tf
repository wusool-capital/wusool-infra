data "aws_caller_identity" "current" {}

locals {
  # Plain on-demand foundation models, invoked directly in their own region.
  foundation_model_arns = [
    for m in var.models :
    "arn:aws:bedrock:${m.region}::foundation-model/${m.model_id}"
    if m.inference_profile_id == null
  ]

  # Models that require a cross-region inference profile (e.g. some newer
  # Anthropic models reject on-demand invocation). Granting the profile ARN
  # is required; the underlying foundation model ARN is also required since
  # the profile can route the request to any region it covers, and Bedrock
  # checks both the profile ARN and the resolved model ARN.
  inference_profile_arns = [
    for m in var.models :
    "arn:aws:bedrock:${m.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${m.inference_profile_id}"
    if m.inference_profile_id != null
  ]

  inference_profile_model_arns = [
    for m in var.models :
    "arn:aws:bedrock:*::foundation-model/${m.model_id}"
    if m.inference_profile_id != null
  ]

  model_arns = concat(
    local.foundation_model_arns,
    local.inference_profile_arns,
    local.inference_profile_model_arns,
  )
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "${var.project}-${var.environment}-bedrock-invoke"
  role = var.iam_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeBedrockModels"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = local.model_arns
      }
    ]
  })
}
