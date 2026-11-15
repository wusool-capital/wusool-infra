# Release the Engine

The Engine has two copies. A merge to `dev` deploys engine-dev, which reads the
dev Toolkit. A merge to `prod` deploys the live Engine at
`engine.wusoolcapital.com`, which reads the production Toolkit. Both use the
`Deploy engine` workflow.

To bring up the live Engine for the first time:

1. Apply the `engine-frontend` stack by hand. It creates the `wusool-engine-prod`
   Access application and widens the deploy role. Note the `access_aud_prod` output.
2. Add `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_ENGINE_AUD` to the `env` of
   `/wusool/prod/toolkit`. The audience is `access_aud_prod`.
3. Create the `engine-prod` GitHub environment, then set the repository variable
   `ENGINE_PROD_ACCESS_APPLIED` to `true`.
4. Promote `dev` to `prod`. `Deploy prod` rolls the Toolkit, which reads the new
   secret, and `Deploy engine` publishes the Worker.
5. Check three things. The hostname redirects to the Access sign-in.
   `/api/v1/me` on the Toolkit answers 401 without a token. An advisor can sign
   in and see the Buyers page.

**Roll back** the Toolkit as described in
[Deployment and rollback](deployment-and-rollback.md). To take the Engine offline,
set `ENGINE_PROD_ACCESS_APPLIED` to `false`, which stops new deploys, and remove
the route from the Cloudflare dashboard.
