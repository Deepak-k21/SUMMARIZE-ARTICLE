from app.extractive import summarize_extractive
from app.schemas import SummaryLength, SummaryStyle
from app.text_utils import normalize_whitespace, split_sentences, word_count


def test_split_sentences_handles_abbreviations():
    text = "Dr. Smith arrived at 5 p.m. on Monday. She met Mr. Jones! Was it planned? Nobody knows."
    assert split_sentences(text) == [
        "Dr. Smith arrived at 5 p.m. on Monday.",
        "She met Mr. Jones!",
        "Was it planned?",
        "Nobody knows.",
    ]


def test_normalize_whitespace_keeps_paragraphs():
    assert normalize_whitespace("a   b\r\n\r\n\r\n\r\nc\t d ") == "a b\n\nc d"


def test_word_count():
    assert word_count("It's a well-known fact, isn't it?") == 6


def test_length_controls_summary_size(article):
    short = summarize_extractive(article, SummaryLength.short)
    long = summarize_extractive(article, SummaryLength.long)
    assert word_count(short.summary) < word_count(long.summary)


def test_sentences_keep_original_order(article):
    sentences = split_sentences(article)
    result = summarize_extractive(article, SummaryLength.medium)
    positions = [sentences.index(s) for s in split_sentences(result.summary)]
    assert positions == sorted(positions)


def test_bullets_style(article):
    result = summarize_extractive(article, style=SummaryStyle.bullets)
    assert all(line.startswith("- ") for line in result.summary.splitlines())


def test_tldr_style(article):
    result = summarize_extractive(article, SummaryLength.short, SummaryStyle.tldr)
    assert result.summary.startswith("TL;DR: ")
    assert len(split_sentences(result.summary.removeprefix("TL;DR: "))) == 1


def test_key_points_toggle(article):
    assert summarize_extractive(article, include_key_points=False).key_points == []
    assert len(summarize_extractive(article, SummaryLength.short).key_points) == 3


def test_title_from_heading(article):
    result = summarize_extractive("Council Expands Bike Lanes\n\n" + article)
    assert result.title == "Council Expands Bike Lanes"


def test_empty_text():
    assert summarize_extractive("").summary == ""


def test_heading_not_used_as_sentence(article):
    result = summarize_extractive("Council Expands Bike Lanes\n\n" + article, include_key_points=True)
    assert "Council Expands Bike Lanes" not in result.summary
    assert all("Council Expands Bike Lanes" not in p for p in result.key_points)
