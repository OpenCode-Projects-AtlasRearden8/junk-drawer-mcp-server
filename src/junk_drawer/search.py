"""Search over the junk drawer: plain words, forgiving matches.

Built for the "do we have an HDMI adapter?" moment - type what you
remember and get the best candidates first. Naming is loose on purpose;
the scoring leans on name and tags rather than exact phrases.
"""

from __future__ import annotations

import re
from typing import Any

# Weights for each searchable field. Name and tags carry the most signal.
_WEIGHTS = {
    "name": 3.0,
    "tags": 2.5,
    "kind": 2.0,
    "description": 1.5,
    "container": 1.0,
    "room": 0.5,
}

# "All one word vs two" and small plurals: token-level, no heavy stemming.
_STOPWORDS = {
    "a",
    "an",
    "any",
    "around",
    "do",
    "for",
    "have",
    "here",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "the",
    "there",
    "was",
    "we",
    "were",
    "where",
    "wheres",
    "you",
}

def tokenize(query: str) -> list[str]:
    """Lowercase tokens, minus the scaffolding words of a question."""
    rough = re.findall(r"[a-z0-9\-\+#\.]+", query.lower())
    out: list[str] = []
    for tok in rough:
        if tok in _STOPWORDS:
            continue
        out.append(tok)
    return out


def _variants(tok: str) -> set[str]:
    """The token plus a light plural/singular variant."""
    v = {tok}
    if len(tok) > 3 and tok.endswith("s"):
        v.add(tok[:-1])
        if tok.endswith("es"):
            v.add(tok[:-2])
    elif len(tok) > 2:
        v.add(tok + "s")
    return v


def _field_text(item: dict[str, Any], field: str) -> str:
    if field == "tags":
        return " ".join(item.get("tags", []))
    return str(item.get(field, ""))


def matches(item: dict[str, Any], tokens: list[str]) -> tuple[bool, float]:
    """Boolean hit plus a score; every token must land somewhere."""
    if item.get("status", "live") != "live":
        return False, 0.0
    score = 0.0
    for tok in tokens:
        want = _variants(tok)
        hit = 0.0
        for field, weight in _WEIGHTS.items():
            words = re.findall(r"[a-z0-9\-\+#\.]+", _field_text(item, field))
            for word in words:
                if word in want:
                    hit = max(hit, weight)
                elif any(w in word or word in w for w in want) and len(word) > 2:
                    hit = max(hit, weight * 0.5)
        if hit == 0.0:
            return False, 0.0
        score += hit
    score += min(len(item.get("moves", [])), 3) * 0.05  # well-moved items first
    return True, round(score, 4)


def search(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Ranked live items matching all query tokens; empty query -> none."""
    tokens = tokenize(query)
    if not tokens:
        return []
    hits = []
    for item in items:
        ok, score = matches(item, tokens)
        if ok:
            hits.append((score, item["id"], item))
    hits.sort(key=lambda t: (-t[0], t[1]))
    return [h[2] for h in hits]
