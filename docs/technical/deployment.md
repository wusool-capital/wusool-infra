# Deployment

## Infrastructure as code

The AWS environment is defined with **OpenTofu** and applied automatically:
a merge to the main branch builds and deploys the affected parts of the
system.

## Deploy pipeline

1. Build the bot's container image and publish it by an immutable digest.
2. Apply any changed infrastructure, in dependency order.
3. Run any pending database migration before rolling out the new code — a
   failed migration blocks the deploy.
4. Roll the application and poll its health endpoint until it responds
   successfully. A deploy is only considered successful once the health
   check passes — not merely once the infrastructure apply command exits.

There is deliberately no manual approval gate before this pipeline runs —
every step is health-checked automatically, and the blast radius of any one
change is kept small by only touching what actually changed.

## Continuous integration

Every change runs through automated checks before merge: linting, type
checking, the automated test suite, and a check that the database schema
and its migrations agree with each other. Infrastructure changes are
validated and a plan is posted for review before merge.

## Configuration

- Runtime secrets: AWS Secrets Manager.
- Non-secret, per-environment configuration: version-controlled
  infrastructure configuration files.
- A configuration check fails automatically if a setting is introduced in
  code but not documented in the environment template, so configuration
  drift is caught before it reaches production.
