# Bumping the app version

There is no sync script — the version lives in three files, and all three
must agree exactly (same string, e.g. `0.4.1`) or `scribe-release.yml`'s
version-guard step fails the release before anything is built.

| File | Key |
|---|---|
| `frontend/src-tauri/tauri.conf.json` | top-level `"version"` — this one is the source of truth; the release workflow reads it to decide what to build and tag |
| `frontend/package.json` | top-level `"version"` |
| `frontend/src-tauri/Cargo.toml` | `[package]` block's `version` |
| `Cargo.lock` (workspace root) | the `wusoolscribe` package's `version` entry — regenerate this by running `cargo check` (or any cargo command) from `scribe-desktop/` after editing `Cargo.toml`, rather than hand-editing it |

## When to bump it

Bump it in the **same PR as the feature/fix**, if that PR is meant to ship as
a user-visible update. Don't bump it for internal-only changes (CI, docs,
refactors with no user-facing effect) — every bump becomes a real release
the next time someone runs `scribe-release.yml`, so an unnecessary bump just
means an update with nothing in it.

If several PRs land on `dev` before you're ready to cut a release, bump the
version once, in its own small PR, right before running the workflow —
don't bump it per-PR speculatively.

## After merging the bump

Run `scribe-release.yml` manually (Actions → Scribe release → Run workflow).
It builds whatever version is currently committed — it does not choose or
increment a version itself. See
[`docs/dev/SCRIBE_UPDATE_FEED.md`](../../docs/dev/SCRIBE_UPDATE_FEED.md) in
the repo root for the full release runbook.
