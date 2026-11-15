# 0001: Prototype stack

Date: 7 Nov 2026 · Status: accepted

## Context
The first slice is a clickable prototype of all 14 tabs on invented data, to agree on flow and look. Production will call the Python Toolkit (FastAPI) through a typed client. Deal Room v1 already runs on React Router 7.

## Decision
- React Router 7 in SPA mode (`ssr: false`), TypeScript strict, Vite, plain CSS from the DESIGN.md tokens, Inter self-hosted with `@fontsource-variable/inter`.
- React Router is pinned to 7 (npm now defaults to 8) to match Deal Room and CLAUDE.md.
- `@react-router/node` and `isbot` are regular dependencies because the SPA build prerenders `index.html` in Node.
- Fresh scaffold, not a fork of Deal Room. Deal Room components (stage stepper, counterparty table) are ported when the Mandates tab needs them.
- One shared placeholder route serves tabs not yet built. A tab gets its own route file when it is built.
- No test framework yet. Checks are typecheck, build and a browser click-through at 1440px and 390px. Playwright click-count tests come when tabs have real flows.

## Consequences
- The prototype is static files, ready for Cloudflare Workers static assets behind Cloudflare Access. Not deployed yet.
- GitHub branch protection on `main` is not available: the `wusool-capital` org is on the Free plan and the repo is private. Rule until upgraded: no direct pushes to `main`, everything through a pull request.
