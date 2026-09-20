# Postmortems

Create a postmortem when a production problem has been resolved. Postmortems
are factual records of what happened, what was done, and how recurrence will be
prevented.

## Location and naming

Create a new file under `docs/postmortems/`. Do not overwrite
an existing postmortem.

Use a descriptive filename:

```text
docs/postmortems/YYYY-MM-DD-short-incident-name.md
```

Create the directory only when the first postmortem is needed; do not add an
empty placeholder directory.

## Required format

```markdown
# Postmortem: <incident name>

## Summary

What happened and how it was resolved.

## Impact

Affected users, environments, services, and duration.

## Severity

P0 / P1 / P2 / P3, with justification.

## Detection

How the issue was discovered and which alerts or checks fired.

## Timeline

Use UTC timestamps for the incident, diagnosis, actions, recovery, and validation.

## Symptoms and Diagnosis

Verified errors, logs, health checks, and the confirmed root cause.

## Resolution

The exact steps taken, including commands or deployment/run references that were used.

## Validation and Rollback

Evidence that service recovered and whether a rollback was used or remains unavailable.

## Follow-Up Actions

Concrete owners, actions, and tracking references.

## References

Relevant runbook, deployment, alarm, or issue links.
```

## Safety rules

- Redact passwords, tokens, API keys, private keys, database credentials,
  customer data, and secret values.
- Mark missing evidence, ownership, or recovery mechanisms as `NOT VERIFIED`.
- Record commands only when they were actually used and are valid for this
  repository; do not turn guesses into procedures.
- Update the relevant runbook when the incident reveals stale, incomplete, or
  unsafe instructions. Add a new project-specific runbook only for a real
  uncovered failure mode.
- Do not create a resolution postmortem for an unresolved or merely planned
  issue; document its blocker and escalation state instead.
