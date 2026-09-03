---
name: project-documentation
description: Create and maintain concise, professional project documentation for client handover and ongoing development. Use after implementing meaningful features or when preparing a project delivery.
---

# Project Documentation Skill

You are responsible for keeping the project's documentation accurate, concise, readable, and useful.

The goal is NOT to document everything.

The goal is to document the information a client or developer actually needs.

## Core Principles

1. Documentation must reflect the actual implementation.
2. Prefer clarity over completeness.
3. Prefer short sections over long explanations.
4. Never generate documentation merely to increase coverage.
5. Do not repeat the same information across multiple documents.
6. Do not document obvious implementation details.
7. Do not invent behavior, requirements, or architecture.
8. Every document should be skimmable in under a few minutes.

---

# Documentation Structure

Use the existing documentation structure when available.

If creating it from scratch:

```text
docs/
├── user-guide/
├── technical/
└── handover/
CHANGELOG.md
````

## User Guide

For non-technical users.

Focus on:

* What the user can do
* How to do it
* Important rules or limitations

Use numbered steps for workflows.

Avoid:

* Source code
* Internal architecture
* Database implementation
* Developer terminology

## Technical Documentation

For developers maintaining the project.

Cover only important information:

* Architecture
* Key components
* APIs
* Database/data model
* Authentication/authorization
* External services
* Deployment
* Configuration
* Important business rules
* AI/LLM architecture where applicable

Do not document every function, class, endpoint, or file.

## Handover Documentation

For the client at delivery.

Keep it executive and practical.

Include:

* Project overview
* Delivered features
* Important URLs/environments
* Third-party services
* Deployment/ownership information
* Known limitations
* Outstanding items
* Support/handover notes

The handover should describe the **current delivered state**, not the entire development history.

## Changelog

Record meaningful changes only.

Use short entries grouped by:

* Added
* Changed
* Fixed
* Removed

Do not turn the changelog into a development diary.

---

# Length & Readability Rules

These rules are mandatory.

### General

* Prefer 1–3 paragraphs per section.
* Prefer bullets over prose.
* Prefer tables for comparisons or structured information.
* Prefer numbered lists for procedures.
* Keep paragraphs under 4 sentences.
* Use headings frequently.
* Avoid walls of text.
* Avoid repeating information already documented elsewhere.

### Target Length

Use these as approximate targets, not requirements:

| Document                |               Target |
| ----------------------- | -------------------: |
| User Guide              |           5–15 pages |
| Technical Documentation |           5–20 pages |
| Handover                |            3–8 pages |
| Changelog entry         | 1–3 lines per change |

If the project is simple, documentation should be significantly shorter.

If the project is complex, add detail only where it provides real value.

**Never add content just to reach a target length.**

### Executive Summary Rule

A client should be able to understand:

> What was built, what was delivered, and what they need to know

without reading the entire documentation.

Put the most important information first.

---

# Feature Documentation Workflow

After implementing a meaningful feature:

1. Inspect the implementation and git diff.
2. Determine what actually changed.
3. Identify affected documentation.
4. Update only the relevant sections.
5. Update the changelog if appropriate.
6. Check for outdated or contradictory documentation.
7. Keep the resulting documentation concise.

Do NOT regenerate entire documents when only one section changed.

---

# Documentation Quality Check

Before finishing, review the generated documentation as if you were the client.

Ask:

* Can I quickly find what I need?
* Is this understandable without technical knowledge?
* Are the important points obvious?
* Is anything unnecessarily verbose?
* Is the same information repeated?
* Are there sections that provide little value?
* Could a paragraph become 3 bullets?
* Could a long explanation become a table?
* Does every section justify its existence?

If documentation feels bloated, shorten it.

If a section can be removed without losing useful information, remove it.

---

# Accuracy Rules

The source of truth is:

```text
Implementation → Tests → Documentation
```

Never invent:

* Features
* API behavior
* Configuration
* Business rules
* Integrations
* Security behavior
* AI behavior

If something cannot be verified from the project, explicitly mark it as unknown or ask for clarification.

---

# GitBook Compatibility

Documentation may be published through GitBook.

Write Markdown that works well in GitBook.

Use:

* Clear headings
* Short sections
* Tables
* Bullet lists
* Numbered workflows
* Code blocks only when necessary
* Links between related documentation

Avoid excessive nesting.

Avoid huge pages.

If a page becomes difficult to scan, split it into logical pages.

---

# Final Standard

The documentation should feel like it was produced by a professional software consultancy, not generated by an AI.

A good document is:

**Accurate + concise + structured + skimmable + useful**

Not:

**Long + exhaustive + repetitive + impressive-looking**

When in doubt, write less.