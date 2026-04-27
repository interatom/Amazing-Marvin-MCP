"""Free-text query matching for search_docs.

Mirrors the semantics of the Marvin client's free-text search bar:

- The query is split into bare tokens (whitespace-separated) and quoted phrases.
- Quoted phrases that contain any uppercase letter are matched case-sensitively
  ("Q1" must appear literally as "Q1"). All-lowercase quoted phrases and bare
  tokens are matched case-insensitively.
- Diacritics are stripped on both query and haystacks before comparison, so
  "cafe" matches "café" and "naive" matches "naïve".
- Multiple terms are combined with implicit AND: every token / phrase must
  appear in at least one haystack for the document to match.

Used by the search_docs MCP tool to filter docs after a Mango pre-filter.
"""

from __future__ import annotations

import re
import unicodedata

_PHRASE_OR_TOKEN = re.compile(r'"([^"]+)"|(\S+)')


def _strip_diacritics(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def tokenize_query(query: str) -> tuple[list[str], list[str]]:
    """Split a query into (case_insensitive_terms, case_sensitive_phrases).

    Bare tokens and all-lowercase quoted phrases land in the case-insensitive
    list (lowercased, diacritic-stripped). Quoted phrases with any uppercase
    letter land in the case-sensitive list (diacritic-stripped only).
    """
    ci: list[str] = []
    cs: list[str] = []
    stripped = _strip_diacritics(query)
    for m in _PHRASE_OR_TOKEN.finditer(stripped):
        phrase, bare = m.group(1), m.group(2)
        if phrase is not None:
            if any(c.isupper() for c in phrase):
                cs.append(phrase)
            else:
                ci.append(phrase.lower())
        elif bare:
            ci.append(bare.lower())
    return ci, cs


def matches(query: str, haystacks: list[str | None]) -> bool:
    """Return True if every term in `query` appears in at least one haystack.

    Empty / whitespace-only queries return False. None / empty haystacks are
    skipped silently.
    """
    ci, cs = tokenize_query(query)
    if not ci and not cs:
        return False

    cleaned = [_strip_diacritics(h) for h in haystacks if h]
    lowered = [h.lower() for h in cleaned]

    for term in ci:
        if not any(term in h for h in lowered):
            return False
    for phrase in cs:
        if not any(phrase in h for h in cleaned):
            return False
    return True


def longest_token(query: str) -> str | None:
    """Return the longest case-insensitive token from the query, or None.

    Used as a Mango pre-filter to narrow the candidate set server-side before
    running the full matcher in Python. The longest token tends to be the most
    distinctive, so it discards the most non-matching docs early.
    """
    ci, cs = tokenize_query(query)
    candidates = ci + [p.lower() for p in cs]
    if not candidates:
        return None
    return max(candidates, key=len)
