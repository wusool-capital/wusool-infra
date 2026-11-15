// Runs static/embed.js against a stub PostHog and prints what each consent flow did, as JSON.
// Used by test_embed_js.py; not part of the shipped static files.
const fs = require("fs");
const vm = require("vm");

const src = fs.readFileSync(process.argv[2], "utf8");
const tick = (ms) => new Promise((r) => setTimeout(r, ms));

function scenario({ stored, optedOut = false }) {
  const log = [];
  const handlers = [];
  const store = stored ? { wusool_analytics_consent: stored } : {};
  const ph = {
    props: {},
    optedOut,
    init(key, opts) {
      log.push(`init pageview=${opts.capture_pageview} replay_off=${opts.disable_session_recording}`);
      opts.loaded(ph);
      if (!ph.optedOut) log.push(`pageview is_test=${ph.props.is_test}`);
    },
    register(p) {
      Object.assign(ph.props, p);
      log.push("register is_test");
    },
    has_opted_out_capturing: () => ph.optedOut,
    opt_in_capturing(o) {
      ph.optedOut = false;
      log.push(`opt_in captureEventName=${o && o.captureEventName}`);
    },
    opt_out_capturing() {
      ph.optedOut = true;
      log.push("opt_out");
    },
    capture(name, props) {
      log.push(`capture ${name} ${props ? JSON.stringify(props) : ""}`.trim());
    },
  };
  const script = {
    getAttribute: (k) => (k === "data-tool" ? "get-started" : null),
    hasAttribute: (k) => k === "data-modal",
    src: "https://tools.example/embed.js",
  };
  const doc = {
    currentScript: script,
    head: { appendChild: (tag) => setTimeout(() => tag.onload(), 0) },
    createElement: () => ({}),
    querySelectorAll: () => [],
    body: { appendChild() {} },
    addEventListener: (type, fn, capture) => type === "click" && handlers.push({ fn, capture }),
  };
  const ctx = {
    document: doc,
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => (store[k] = v),
      removeItem: (k) => delete store[k],
    },
    URL,
    URLSearchParams,
    Image: function () {},
    setTimeout,
    location: { href: "https://site.example/", search: "" },
    addEventListener() {},
    posthog: ph,
    fetch: () =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ enabled: true, key: "k", host: "h", assets_host: "a", is_test: true }),
      }),
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  const click = (name, text = "Button text") =>
    handlers.forEach((h) =>
      h.fn({ target: { closest: () => (name === null ? null : { getAttribute: () => name, textContent: text }) } })
    );
  return { log, ctx, click, handlers, ph };
}

(async () => {
  const out = {};

  let s = scenario({});
  await tick(30);
  s.click("get-started");
  out.noConsent = s.log;

  s = scenario({ stored: "granted" });
  await tick(30);
  out.accept = s.log;

  s = scenario({ stored: "granted", optedOut: true });
  await tick(30);
  out.storedOptOut = s.log;

  s = scenario({ stored: "granted" });
  await tick(30);
  s.log.length = 0;
  s.ctx.WusoolAnalytics.setConsent(false);
  s.ctx.WusoolAnalytics.setConsent(true);
  s.ctx.WusoolAnalytics.setConsent(true);
  out.withdrawThenReaccept = s.log;

  s = scenario({ stored: "granted" });
  s.click("buyers"); // PostHog still loading: kept, then sent once ready
  s.click("get-started"); // only the last one is kept
  await tick(30);
  s.click("buyers");
  s.click("Bad_Value!");
  s.click(null);
  out.cta = { log: s.log, capturePhase: s.handlers.every((h) => h.capture === true) };

  s = scenario({ stored: "granted" });
  s.click("buyers");
  s.ctx.WusoolAnalytics.setConsent(false); // withdrawn while the library loads
  await tick(30);
  s.click("buyers");
  out.withdrawnWhileLoading = s.log;

  console.log(JSON.stringify(out));
})();
