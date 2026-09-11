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

  // `100vh` inside an iframe resolves to the iframe's own current height —
  // exactly what this file computes the iframe's height *from*. A page
  // section styled `min-height:100vh` (correct on a standalone visit, where
  // the browser window is the real viewport) therefore stretches to match
  // whatever height was last reported, that stretched height gets reported
  // right back, and the two chase each other to an oversized iframe with
  // the actual content centered in a lot of empty space. This class lets a
  // page's own CSS opt those rules out only when actually embedded.
  document.documentElement.classList.add("wusool-embedded");

  function report() {
    window.parent.postMessage(
      { type: "wusool:height", height: document.documentElement.scrollHeight },
      "*"
    );
  }

  new ResizeObserver(report).observe(document.documentElement);
  report();
})();
