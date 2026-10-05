(quietMs) => new Promise((resolve) => {
  // Resolves once the DOM has gone `quietMs` without a mutation. A bundle's
  // loader swaps in the real document some time after `load`, so `load` alone is too early.
  let timer;
  const done = () => { observer.disconnect(); resolve(true); };
  const observer = new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(done, quietMs); });
  observer.observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  timer = setTimeout(done, quietMs);
})
