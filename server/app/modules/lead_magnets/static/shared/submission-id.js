/*
 * One submission id per page load, shared by every tool.
 *
 * This has to be evaluated once per *visit*, not once per click. The server
 * tells a retry apart from a returning person by comparing this value
 * against the one already stored on the colliding `tool_runs` row
 * (`persistence/tool_runs_repository.py::start`): same id means a replay —
 * the identical submission landed twice, a network retry — and a different
 * id means a genuine second visit, which is rejected with a 409.
 *
 * Minting it inside a submit handler breaks that. Buyers and readiness
 * re-enable their submit button on failure, so a visitor retrying after a
 * dropped response would send a *new* id and be told they had already
 * completed a form they never got through. Hoisting it here makes the retry
 * a replay, which is what the distinction was built for. A genuine second
 * visit reloads the page, re-evaluates this file, and still correctly 409s.
 *
 * Loaded as a plain <script src> rather than a module so it also works on
 * the valuation page, where everything else is type="text/babel" — the same
 * reason `valuation/10-data.js` is a plain script.
 */
window.WUSOOL_SUBMISSION_ID =
  window.crypto && crypto.randomUUID
    ? crypto.randomUUID()
    : Date.now() + "-" + Math.random().toString(36).slice(2);
