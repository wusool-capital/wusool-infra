# Documentation style guide

This guide defines the review standard for client-facing Markdown under
`docs/`. Vale checks measurable limits; reviewers remain responsible for
accuracy, usefulness, and information architecture.

## Content budgets

| Content | Target | Vale warning |
| --- | --- | --- |
| Homepage or section index | 150–350 words | More than 350 words for `docs/README.md` |
| Focused user guide | 400–900 words | More than 900 words |
| Technical tool reference | 600–1,200 words | More than 1,200 words |
| Operations runbook | 500–1,000 words | More than 1,000 words |
| Paragraph | One idea, normally 1–4 sentences | More than 100 words |
| Sentence | Prefer 20 words or fewer | More than 25 words |

Word limits are review signals rather than reasons to remove necessary safety
or recovery detail. Split a page when it contains independent user goals or
systems. Keep it intact when the sections form one procedure or reference.

## Page structures

Use the smallest template that covers the reader's task.

### User tool page

1. Purpose and expected outcome.
2. Prerequisites or access.
3. Core tasks, each under a descriptive action heading.
4. Expected result and failure guidance beside each procedure.
5. Limitations, data handling, and troubleshooting links.

### Technical tool page

1. Purpose.
2. Components and architecture.
3. Data flow.
4. Dependencies and configuration.
5. Interfaces with verified examples.
6. Processing rules, failure behavior, and security boundaries.
7. Links to the relevant operations runbooks.

### Operations runbook

1. When to use the runbook.
2. Access and prerequisites.
3. Ordered procedure.
4. Expected outcome and verification evidence.
5. Failure, rollback, and escalation conditions.

## Writing rules

- Use one unique H1 and do not skip heading levels.
- Use sentence case. Start task headings with an action verb and concept
  headings with a noun phrase.
- Put the result or critical condition first.
- Address the reader as “you” in user instructions and use active voice.
- Use numbered lists for sequences and bullets for unordered choices.
- Use synthetic or redacted examples. Never include secrets or client data.
- Mark repository-backed capability separately from live production evidence.
- Link to the canonical page instead of repeating shared operational detail.

## Run the checks

Install Vale 3.17.0 or a compatible Vale 3 release, then run:

```bash
vale CHANGELOG.md docs/README.md docs/SUMMARY.md docs/user-guide docs/technical docs/operations docs/deliverables
```

Warnings require editorial judgment. Errors identify terminology that must be
fixed or explicitly excluded with a narrow Vale annotation.
