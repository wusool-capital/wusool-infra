/*
 * Tells the parent embed.js how tall this document is, so the iframe can
 * grow and shrink with its content instead of sitting at a fixed height.
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

  var last = 0;

  // Measured from <body>, never <html>. `documentElement.scrollHeight` is the
  // scrolling element's scroll area, which can never report *less* than the
  // iframe's own viewport — so embedded, every page's first report was just
  // the height the iframe already had, and nothing ever grew it. <body> is a
  // plain auto-height block: its box is the real content height, and it
  // shrinks as well as grows. The +1 absorbs sub-pixel rounding so the
  // iframe never shows a 1px scrollbar over nothing.
  function report() {
    var height = document.body.scrollHeight + 1;
    if (height === last) return; // steady state, and breaks any one-way feedback
    last = height;
    window.parent.postMessage({ type: "wusool:height", height: height }, "*");
  }

  // <body> catches content changes; <html> catches the iframe being resized,
  // by us or by the host page reflowing — cheaper than a `resize` listener
  // and it re-measures on the same path. `load` and `document.fonts.ready`
  // would add nothing: both reflow <body>, which the first observer sees.
  var observer = new ResizeObserver(report);
  observer.observe(document.body);
  observer.observe(document.documentElement);
  report();
})();
