"""Request / response models shared by the API and the summarizer engines."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SummaryLength(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"


class SummaryStyle(str, Enum):
    paragraph = "paragraph"
    bullets = "bullets"
    tldr = "tldr"
    executive = "executive"
    simple = "simple"


class SummarizeRequest(BaseModel):
    text: str | None = Field(default=None, description="Raw article text to summarize.")
    url: HttpUrl | None = Field(default=None, description="Public article URL to fetch and summarize.")
    length: SummaryLength = SummaryLength.medium
    style: SummaryStyle = SummaryStyle.paragraph
    include_key_points: bool = True

    @model_validator(mode="after")
    def _exactly_one_source(self) -> SummarizeRequest:
        has_text = bool(self.text and self.text.strip())
        if has_text == bool(self.url):
            raise ValueError("Provide either 'text' or 'url' (exactly one).")
        return self


class SummaryContent(BaseModel):
    """What a summarizer engine produces."""

    title: str = Field(description="A short, informative title for the article.")
    summary: str = Field(description="The summary, in the requested length and style.")
    key_points: list[str] = Field(default_factory=list, description="The most important takeaways.")


class SummaryStats(BaseModel):
    original_words: int
    summary_words: int
    compression_ratio: float = Field(description="summary_words / original_words")
    reading_time_minutes: float = Field(description="Estimated reading time of the original article.")


class SummarizeResponse(SummaryContent):
    engine: str = Field(description="'claude' or 'extractive'")
    model: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    stats: SummaryStats
