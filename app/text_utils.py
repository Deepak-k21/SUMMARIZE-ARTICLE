"""Small text helpers: normalisation, word counts, sentence splitting."""

from __future__ import annotations

import re

WORDS_PER_MINUTE = 238  # average adult silent reading speed

_WORD_RE = re.compile(r"\b[\w'’-]+\b", re.UNICODE)
# Split after ., ! or ? (optionally followed by a closing quote/bracket) when the
# next token starts like a new sentence. Avoid splitting common abbreviations.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e",
    "inc", "ltd", "co", "corp", "u.s", "u.k", "no", "fig", "jan", "feb", "mar",
    "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+(?=[\"'“‘(\[]?[A-Z0-9])")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces while keeping paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def reading_time_minutes(text: str) -> float:
    return round(max(word_count(text) / WORDS_PER_MINUTE, 0.1), 1)


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for paragraph in normalize_whitespace(text).split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        pieces = _SENTENCE_END_RE.split(paragraph)
        buffer = ""
        for piece in pieces:
            buffer = f"{buffer} {piece}".strip() if buffer else piece.strip()
            last_word = buffer.rstrip(".!?\"'”’)]").rsplit(" ", 1)[-1].lower()
            if last_word in _ABBREVIATIONS:
                continue  # keep accumulating: the "." belonged to an abbreviation
            sentences.append(buffer)
            buffer = ""
        if buffer:
            sentences.append(buffer)
    return [s for s in sentences if s]
