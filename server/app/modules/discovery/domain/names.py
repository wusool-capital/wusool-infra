"""Decides whether a discovered lead's name is close enough to an existing
organization's to flag it as a possible duplicate for a human.

The database search is deliberately loose (typo-tolerant trigram similarity
over 0.3), which lets a single shared generic word through ("Intelligence"
alone put two unrelated AI firms next to "FLOW Intelligence"). This is the
stricter second look: generic words are ignored, and what's left must overlap.
"""

import re

# Words that say what a company is or how it's incorporated, not which one.
GENERIC_WORDS: frozenset[str] = frozenset(
    {
        # What the company does.
        "advanced", "ai", "artificial", "capital", "global", "group", "intelligence",
        "international", "services", "solutions", "systems", "tech", "technologies",
        "technology",
        # How it's incorporated.
        "ab", "ag", "as", "bv", "co", "company", "corp", "corporation", "fze", "fzco",
        "gmbh", "holding", "holdings", "inc", "kg", "kgaa", "limited", "llc", "llp", "lp",
        "ltd", "nv", "oy", "plc", "pty", "sa", "sarl", "spa", "srl", "ug",
        # Connectors.
        "and", "for", "of", "the",
    }
)  # fmt: skip

# Trigram overlap (as in Postgres `pg_trgm`) the distinctive words must reach.
MIN_SIMILARITY = 0.5
# A single shared word only settles it alone when it is this long; "Atlas" or
# "Noor" sit inside too many unrelated company names.
MIN_SOLE_WORD_LENGTH = 7


def _words(name: str) -> list[str]:
    return re.findall(r"\w+", name.casefold())


def _trigrams(words: list[str]) -> set[str]:
    grams: set[str] = set()
    for word in words:
        padded = f"  {word} "
        grams.update(padded[i : i + 3] for i in range(len(padded) - 2))
    return grams


def _similarity(a: list[str], b: list[str]) -> float:
    grams_a, grams_b = _trigrams(a), _trigrams(b)
    union = grams_a | grams_b
    return len(grams_a & grams_b) / len(union) if union else 0.0


def names_similar(lead_name: str, org_name: str) -> bool:
    all_a, all_b = _words(lead_name), _words(org_name)
    # One-letter leftovers ("O" in "O AI Company") identify nothing.
    key_a = [w for w in all_a if w not in GENERIC_WORDS and len(w) > 1]
    key_b = [w for w in all_b if w not in GENERIC_WORDS and len(w) > 1]
    if not key_a or not key_b:
        # Nothing distinctive on one side: compare the full names instead.
        return _similarity(all_a, all_b) >= MIN_SIMILARITY
    set_a, set_b = set(key_a), set(key_b)
    # "Savvytec" vs "Savvytec Trading": one name's distinctive words sit inside the other's.
    smaller = set_a if len(set_a) <= len(set_b) else set_b
    if (set_a <= set_b or set_b <= set_a) and (
        len(smaller) > 1 or len(next(iter(smaller))) >= MIN_SOLE_WORD_LENGTH
    ):
        return True
    return _similarity(key_a, key_b) >= MIN_SIMILARITY
