async () => {
  // Static snapshot: assets inlined, shadow-DOM styles copied out, scripts removed.
  const toData = async (url) => {
    const blob = await (await fetch(url)).blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(blob);
    });
  };
  const inlineBlobs = async (text) => {
    for (const m of [...text.matchAll(/blob:[^)"'\s]+/g)]) text = text.split(m[0]).join(await toData(m[0]));
    return text;
  };
  for (const el of document.querySelectorAll('[src^="blob:"]')) el.setAttribute('src', await toData(el.src));
  for (const el of document.querySelectorAll('[href^="blob:"]')) el.setAttribute('href', await toData(el.href));
  for (const el of document.querySelectorAll('[style*="blob:"]')) el.setAttribute('style', await inlineBlobs(el.getAttribute('style')));
  for (const st of document.querySelectorAll('style')) st.textContent = await inlineBlobs(st.textContent);

  const freeze = (el, props) => {
    const cs = getComputedStyle(el);
    for (const p of props) el.style.setProperty(p, cs.getPropertyValue(p));
  };
  for (const host of [...document.querySelectorAll('*')].filter((e) => e.shadowRoot)) {
    freeze(host, ['display', 'position', 'padding', 'background-color', 'min-height', 'box-sizing']);
    for (const child of host.children) {
      freeze(child, ['display', 'position', 'width', 'height', 'container-type', 'overflow', 'box-sizing',
                     'background-color', 'border-radius', 'box-shadow', 'margin-top']);
      child.style.marginLeft = child.style.marginRight = 'auto';
    }
  }
  // Hidden copies (a bundle's source template, noscript fallbacks) would leak gated text.
  document.querySelectorAll('x-dc, template, noscript, [hidden]').forEach((e) => e.remove());
  // With scripts gone, ":not(:defined)" hiding would never clear.
  // Guarded: the regex is quadratic on large inlined-font sheets.
  for (const st of document.querySelectorAll('style'))
    if (st.textContent.includes(':not(:defined)'))
      st.textContent = st.textContent.replace(/[^{}]*:not\(:defined\)[^{}]*\{[^}]*\}/g, '');
  document.querySelectorAll('script').forEach((s) => s.remove());
  return '<!DOCTYPE html>' + document.documentElement.outerHTML;
}
