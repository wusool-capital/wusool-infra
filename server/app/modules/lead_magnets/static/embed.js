/*
 * Webflow embed loader. One <script src="/embed.js" data-tool="benchmark">
 * tag per placement — the src is always the same URL, `data-tool` picks
 * which iframe this particular tag builds. `TOOLS` grows one entry per
 * tool as each one ships; cutover and rollback are both one line here.
 */
(function () {
  "use strict";

  var TOOLS = {
    benchmark: "/benchmark/",
    readiness: "/readiness/",
    valuation: "/valuation/",
    buyers: "/buyers/",
  };

  var script = document.currentScript;
  if (!script) return;

  var tool = script.getAttribute("data-tool");
  var src = TOOLS[tool];
  // Unknown tool name: no-op. The path always comes from this map, never
  // from the attribute itself, so a bad value can't be turned into an
  // iframe src.
  if (!src) return;

  // Derived, not hardcoded: the same script works from a dev bare-IP host
  // or the prod hostname without a build-time swap. This is where the
  // child iframe's height messages must come from — not the parent
  // page's own origin, which is Webflow's.
  var toolsOrigin = new URL(script.src, window.location.href).origin;

  var iframe = document.createElement("iframe");
  // Absolute, built from toolsOrigin — the map's paths are root-relative
  // ("/benchmark/"), which a bare assignment would resolve against the
  // *parent* page's own origin (Webflow's), not the tools host. That
  // would silently send the iframe to e.g. wusoolcapital.com/benchmark/
  // instead of the tools server, 404ing on the parent site.
  iframe.src = toolsOrigin + src;
  iframe.title = "Wusool " + tool + " tool";
  iframe.style.border = "0";
  iframe.style.display = "block";
  iframe.style.width = "100%";
  iframe.style.maxWidth = "100%";
  // Viewport-relative placeholder, not a per-tool pixel guess: it is only
  // what shows for the frame or two before shared/height.js reports the
  // real content height, and it is right at every screen size.
  iframe.style.height = "100vh";
  // No `scrolling="no"`. It is what turned a wrong height into *unreachable*
  // content — a lead form that simply ended mid-field with no way to reach
  // the rest. Default scrolling degrades the same failure to an inner
  // scrollbar. With a correct height there is no overflow, so none appears.

  var host = script.parentNode;
  host.insertBefore(iframe, script);
  // Webflow's embed containers ship a fixed `height:100vh` that the iframe
  // then overflows, so everything past one screen was painted over by the
  // footer. The iframe sizes itself; the container must just get out of the
  // way, here rather than in the Designer so it cannot silently regress.
  host.style.height = "auto";

  // Sanity bound only — not a layout value. Stops a pathological page from
  // asking for a million-pixel iframe.
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
    iframe.style.height = Math.min(maxHeight, height) + "px";
  });
})();
