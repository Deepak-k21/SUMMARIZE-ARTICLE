"""Offline extractive summarizer.

Used when no ANTHROPIC_API_KEY is configured (or as a fallback when the API is
unreachable). It scores sentences by normalised term frequency with a position
bonus, then returns the top sentences in their original order. It is not as
good as an LLM summary, but it is deterministic, fast and dependency-free.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .schemas import SummaryContent, SummaryLength, SummaryStyle
from .text_utils import split_sentences, words

STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are aren't as at be because been
    before being below between both but by can can't cannot could couldn't did didn't do does
    doesn't doing don't down during each few for from further had hadn't has hasn't have haven't
    having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll
    i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor
    not of off on once only or other ought our ours ourselves out over own said same say says
    she she'd she'll she's should shouldn't so some such than that that's the their theirs them
    themselves then there there's these they they'd they'll they're they've this those through
    to too under until up very was wasn't we we'd we'll we're we've were weren't what what's
    when when's where where's which while who who's whom why why's will with won't would
    wouldn't you you'd you'll you're you've your yours yourself yourselves just like one two
    new also may might us get got make made many much even well back
    """.split()
)

# Fraction of sentences to keep, with lower/upper bounds, per requested length.
_LENGTH_RULES: dict[SummaryLength, tuple[float, int, int]] = {
    SummaryLength.short: (0.10, 2, 3),
    SummaryLength.medium: (0.20, 3, 6),
    SummaryLength.long: (0.35, 5, 12),
}


def _tokens(sentence: str) -> list[str]:
    return [w.lower() for w in words(sentence) if w.lower() not in STOPWORDS and len(w) > 2]


def _score_sentences(sentences: list[str]) -> list[float]:
    freq = Counter(t for s in sentences for t in set(_tokens(s)))
    if not freq:
        return [0.0] * len(sentences)
    top = max(freq.values())
    n = len(sentences)
    scores = []
    for idx, sentence in enumerate(sentences):
        toks = _tokens(sentence)
        if not toks:
            scores.append(0.0)
            continue
        base = sum(freq[t] / top for t in toks) / math.sqrt(len(toks))
        position_bonus = 1.0 + 0.5 * (1 - idx / max(n - 1, 1)) if n > 1 else 1.0
        if idx == 0:
            position_bonus += 0.25  # ledes usually carry the main point
        scores.append(base * position_bonus)
    return scores


def _pick(sentences: list[str], scores: list[float], k: int) -> list[str]:
    ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:k]
    return [sentences[i] for i in sorted(ranked)]


def _split_heading(text: str) -> tuple[str | None, str]:
    """If the text starts with a headline-like line, return (heading, rest)."""
    first_line, _, rest = text.strip().partition("\n")
    first_line = first_line.strip()
    if rest.strip() and 3 <= len(first_line.split()) <= 14 and not re.search(r"[.!?:;,]$", first_line):
        return first_line, rest
    return None, text


def _make_title(heading: str | None, sentences: list[str]) -> str:
    if heading:
        return heading
    keywords = [w for w, _ in Counter(t for s in sentences for t in _tokens(s)).most_common(4)]
    return " · ".join(k.capitalize() for k in keywords) or "Summary"


def summarize_extractive(
    text: str,
    length: SummaryLength = SummaryLength.medium,
    style: SummaryStyle = SummaryStyle.paragraph,
    include_key_points: bool = True,
) -> SummaryContent:
    heading, body = _split_heading(text)
    sentences = split_sentences(body)
    if not sentences:
        return SummaryContent(title="Summary", summary="", key_points=[])

    ratio, lo, hi = _LENGTH_RULES[length]
    k = max(lo, min(hi, round(len(sentences) * ratio)))
    if style is SummaryStyle.tldr:
        k = 1 if length is SummaryLength.short else min(k, 2)
    k = min(k, len(sentences))

    scores = _score_sentences(sentences)
    chosen = _pick(sentences, scores, k)

    if style is SummaryStyle.bullets:
        summary = "\n".join(f"- {s}" for s in chosen)
    elif style is SummaryStyle.tldr:
        summary = "TL;DR: " + " ".join(chosen)
    else:
        summary = " ".join(chosen)

    key_points: list[str] = []
    if include_key_points:
        n_points = {SummaryLength.short: 3, SummaryLength.medium: 5, SummaryLength.long: 7}[length]
        key_points = _pick(sentences, scores, min(n_points, len(sentences)))

    return SummaryContent(title=_make_title(heading, sentences), summary=summary, key_points=key_points)
