const URL_LIKE = /^(https?:\/\/)?(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?([/?#]\S*)?$/i;
const MAX_SHOWN = 36;

/** An https address for text that looks like a web address, or null for anything else. */
function toUrl(text: string) {
  const trimmed = text.trim();
  if (!URL_LIKE.test(trimmed)) return null;
  try {
    return new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
  } catch {
    return null;
  }
}

/** Host and path without the scheme; a long address keeps its host only, and a cut one ends in "…". */
function shortForm(url: URL) {
  const host = url.host.replace(/^www\./, "");
  const path = url.pathname === "/" ? "" : url.pathname;
  const cut = url.search || url.hash ? "…" : "";
  return `${host}${path}`.length <= MAX_SHOWN ? `${host}${path}${cut}` : `${host}/…`;
}

/** A web address as a short link that opens in a new tab; any other text stays as it is. */
export function LinkText({ text }: { text: string }) {
  const url = toUrl(text);
  if (!url) return <>{text}</>;
  return (
    <a href={url.href} target="_blank" rel="noopener noreferrer">
      {shortForm(url)}
    </a>
  );
}
