/*
 * Loads an exported bundle straight from the Sanity CDN into a sandboxed frame,
 * so its charts and clicks work. Without `allow-same-origin` the frame has an
 * opaque origin: no cookies, no storage, no reach into this page. The CDN serves
 * the file with `script-src 'none'`, which only applies to navigating to it, so
 * it is fetched (the project's CORS origins allow that) and set as `srcdoc`.
 */
(function () {
  "use strict";

  // Runs inside the frame, as text. It reports the frame's height and, given an
  // exhibit id (`<section id>#<figure index>`), hides everything but that figure.
  // The bundle swaps its page in after load, so it keeps polling.
  function isolate(exhibit) {
    function target() {
      var at = exhibit.split("#");
      var section = document.getElementById(at[0]);
      return section ? section.querySelectorAll("figure")[Number(at[1])] || null : null;
    }
    function show(figure) {
      document.body.style.margin = "0";
      for (var node = figure; node && node !== document.body; node = node.parentNode) {
        node.style.padding = "0";
        node.style.margin = "0";
        node.style.maxWidth = "none";
        for (var i = 0; i < node.parentNode.children.length; i++) {
          var sibling = node.parentNode.children[i];
          if (sibling !== node && sibling.tagName !== "SCRIPT") sibling.style.display = "none";
        }
      }
    }
    var last = 0;
    setInterval(function () {
      var height;
      if (exhibit) {
        var figure = target();
        if (!figure) return;
        show(figure);
        height = Math.ceil(figure.getBoundingClientRect().height);
      } else {
        height = document.body ? document.body.scrollHeight : 0;
      }
      if (!height || height === last) return;
      last = height;
      parent.postMessage({ type: "wusool:frame-height", height: height }, "*");
    }, 250);
  }

  var fetched = {};

  // One download per bundle, however many exhibits share it.
  function bundle(url) {
    if (!fetched[url]) {
      fetched[url] = fetch(url).then(function (response) {
        if (!response.ok) throw new Error("bundle " + response.status);
        return response.text();
      });
      fetched[url].catch(function () {
        delete fetched[url]; // a failed load must not stick
      });
    }
    return fetched[url];
  }

  // `exhibit` empty: the whole bundle. The frame's own origin is "null", so the
  // sender is matched by window, never by origin.
  function mount(container, url, exhibit) {
    return bundle(url).then(function (html) {
      var script = "<script>(" + isolate + ")(" + JSON.stringify(exhibit || "") + ");<\/script>";
      var frame = document.createElement("iframe");
      frame.setAttribute("sandbox", "allow-scripts allow-popups allow-popups-to-escape-sandbox");
      frame.style.cssText = "display:block;width:100%;border:0;height:0";
      frame.title = exhibit ? "Interactive chart" : "Interactive report";
      window.addEventListener("message", function (event) {
        var data = event.data;
        if (event.source !== frame.contentWindow || !data || data.type !== "wusool:frame-height") return;
        if (typeof data.height !== "number") return;
        frame.style.height = data.height + "px";
        // First paint of the bundle: callers swap their placeholder for the frame now.
        if (!frame.dataset.ready) {
          frame.dataset.ready = "1";
          frame.dispatchEvent(new Event("ready"));
        }
      });
      frame.srcdoc = script + html;
      container.appendChild(frame);
      return frame;
    });
  }

  window.WusoolInteractive = { mount: mount };
})();
