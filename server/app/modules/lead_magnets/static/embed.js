/*
 * Webflow embed loader. One <script src="/embed.js" data-tool="benchmark">
 * tag per placement — the src is always the same URL, `data-tool` picks
 * which iframe this particular tag builds. `TOOLS` grows one entry per
 * tool as each one ships; cutover and rollback are both one line here.
 */
(function () {
  "use strict";

  var TOOLS = {
    benchmark: { src: "/benchmark/", fallbackHeight: 1400 },
    readiness: { src: "/readiness/", fallbackHeight: 1000 },
  };

  var script = document.currentScript;
  if (!script) return;

  var tool = script.getAttribute("data-tool");
  var config = TOOLS[tool];
  // Unknown tool name: no-op. `config.src` always comes from this map,
  // never from the attribute itself, so a bad value can't be turned into
  // an iframe src.
  if (!config) return;

  // Derived, not hardcoded: the same script works from a dev bare-IP host
  // or the prod hostname without a build-time swap. This is where the
  // child iframe's height messages must come from — not the parent
  // page's own origin, which is Webflow's.
  var toolsOrigin = new URL(script.src, window.location.href).origin;

  var iframe = document.createElement("iframe");
  iframe.src = config.src;
  iframe.title = "Wusool " + tool + " tool";
  iframe.setAttribute("scrolling", "no");
  iframe.style.border = "0";
  iframe.style.width = "100%";
  iframe.style.display = "block";
  iframe.style.height = config.fallbackHeight + "px";

  script.parentNode.insertBefore(iframe, script);

  var minHeight = config.fallbackHeight / 4;
  var maxHeight = 20000;

  // event.source === iframe.contentWindow is what disambiguates this
  // embed's messages from any other wusool iframe on the same host page —
  // the child cannot know an id the parent assigned after the iframe was
  // created, so there is nothing for it to echo back.
  window.addEventListener("message", function (event) {
    if (event.origin !== toolsOrigin) return;
    if (event.source !== iframe.contentWindow) return;
    var data = event.data;
    if (!data || data.type !== "wusool:height") return;
    var height = Number(data.height);
    if (!isFinite(height) || height <= 0) return;
    height = Math.max(minHeight, Math.min(maxHeight, height));
    iframe.style.height = height + "px";
  });
})();
