# Environments and access

The platform has isolated `dev` and `prod` AWS environments in the Frankfurt
region. They share an AWS account and one SOURCE Attio workspace, but use
separate networks, databases, secrets, container repositories, and deployment
roles. Test records in Attio distinguish development data from production data.

| Environment | Change path | n8n | Toolkit and lead tools |
| --- | --- | --- | --- |
| Development | Merge or manually run the `Deploy dev` workflow | `https://n8n-dev.wusoolcapital.com/` | Obtain the current URL from the toolkit stack output |
| Production | Merge or manually run the `Deploy prod` workflow | `https://n8n.wusoolcapital.com/` | Lead tools use `https://tools.wusoolcapital.com/`; obtain the current Toolkit URL from the stack output |

DNS is managed in Cloudflare. The repository defines the target services but
does not manage or prove the live Cloudflare records.

## Required access

An operator needs the minimum role for the task:

| System | Needed for |
| --- | --- |
| GitHub repository and Actions | Review changes, inspect checks, deploy, and rerun workflows |
| AWS through the organization's approved sign-in method | Read logs and alarms, use Systems Manager, inspect RDS, and run OpenTofu when necessary |
| Slack administration | Maintain the Toolkit app and operational alert channel |
| Attio administration | Maintain CRM attributes, lists, webhooks, and workspace users |
| Cloudflare administration | Maintain service DNS records |
| n8n owner or administrator account | Manage users, credentials, workflows, and execution history |

Named client owners and the access-request route are **not recorded in this
repository**. The client must add them to the ownership register before final
handover. Do not document account numbers, role identifiers, tokens, or personal
credentials here.

## Verify access before a change

1. Confirm the intended environment and Git branch (`dev` or `prod`).
2. Confirm GitHub shows the matching deployment environment and recent runs.
3. Authenticate to AWS and verify the current identity and Frankfurt region.
4. For shell work, confirm the target instance is online in Systems Manager.
5. For database work, use the documented Systems Manager tunnel or execute from
   an approved application instance; direct internet access should fail.
6. Open the relevant service URL and confirm its health before changing it.

**Expected outcome:** the operator can inspect the target without copying any
credentials locally or opening public database/SSH access.

**If verification fails:** stop before deploying. Ask the named system owner to
restore the missing least-privilege access. Escalate immediately if an expected
private service is publicly reachable or if development credentials can modify
production resources unexpectedly.
