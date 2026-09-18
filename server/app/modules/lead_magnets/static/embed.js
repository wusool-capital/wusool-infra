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
    "get-started": "/get-started/",
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

  // Modal mode is an early return, deliberately placed above every line of
  // the inline path below. A tag without `data-modal` — which is all four of
  // the original tools — executes exactly the statements it always has, in
  // the same order. Nothing below this block was touched.
  //
  // The Get Started CTA opens an overlay rather than sitting inline: it
  // replaces a Tally popup, so the host page keeps its own layout and its
  // URL never changes. `wusool:height` is deliberately NOT wired up here —
  // a modal is a fixed-size overlay that scrolls internally, so there is no
  // iframe to grow.
  if (script.hasAttribute("data-modal")) {
    buildModal(script.getAttribute("data-trigger"), toolsOrigin + src, tool);
    return;
  }

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

  // ---------------------------------------------------------------------
  // Modal mode. Function declaration, so it is hoisted above the early
  // return that calls it while still living below the inline path it must
  // not disturb.
  // ---------------------------------------------------------------------
  function buildModal(triggerSelector, url, toolName) {
    // No trigger, nothing to open — a no-op rather than an overlay that can
    // never be dismissed, matching how an unknown `data-tool` is handled.
    if (!triggerSelector) return;
    var triggers = document.querySelectorAll(triggerSelector);
    if (!triggers.length) return;

    var overlay = document.createElement("div");
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Wusool " + toolName);
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:2147483647;background:rgba(8,12,40,.6);" +
      "display:none;align-items:center;justify-content:center;padding:16px";

    var panel = document.createElement("div");
    panel.style.cssText =
      "position:relative;width:min(680px,92vw);height:min(90vh,900px);" +
      "background:#fff;border-radius:12px;overflow:hidden;" +
      "box-shadow:0 24px 64px rgba(0,0,0,.32)";

    var close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    close.innerHTML = "&times;";
    close.style.cssText =
      "position:absolute;top:8px;right:10px;z-index:1;width:32px;height:32px;" +
      "border:none;border-radius:50%;background:rgba(8,12,40,.06);color:#0b1240;" +
      "font-size:22px;line-height:1;cursor:pointer";

    // Created on first open, not now: a visitor who never clicks the CTA
    // never loads the form and never runs its scripts.
    var frame = null;
    var lastFocused = null;

    function focusable() {
      return [close].concat(
        [].slice.call(panel.querySelectorAll("iframe"))
      );
    }

    function onKeydown(event) {
      if (event.key === "Escape") {
        closeModal();
        return;
      }
      if (event.key !== "Tab") return;
      // Only the close button and the iframe are tabbable in the parent
      // document; the form's own fields live in the child and the browser
      // keeps focus inside it once there.
      var items = focusable();
      var first = items[0];
      var last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function openModal(event) {
      if (event) event.preventDefault();
      lastFocused = document.activeElement;
      if (!frame) {
        frame = document.createElement("iframe");
        frame.src = url;
        frame.title = "Wusool " + toolName + " form";
        frame.style.cssText = "width:100%;height:100%;border:0;display:block";
        panel.appendChild(frame);
      }
      overlay.hidden = false;
      overlay.style.display = "flex";
      document.body.style.overflow = "hidden";
      document.addEventListener("keydown", onKeydown);
      close.focus();
    }

    function closeModal() {
      overlay.hidden = true;
      overlay.style.display = "none";
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKeydown);
      // The iframe is kept, not destroyed: reopening should not discard a
      // half-filled form, and must not re-request the page.
      if (lastFocused && lastFocused.focus) lastFocused.focus();
    }

    close.addEventListener("click", closeModal);
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) closeModal();
    });

    panel.appendChild(close);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    for (var i = 0; i < triggers.length; i++) {
      triggers[i].addEventListener("click", openModal);
    }
  }
})();
