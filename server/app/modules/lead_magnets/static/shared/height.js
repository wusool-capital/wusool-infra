/*
 * Tells the parent embed.js how tall this document is, so the iframe can
 * grow/shrink instead of sitting at embed.js's fixed fallbackHeight.
 * targetOrigin "*": a viewport height is not a secret, this document cannot
 * know the Webflow host's origin, and CSP frame-ancestors (api/static.py)
 * is the actual access control.
 */
(function () {
  "use strict";
  if (window.parent === window) return; // not embedded, nothing to report

  function report() {
    window.parent.postMessage(
      { type: "wusool:height", height: document.documentElement.scrollHeight },
      "*"
    );
  }

  new ResizeObserver(report).observe(document.documentElement);
  report();
})();
