({ quietMs, maxMs }) => new Promise((resolve) => {
  // Bundles swap in the real page after `load`; maxMs caps pages that never settle.
  let timer;
  const done = () => { observer.disconnect(); clearTimeout(cap); resolve(true); };
  const observer = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(done, quietMs);
  });
  observer.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  timer = setTimeout(done, quietMs);
  const cap = setTimeout(done, maxMs);
})
