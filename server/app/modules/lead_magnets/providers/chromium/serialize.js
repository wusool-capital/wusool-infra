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

  // Marks the block boundary nearest `share` of the drawn height; the server cuts the preview there.
  const markGate = (share) => {
    const skip = new Set(['SCRIPT', 'STYLE', 'LINK', 'META', 'BR', 'WBR']);
    const inline = (el) => getComputedStyle(el).display.startsWith('inline');
    const blocks = (el) => [...el.children].filter(
      (c) => !skip.has(c.tagName) && !inline(c) && Math.max(c.getBoundingClientRect().height, c.scrollHeight) > 0);
    const top = (el) => el.getBoundingClientRect().top + window.scrollY;
    // Wrappers fixed at viewport height overflow; their real extent is the content's.
    const bottom = (el) => top(el) + Math.max(el.getBoundingClientRect().height, el.scrollHeight);
    const total = document.body.scrollHeight;
    const target = total * share;
    let root = document.body;
    for (;;) {
      const kids = blocks(root);
      const i = kids.findIndex((k) => bottom(k) >= target);
      if (i < 0) return;
      const kid = kids[i];
      const big = bottom(kid) - top(kid) > total * 0.1;
      if ((kids.length === 1 || big) && blocks(kid).length > 0) { root = kid; continue; }
      const afterKid = target - top(kid) > bottom(kid) - target && i + 1 < kids.length;
      const mark = afterKid ? kids[i + 1] : (i > 0 ? kid : kids[1]);
      if (mark) mark.setAttribute('data-wusool-gate', '');
      return;
    }
  };

  const freeze = (el, props) => {
    const cs = getComputedStyle(el);
    for (const p of props) el.style.setProperty(p, cs.getPropertyValue(p));
  };
  for (const host of [...document.querySelectorAll('*')].filter((e) => e.shadowRoot)) {
    // Only the layout survives; a standalone viewer's "desk" margin would waste the embed's width.
    freeze(host, ['display', 'position', 'box-sizing']);
    for (const child of host.children) {
      // Not the viewer's page gaps, shadows or corners: on the site, pages read as one document.
      freeze(child, ['display', 'position', 'width', 'height', 'container-type', 'overflow', 'box-sizing',
                     'background-color']);
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
  // Readers load this on our tools origin: no code, no embedded third-party frames, no redirects.
  document.querySelectorAll('iframe, frame, frameset, object, embed, applet, base, meta[http-equiv]')
    .forEach((e) => e.remove());
  const urlAttrs = ['href', 'src', 'action', 'formaction', 'xlink:href', 'data', 'srcdoc'];
  for (const el of document.querySelectorAll('*')) {
    for (const attr of [...el.attributes]) {
      const name = attr.name.toLowerCase();
      const value = attr.value.replace(/[\s\u0000-\u001f]/g, '').toLowerCase();
      if (name.startsWith('on') || name === 'srcdoc' ||
          (urlAttrs.includes(name) && /^(javascript|vbscript|data:text\/html)/.test(value))) {
        el.removeAttribute(attr.name);
      }
    }
  }
  markGate(0.25);
  return '<!DOCTYPE html>' + document.documentElement.outerHTML;
}

