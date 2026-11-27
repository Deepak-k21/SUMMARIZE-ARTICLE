"""FastAPI application: JSON API + static web UI."""

from __future__ import annotations

import logging
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .extractive import summarize_extractive
from .fetcher import FetchError, fetch_article
from .llm import ClaudeSummarizer, SummarizerError
from .schemas import SummarizeRequest, SummarizeResponse, SummaryStats
from .text_utils import normalize_whitespace, reading_time_minutes, word_count

logger = logging.getLogger("summarizer")
STATIC_DIR = Path(__file__).parent / "static"
MIN_WORDS = 40


def create_app(settings: Settings | None = None, summarizer: ClaudeSummarizer | None = None) -> FastAPI:
    settings = settings or get_settings()
    if summarizer is None and settings.llm_enabled:
        summarizer = ClaudeSummarizer(
            anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
            model=settings.model,
            effort=settings.effort,
        )

    app = FastAPI(
        title="Article Summarizer",
        version="1.0.0",
        description="Summarize articles (pasted text or a URL) with Claude, with an offline fallback.",
    )

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "engine": "claude" if summarizer else "extractive",
            "model": settings.model if summarizer else None,
        }

    @app.post("/api/summarize", response_model=SummarizeResponse)
    async def summarize(req: SummarizeRequest) -> SummarizeResponse:
        source_url = source_title = None
        if req.url:
            try:
                article = await fetch_article(
                    str(req.url),
                    timeout=settings.fetch_timeout_seconds,
                    max_bytes=settings.fetch_max_bytes,
                )
            except FetchError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            text, source_url, source_title = article.text, article.url, article.title
        else:
            text = normalize_whitespace(req.text or "")

        if word_count(text) < MIN_WORDS:
            raise HTTPException(
                status_code=422,
                detail=f"The article is too short to summarize (need at least {MIN_WORDS} words).",
            )
        if len(text) > settings.max_input_chars:
            raise HTTPException(
                status_code=413,
                detail=f"The article is too long ({len(text):,} characters; the limit is "
                       f"{settings.max_input_chars:,}).",
            )

        engine, model = "extractive", None
        content = None
        if summarizer:
            try:
                content, model = await summarizer.summarize(
                    text, req.length, req.style, req.include_key_points, source_title
                )
                engine = "claude"
            except SummarizerError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except anthropic.AuthenticationError as exc:
                logger.error("Anthropic authentication failed: %s", exc)
                raise HTTPException(status_code=502, detail="The server's Anthropic API key is invalid.") from exc
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
                # Transient upstream problem: degrade gracefully instead of failing the request.
                logger.warning("Claude unavailable (%s); falling back to extractive summary.", exc)
            except anthropic.APIStatusError as exc:
                logger.error("Anthropic API error: %s", exc)
                raise HTTPException(status_code=502, detail="The summarization service returned an error.") from exc

        if content is None:
            content = summarize_extractive(text, req.length, req.style, req.include_key_points)

        original_words = word_count(text)
        summary_words = word_count(content.summary)
        return SummarizeResponse(
            **content.model_dump(),
            engine=engine,
            model=model,
            source_url=source_url,
            source_title=source_title,
            stats=SummaryStats(
                original_words=original_words,
                summary_words=summary_words,
                compression_ratio=round(summary_words / original_words, 3) if original_words else 0.0,
                reading_time_minutes=reading_time_minutes(text),
            ),
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
