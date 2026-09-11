"""Normalisation and key composition for repeat-submitter detection.

Two different jobs, deliberately not one:

`org_key`/`person_key` decide whether a submission belongs to a company or
person we have already seen. The org key is domain **and** name, never
domain alone — one holdco domain legitimately covers several distinct
businesses (a founder running two brands, an advisor submitting for several
clients), and domain alone would merge them permanently. This is also why
marking `organizations.domains` unique in Attio was rejected.

`idempotency_key` decides whether *this exact submission* has already been
processed, and is the only one of the three that carries the tool name.
Putting the tool in the entity key instead would produce one organisation
per tool — the opposite of dedup.

Note what the idempotency key does and does not catch: with
`submission_id` minted once per page load, it collapses a double-click or a
retried POST, but two genuine submissions from the same person get two
rows. That is correct — the org-side query-then-write is what stops the
second one creating a second Attio organisation.
"""

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

# Matched after stripping dots and hyphens, so "l.l.c" and "fz-llc" both
# reduce into this set rather than needing an entry per spelling.
_LEGAL_SUFFIXES = frozenset({"llc", "fzllc", "fzco", "fze", "ltd", "limited", "wll", "dmcc", "inc"})

_WHITESPACE = re.compile(r"\s+")


def normalise_domain(raw: str | None) -> str:
    """Host only, lowercased, `www.` and any trailing dot removed.

    Accepts whatever a form field yields — a bare host, a full URL with a
    path and query, a copied address with a port. Returns `""` for anything
    with no host at all, so a missing domain composes into a key instead of
    blowing up.
    """
    if raw is None:
        return ""
    text = raw.strip()
    if not text:
        return ""
    # No scheme means urlsplit reads the whole string as a path, leaving
    # `hostname` empty; "//" forces it to parse as a network location.
    if "//" not in text:
        text = "//" + text
    host = urlsplit(text).hostname or ""
    host = host.rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def normalise_name(raw: str | None) -> str:
    """Lowercased, whitespace collapsed, trailing legal suffixes removed.

    Strips repeatedly ("Foo Trading L.L.C." carries one, but nothing stops a
    form holding two) and never strips the name away entirely — a company
    whose whole name is "Limited" keeps it.
    """
    if raw is None:
        return ""
    name = _WHITESPACE.sub(" ", raw.strip().lower())
    while True:
        parts = name.split(" ")
        if len(parts) < 2:
            return name
        tail = parts[-1].strip(".,").replace(".", "").replace("-", "")
        if tail not in _LEGAL_SUFFIXES:
            return name
        name = " ".join(parts[:-1]).strip(".,").strip()


def normalise_email(raw: str | None) -> str:
    """Lowercased and trimmed, and nothing else.

    Deliberately no provider-specific cleverness (Gmail dot-stripping,
    `+tag` removal): those change which address we believe a person owns,
    and getting that wrong merges two real people.
    """
    if raw is None:
        return ""
    return raw.strip().lower()


def org_key(*, domain: str | None, name: str | None) -> str:
    return f"{normalise_domain(domain)}|{normalise_name(name)}"


def domain_matches(candidate_domains: Iterable[str], domain: str | None) -> bool:
    """True if `domain` is genuinely one of `candidate_domains`, both
    normalised the same way.

    Used to confirm a name-similarity search hit is actually the same
    organisation, not a similarly-named one — domain alone is never enough
    on its own (a holdco domain can legitimately cover several distinct
    businesses, see the module docstring), so an empty/unmatched `domain`
    is always `False` rather than treated as a wildcard.
    """
    target = normalise_domain(domain)
    if not target:
        return False
    return target in {normalise_domain(d) for d in candidate_domains}


def person_key(email: str | None) -> str:
    return normalise_email(email)


def idempotency_key(*, tool: str, email: str | None, domain: str | None, submission_id: str) -> str:
    return f"{tool}|{person_key(email)}|{normalise_domain(domain)}|{submission_id}"
