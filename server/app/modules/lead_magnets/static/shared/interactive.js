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
      // Siblings are hidden with !important because the bundle's own styles also set display.
      var keep = [];
      for (var node = figure; node; node = node.parentElement) keep.push(node);
      keep.forEach(function (node) {
        if (node !== figure && node !== document.documentElement) {
          node.style.setProperty("padding", "0", "important");
          node.style.setProperty("margin", "0", "important");
          node.style.setProperty("max-width", "none", "important");
        }
        Array.prototype.forEach.call(node.children, function (child) {
          if (keep.indexOf(child) < 0 && child.tagName !== "STYLE" && child.tagName !== "SCRIPT") {
            child.style.setProperty("display", "none", "important");
          }
        });
      });
      document.documentElement.style.setProperty("overflow", "hidden", "important");
      document.body.style.setProperty("margin", "0", "important");
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
      // Before </head>, never ahead of the doctype: that would drop the bundle into quirks mode.
      var doc = html.indexOf("</head>") < 0 ? script + html : html.replace("</head>", function () { return script + "</head>"; });
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
      frame.srcdoc = doc;
      container.appendChild(frame);
      return frame;
    });
  }

  window.WusoolInteractive = { mount: mount };
})();
