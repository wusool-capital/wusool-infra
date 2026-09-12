# n8n

n8n is Wusool Capital's self-hosted workflow-automation platform. It has its
own account and web interface. Changing an active workflow can affect live
business processes.

## Sign in

1. Open the intended environment:
   - Development: `https://n8n-dev.wusoolcapital.com/`
   - Production: `https://n8n.wusoolcapital.com/`
2. Sign in with your invited account. If you have none, ask an administrator
   to invite you from **Settings → Users**.

**Expected result:** you reach that environment's workflow list. Development
and production are separate; a workflow or credential in one does not prove
it exists in the other.

Password reset and invitation email depend on the configured mail service.
If no message arrives, check spam and ask the administrator to confirm your
address. Some recipients may require verification while email remains in
sandbox mode.

## Inspect or run a workflow

1. Confirm the environment in the browser address.
2. Read the workflow description and recent executions before changing or
   manually running it.
3. Prefer development for manual tests when the workflow and test credentials
   are available there.
4. Open **Executions** and inspect each node's output after the run.

**Expected result:** a successful execution shows completed nodes and output.
A failure identifies the node and error that stopped or partially completed
the run.

## Example: investigate a failed execution

Suppose an active workflow stops at **Create CRM record**.

1. Open the failed execution without retrying it.
2. Inspect that node's input, output, credential reference, and error.
3. Check whether the target CRM already contains the intended record.
4. Correct the cause in development or with the workflow owner.
5. Retry only after confirming that completed nodes will not duplicate work.

**Expected result:** the retry completes once, or the owner receives the
execution ID and exact failing node for escalation. Never treat a red final
node as proof that earlier nodes made no external changes.

## Change a workflow safely

- Confirm the owner and expected inputs and outputs.
- Check credentials, webhooks, schedules, and external systems it uses.
- Keep production data out of development tests unless approved by the owner.
- Save, test, and review the execution before activating a schedule or
  webhook.
- Do not assume every feature in public n8n documentation is configured here.

Use the [official n8n documentation](https://docs.n8n.io/) for the editor and
nodes. For a Wusool workflow, credentials, or business behavior, contact its
owner.

If a run fails, record the environment, workflow, execution ID, failed node,
error, and time. Check whether it affected an external system before retrying;
a retry can duplicate messages or records.
