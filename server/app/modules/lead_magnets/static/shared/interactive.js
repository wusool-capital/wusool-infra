// Mounts an exported bundle in a sandboxed frame, so its charts work without reaching the page.
(function () {
  "use strict";

  // iOS Safari 18 ignores some images' "height: 100%" and draws them at full natural height, so pin it in px.
  // Where the browser gets it right the heights already match and nothing changes.
  function pinImages(root) {
    Array.prototype.forEach.call(root.querySelectorAll("img"), function (img) {
      var box = img.parentElement;
      if (img.style.height !== "100%" || !box || !img.complete) return;
      var style = getComputedStyle(box);
      var room = box.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
      if (room > 0 && Math.abs(img.offsetHeight - room) > 1) img.style.height = room + "px";
    });
  }

  // Runs inside the frame as text: reports height and hides all but the exhibit's figure.
  function isolate(exhibit, site, pinImages) {
    // Sites refuse to load in a frame, so a link followed in place shows a blank page.
    document.addEventListener("click", function (event) {
      var link = event.target.closest && event.target.closest("a[href]");
      var href = link && link.getAttribute("href");
      if (!href || href.charAt(0) === "#") return;
      if (site) link.href = new URL(href, site).href;
      link.target = "_blank";
    }, true);
    // A whole page tells the site when it leaves the top, so the site's header can change with it.
    if (site) {
      var atTop = null;
      var reportTop = function () {
        var top = window.scrollY < 8;
        if (top === atTop) return;
        atTop = top;
        parent.postMessage({ type: "wusool:frame-top", top: top }, "*");
      };
      window.addEventListener("scroll", reportTop, { passive: true });
    }
    // The frame resolves "#id" against the parent's URL, so following it loads the parent page inside the frame.
    document.addEventListener("click", function (event) {
      var link = event.target.closest && event.target.closest('a[href^="#"]');
      if (!link || event.defaultPrevented) return;
      event.preventDefault();
      var id = decodeURIComponent(link.getAttribute("href").slice(1));
      var target = id && (document.getElementById(id) || document.getElementsByName(id)[0]);
      if (!target) return;
      // Not scrollIntoView: that also scrolls the parent page, sliding the frame under the site header.
      var margin = parseFloat(getComputedStyle(target).scrollMarginTop) || 0;
      window.scrollTo({ top: target.getBoundingClientRect().top + window.scrollY - margin });
    });
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
        // The figure's own children are the chart; only its ancestors' other children go.
        if (node === figure) return;
        Array.prototype.forEach.call(node.children, function (child) {
          if (keep.indexOf(child) < 0 && child.tagName !== "STYLE" && child.tagName !== "SCRIPT") {
            child.style.setProperty("display", "none", "important");
          }
        });
      });
      document.documentElement.style.setProperty("overflow", "hidden", "important");
      document.body.style.setProperty("margin", "0", "important");
    }
    // Content wider than the frame shrinks to fit it; content that already fits stays 1:1.
    // A transform, not CSS zoom: iOS Safari mis-sizes images under zoom. It lays out as on desktop, then shrinks.
    var scale = 1;
    function fitWidth() {
      var root = document.documentElement;
      var body = document.body;
      ["transform", "transform-origin", "width", "box-sizing", "margin-bottom"].forEach(function (name) {
        body.style.removeProperty(name);
      });
      scale = 1;
      var style = getComputedStyle(body);
      var sides = parseFloat(style.marginLeft) + parseFloat(style.marginRight);
      var natural = root.scrollWidth - sides;
      var room = root.clientWidth - sides;
      if (natural <= room) return;
      scale = room / natural;
      body.style.boxSizing = "border-box";
      body.style.width = natural + "px";
      body.style.transformOrigin = "0 0";
      body.style.transform = "scale(" + scale + ")";
      // A transform keeps the full-size layout box, so pull up the empty space it leaves below.
      body.style.marginBottom = parseFloat(style.marginBottom) - body.offsetHeight * (1 - scale) + "px";
    }
    function refit() {
      // Deferred: resizing the observed body inside its callback raises a loop error the bundle reports.
      requestAnimationFrame(function () {
        if (document.body) fitWidth();
      });
    }
    var fitted = null;
    var resized = new ResizeObserver(refit);
    // The body's width is pinned while shrunk, so only the window reports a rotation.
    window.addEventListener("resize", refit);
    var root = null;
    var last = 0;
    // Polls because the bundle swaps its page in after load.
    setInterval(function () {
      var height;
      // Again on each swapped-in document: iOS enlarges text in a shrunk page, overflowing fixed-height pages.
      if (document.documentElement !== root) {
        root = document.documentElement;
        root.style.setProperty("-webkit-text-size-adjust", "100%");
        root.style.setProperty("text-size-adjust", "100%");
      }
      pinImages(document);
      if (exhibit) {
        var figure = target();
        if (!figure) return;
        show(figure);
        // The bottom edge, not the height: the figure can sit a few px below the frame's top.
        height = Math.ceil(figure.getBoundingClientRect().bottom);
      } else if (document.body) {
        if (document.body !== fitted) {
          fitted = document.body;
          resized.observe(fitted);
          // A report sizes the frame, so its own "html,body{height:100%}" would only let the frame grow.
          if (!site) {
            [document.documentElement, fitted].forEach(function (node) {
              node.style.setProperty("height", "auto", "important");
              node.style.setProperty("min-height", "0", "important");
            });
          }
        }
        height = Math.ceil(document.body.scrollHeight * scale);
      }
      if (!height || height === last) return;
      last = height;
      parent.postMessage({ type: "wusool:frame-height", height: height }, "*");
    }, 250);
  }

  var LOAD_TIMEOUT_MS = 30000;
  // Same ceiling embed.js puts on a report: the 71-page one is about 118,000px.
  var MAX_FRAME_HEIGHT = 200000;
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

  // Empty `exhibit` mounts the whole bundle. Senders match by window: the frame's origin is "null".
  // `page` ({height, site}) mounts it as the whole page: a fixed height it scrolls in, so sticky parts stay put.
  function mount(container, url, exhibit, page) {
    return bundle(url).then(function (html) {
      var id = JSON.stringify(exhibit || "").replace(/</g, "\\u003c");
      var site = JSON.stringify(page ? page.site : "").replace(/</g, "\\u003c");
      var script = "<script>(" + isolate + ")(" + id + "," + site + "," + pinImages + ");<\/script>";
      // Before </head>, never ahead of the doctype: that would drop the bundle into quirks mode.
      var doc = html.indexOf("</head>") < 0 ? script + html : html.replace("</head>", function () { return script + "</head>"; });
      var frame = document.createElement("iframe");
      frame.setAttribute("sandbox", "allow-scripts allow-popups allow-popups-to-escape-sandbox");
      // Not 0: a bundle first laid out in a zero-height viewport stays collapsed once resized.
      frame.style.cssText = "display:block;width:100%;border:0;height:600px";
      frame.title = exhibit ? "Interactive chart" : page ? "Article" : "Interactive report";
      // Collapsed until it draws, so a bundle that never does leaves no gap.
      var holder = document.createElement("div");
      holder.style.cssText = "position:relative;height:0;overflow:hidden";
      window.addEventListener("message", function (event) {
        var data = event.data;
        if (event.source !== frame.contentWindow || !data || data.type !== "wusool:frame-height") return;
        if (typeof data.height !== "number" || !isFinite(data.height) || data.height <= 0) return;
        frame.style.height = page ? page.height : Math.min(data.height, MAX_FRAME_HEIGHT) + "px";
        // First paint of the bundle: callers swap their placeholder for the frame now.
        if (!frame.dataset.ready) {
          frame.dataset.ready = "1";
          holder.style.cssText = "";
          frame.dispatchEvent(new Event("ready"));
        }
      });
      frame.srcdoc = doc;
      holder.appendChild(frame);
      container.appendChild(holder);
      setTimeout(function () {
        if (!frame.dataset.ready) holder.remove();
      }, LOAD_TIMEOUT_MS);
      return frame;
    });
  }

  window.WusoolInteractive = { mount: mount, pinImages: pinImages };
})();
