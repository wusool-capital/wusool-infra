# WusoolScribe desktop update feed

How the desktop app's Tauri auto-updater is fed, who publishes to it, and how
to cut a release. Infra is `infrastructure/terraform/stacks/scribe-updates/`;
the app side lives in `scribe-desktop/frontend`.

## Why a separate stack

The feed is one public S3 + CloudFront distribution, not a per-environment
resource — the axis of variation is the release *channel* (`stable`/`beta`),
which lives in the S3 key prefix, not in a dev/prod split. It follows the same
"applied out of band, no `-var-file`" shape as `stacks/account` and
`stacks/peering`.

## Key layout

```
scribe/<channel>/latest.json
scribe/<channel>/<version>/darwin-aarch64/WusoolScribe_<version>_aarch64.app.tar.gz
scribe/<channel>/<version>/darwin-aarch64/WusoolScribe_<version>_aarch64.app.tar.gz.sig
```

Only `stable` is used today. `beta` is a new prefix with **zero** Terraform
change — the manifest cache behavior and the release role's IAM are already
scoped to `scribe/*`. A second platform (e.g. `darwin-x86_64`, later
`windows-x86_64`) is a new subdirectory, not a rename.

The bucket is private; CloudFront (via Origin Access Control) is the only
reader. The artifacts are downloaded **unauthenticated** by every installed
app — that's by design, not a leak. Integrity comes from Tauri's minisign
signature, verified client-side against the `pubkey` baked into the app in
`tauri.conf.json`, not from access control.

## Release role and the required GitHub Environment

`.github/workflows/scribe-release.yml` assumes
`arn:aws:iam::030179310793:role/wusool-gha-scribe-release`, scoped to
`s3:PutObject`/`GetObject` on `scribe/*` in this bucket and
`cloudfront:CreateInvalidation` on this distribution only — never the
PowerUser `gha_apply` roles, and no `s3:DeleteObject`.

The role's trust condition requires the job to declare
`environment: scribe-release` (see `stacks/scribe-updates/main.tf`'s
`release_trust` policy) — a branch condition doesn't work here, since this is
a public repo and the release workflow runs from arbitrary branches. This is
purely an OIDC-trust label, **not** an approval gate: the environment needs
no protection rules and no required reviewers. `workflow_dispatch` already
requires write access to trigger — that's the actual human gate — and
`job_workflow_ref` further pins the role to this one workflow file.

**One-time manual step, before the first release:** create a `scribe-release`
GitHub Environment (Settings → Environments → New environment, name it
exactly `scribe-release`, add no protection rules). Without it the role is
unassumable and every release run fails at the AssumeRole step — that's the
intended fail-closed behavior, not a bug.

## Cutting a release (macOS aarch64, first pass)

1. In a PR, bump the version in all three places by hand — there is no sync
   script. See
   [`scribe-desktop/docs/VERSIONING.md`](../../scribe-desktop/docs/VERSIONING.md)
   for the exact files/keys and when to bump (ideally in the same PR as the
   feature/fix it ships, not speculatively on every PR).
2. Merge, then run `scribe-release.yml` manually (Actions → Scribe release →
   Run workflow), choosing `channel: stable`. It always builds whatever
   version is currently in `tauri.conf.json` on the branch it's run from.
3. It runs on `macos-14`, builds the app (ad-hoc signed, no Apple Developer
   account — see below), tags the commit `scribe-v<version>` and creates the
   GitHub release from it (DMG = first-install download), then publishes the
   `.app.tar.gz` + `.sig` and a fresh `latest.json` to `scribe/stable/`, and
   invalidates only `/scribe/stable/latest.json`.

A mismatch between `tauri.conf.json`'s version and the other two files fails
the workflow's version-guard step before anything is built — this replaces
an earlier, broken auto-increment scheme that silently shipped binaries
whose internal version never matched the git tag, which would have made the
updater re-offer the same "new" version forever.

To test a channel without touching `stable`, run the workflow with
`channel: beta` instead — it publishes to `scribe/beta/` using the same
`tauri.conf.json` version.

## Signing keys

The Tauri updater's minisign keypair is separate from Apple code-signing.

- Public key: committed in `tauri.conf.json`'s `plugins.updater.pubkey` —
  this is safe and required, it's the client's only means of verifying a
  downloaded payload.
- Private key + passphrase: GitHub secrets `TAURI_SIGNING_PRIVATE_KEY` /
  `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`, backed up in 1Password **and** AWS
  Secrets Manager. Losing it means no installed app can ever be
  auto-updated again; leaking it means whoever also controls the feed can
  ship code to every user.

## The one-time gap

Everyone on `0.4.0` today runs a build with no updater plugin registered at
all. They cannot be auto-updated *to* the first updater-enabled release —
that one has to be installed from the DMG by hand (still via the existing
`xattr -d com.apple.quarantine` workaround — that's unrelated to this feed
and unaffected by it). Auto-update works from that release onward.

## No Apple Developer account: ad-hoc signing, and what it costs

There is no Developer ID Application certificate, so every build here is
**ad-hoc signed** (`tauri.conf.json`'s `signingIdentity: "-"`) and never
notarized — the same as the current `0.4.0` build. Two consequences, one
harmless and one not:

- **Gatekeeper's download-quarantine prompt is unaffected either way.** The
  updater downloads and installs a release entirely through the app's own
  Rust HTTP client, never through a quarantine-setting API (browser, Mail,
  AirDrop), so `com.apple.quarantine` is never set on the swapped `.app` —
  signed or not, notarized or not. It behaves identically to today.
- **macOS TCC permission grants (microphone, screen recording) will not
  reliably survive an update.** TCC keys a grant to the app's stable
  Developer ID Team Identifier when one exists; an ad-hoc signature has no
  certificate, so macOS instead pins the grant to a hash of that specific
  binary. Every rebuild changes that hash, so the OS is expected to revoke
  both grants and re-prompt the user after most releases. **Accepted
  tradeoff** — not something to "fix" here without paying for a Developer ID
  account (~$99/year), which would make the Team Identifier stable across
  builds instead.

If a Developer ID account is added later: restore the Apple cert
import/notarization steps this workflow's history shows were removed, set
`APPLE_CERTIFICATE`/`APPLE_CERTIFICATE_PASSWORD`/`KEYCHAIN_PASSWORD`/
`APPLE_ID`/`APPLE_PASSWORD`/`APPLE_TEAM_ID` as repo secrets, and change
`signingIdentity` in `tauri.conf.json` from `"-"` to the real identity. At
that point `codesign -dv --verbose=4 /Applications/WusoolScribe.app | grep
TeamIdentifier` before/after a release becomes a meaningful check that
permissions will carry over; today it isn't, since there's no Team
Identifier to compare.
