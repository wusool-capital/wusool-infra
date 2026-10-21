/*
 * Consent-gated PostHog tracking, shared by every tool page. Nothing is
 * fetched or loaded until the visitor has accepted tracking; before that,
 * events wait in memory and are dropped if consent never comes.
 *
 * Consent arrives from the parent page (embed.js relays the Webflow banner's
 * choice) or, on a direct visit, from localStorage on this origin. Only
 * names in ALLOWED_PROPS ever leave the page, and no form field is read.
 */
(function () {
  "use strict";

  // The only properties an event may carry; anything else is dropped in track().
  var ALLOWED_PROPS = ["tool", "step", "language", "source", "submission_id"];
  // Kept in step with the server's submit routes by test_static_contract.py.
  var SUBMIT_PATHS = [
    "/benchmark",
    "/buyer/apply",
    "/get-started",
    "/readiness/score",
    "/submit-lead",
  ];
  var REPORT_UNLOCK = /^\/reports\/[a-z0-9-]{1,256}\/unlock$/;
  var TOOLS = {
    benchmark: "benchmark",
    readiness: "readiness",
    valuation: "valuation",
    buyers: "buyer_network",
    "get-started": "get_started",
    report: "insights_report",
  };
  var PARENT_ORIGINS = ["https://www.wusoolcapital.com", "https://wusoolcapital.com"];
  var CONSENT_KEY = "wusool_analytics_consent";
  var UTM_KEY = "wusool_utm";
  var UTM_FIELDS = ["source", "medium", "campaign", "term", "content"];
  var QUEUE_MAX = 50;
  // Longest we wait for the parent's answer before treating the visitor as not consenting.
  var PARENT_WAIT_MS = 3000;

  var framed = window.parent !== window;
  var tool = TOOLS[location.pathname.split("/").filter(Boolean)[0]] || null;
  // null = undecided (events queue), true = tracking accepted, false = not.
  var consent = null;
  var ready = false;
  var loading = false;
  var queue = [];
  var started = false;
  var done = false;
  var abandoned = false;
  var lastStep = null;
  var parentUtm = null;
  var nativeFetch = window.fetch;

  function storage(method, key, val) {
    try {
      return method === "get"
        ? localStorage.getItem(key)
        : method === "set"
          ? localStorage.setItem(key, val)
          : localStorage.removeItem(key);
    } catch (e) {
      return null;
    }
  }

  function cleanUtm(raw) {
    if (!raw || typeof raw !== "object") return null;
    var out = {};
    var any = false;
    for (var i = 0; i < UTM_FIELDS.length; i++) {
      var v = raw[UTM_FIELDS[i]];
      out[UTM_FIELDS[i]] = typeof v === "string" && v.trim() ? v.trim().slice(0, 200) : null;
      if (out[UTM_FIELDS[i]]) any = true;
    }
    return any ? out : null;
  }

  function utmFromUrl() {
    var params = new URLSearchParams(location.search);
    var raw = {};
    for (var i = 0; i < UTM_FIELDS.length; i++) raw[UTM_FIELDS[i]] = params.get("utm_" + UTM_FIELDS[i]);
    return cleanUtm(raw);
  }

  // Sent to our own server with a submit, so it needs no consent; only remembering it does.
  function utm() {
    var current = parentUtm || utmFromUrl();
    if (consent !== true) return current;
    var first = null;
    try {
      first = cleanUtm(JSON.parse(storage("get", UTM_KEY)));
    } catch (e) {}
    if (first) return first;
    if (current) storage("set", UTM_KEY, JSON.stringify(current));
    return current;
  }

  function language() {
    return (navigator.language || "").slice(0, 2).toLowerCase();
  }

  function visitorId() {
    if (consent !== true || !ready || !window.posthog) return null;
    try {
      return window.posthog.get_distinct_id() || null;
    } catch (e) {
      return null;
    }
  }

  function context() {
    return { visitor_id: visitorId(), consent: consent === true, utm: utm() };
  }

  function send(name, props, options) {
    try {
      window.posthog.capture(name, props, options);
    } catch (e) {}
  }

  function track(name, props, options) {
    if (consent === false) return;
    var out = { tool: tool, language: language(), submission_id: window.WUSOOL_SUBMISSION_ID };
    for (var i = 0; i < ALLOWED_PROPS.length; i++) {
      var key = ALLOWED_PROPS[i];
      if (props && Object.prototype.hasOwnProperty.call(props, key) && props[key] != null) {
        out[key] = String(props[key]).slice(0, 100);
      }
    }
    if (consent === true && ready) return send(name, out, options);
    if (queue.length < QUEUE_MAX) queue.push([name, out, options]);
  }

  function flush() {
    var pending = queue;
    queue = [];
    for (var i = 0; i < pending.length; i++) send(pending[i][0], pending[i][1], pending[i][2]);
  }

  function load() {
    if (loading || consent !== true) return;
    loading = true;
    nativeFetch
      .call(window, "/analytics/config", { credentials: "same-origin" })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (cfg) {
        if (!cfg || !cfg.enabled) {
          queue = [];
          return;
        }
        var s = document.createElement("script");
        s.async = true;
        s.src = cfg.assets_host + "/static/array.js";
        s.onload = function () {
          window.posthog.init(cfg.key, {
            api_host: cfg.host,
            autocapture: false,
            capture_pageview: false,
            capture_pageleave: false,
            disable_session_recording: true,
            persistence: "localStorage+cookie",
            cross_subdomain_cookie: true,
            person_profiles: "identified_only",
          });
          window.posthog.register({ is_test: cfg.is_test });
          ready = true;
          if (consent === true) flush();
        };
        document.head.appendChild(s);
      })
      .catch(function () {
        queue = [];
      });
  }

  function setConsent(granted) {
    var next = granted === true;
    if (next === consent) return;
    consent = next;
    if (next) {
      // Remembers first-touch UTM now, not at submit, so a visitor who leaves first still counts.
      utm();
      if (ready) window.posthog.opt_in_capturing();
      else load();
      if (ready) flush();
      return;
    }
    queue = [];
    storage("remove", UTM_KEY);
    if (ready) window.posthog.opt_out_capturing();
  }

  // A step is counted once per page load: back buttons re-run the same transitions.
  var seenSteps = {};
  function step(name) {
    var label = String(name).slice(0, 100);
    if (seenSteps[label]) return;
    seenSteps[label] = true;
    lastStep = label;
    track("tool_step_completed", { step: label });
  }

  function completed() {
    if (done) return;
    done = true;
    track("tool_completed", { step: lastStep });
  }

  // Adds the analytics block to lead submits so the server can keep UTM and link the visitor.
  function prepare(input, init) {
    if (typeof input !== "string" || !init || typeof init.body !== "string") return null;
    if (String(init.method || "GET").toUpperCase() !== "POST") return null;
    var url = new URL(input, location.href);
    if (url.origin !== location.origin) return null;
    var path = url.pathname;
    if (SUBMIT_PATHS.indexOf(path) < 0 && !REPORT_UNLOCK.test(path)) return null;
    var body = JSON.parse(init.body);
    if (!body || typeof body !== "object" || Array.isArray(body)) return null;
    body.analytics = context();
    var next = {};
    for (var k in init) if (Object.prototype.hasOwnProperty.call(init, k)) next[k] = init[k];
    next.body = JSON.stringify(body);
    return { path: path, init: next };
  }

  if (nativeFetch) {
    window.fetch = function (input, init) {
      var args = arguments;
      var path = null;
      try {
        var prepared = prepare(input, init);
        if (prepared) {
          args = [input, prepared.init];
          path = prepared.path;
        }
      } catch (e) {}
      var pending = nativeFetch.apply(this, args);
      if (path && SUBMIT_PATHS.indexOf(path) >= 0) {
        pending.then(
          function (r) {
            if (r && r.ok) completed();
          },
          function () {}
        );
      }
      return pending;
    };
  }

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.type !== "wusool-analytics") return;
    if (event.source !== window.parent) return;
    if (event.origin !== location.origin && PARENT_ORIGINS.indexOf(event.origin) < 0) return;
    parentUtm = cleanUtm(data.utm);
    setConsent(data.consent === true);
  });

  function onFirstTouch(event) {
    if (started) return;
    var el = event.target && event.target.closest ? event.target.closest("input,select,textarea,button,label") : null;
    if (!el) return;
    started = true;
    track("tool_started");
  }
  ["input", "change", "click"].forEach(function (type) {
    document.addEventListener(type, onFirstTouch, true);
  });

  document.addEventListener(
    "click",
    function (event) {
      var link = event.target && event.target.closest ? event.target.closest('a[href*="calendar.app.google"]') : null;
      if (link) track("book_call_clicked", { source: "tool" });
    },
    true
  );

  // sendBeacon survives the page closing, where an ordinary request would be cancelled.
  window.addEventListener("pagehide", function () {
    if (!started || done || abandoned) return;
    abandoned = true;
    track("tool_abandoned", { step: lastStep }, { transport: "sendBeacon" });
  });

  if (storage("get", CONSENT_KEY) === "granted") setConsent(true);
  else if (framed) {
    window.parent.postMessage({ type: "wusool-analytics-ready" }, "*");
    setTimeout(function () {
      if (consent === null) setConsent(false);
    }, PARENT_WAIT_MS);
  } else consent = false;

  track("tool_opened");

  window.WusoolAnalytics = {
    track: track,
    step: step,
    completed: completed,
    context: context,
    visitorId: visitorId,
  };
})();
