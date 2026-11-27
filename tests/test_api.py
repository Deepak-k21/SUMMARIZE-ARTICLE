import anthropic
import httpx2
from fastapi.testclient import TestClient

from app import main
from app.fetcher import FetchedArticle, FetchError
from app.llm import SummarizerError
from app.main import create_app

from .conftest import FakeSummarizer, make_settings


def test_index_served(offline_client):
    r = offline_client.get("/")
    assert r.status_code == 200
    assert "Article Summarizer" in r.text
    assert offline_client.get("/static/app.js").status_code == 200


def test_health_reports_engine(offline_client, llm_client):
    assert offline_client.get("/api/health").json()["engine"] == "extractive"
    body = llm_client.get("/api/health").json()
    assert body == {"status": "ok", "engine": "claude", "model": "claude-opus-5-5"}


def test_summarize_offline(offline_client, article):
    r = offline_client.post("/api/summarize", json={"text": article, "length": "short"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "extractive"
    assert body["summary"]
    assert body["key_points"]
    assert body["stats"]["original_words"] > body["stats"]["summary_words"] > 0
    assert 0 < body["stats"]["compression_ratio"] < 1


def test_summarize_with_claude_passes_options(llm_client, fake_summarizer, article):
    r = llm_client.post("/api/summarize", json={
        "text": article, "length": "long", "style": "bullets", "include_key_points": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "claude"
    assert body["model"] == "claude-opus-5-5"
    assert body["title"] == "Council expands bike lanes"
    assert body["key_points"] == []
    call = fake_summarizer.calls[0]
    assert call["length"].value == "long"
    assert call["style"].value == "bullets"
    assert call["include_key_points"] is False


def test_requires_exactly_one_source(offline_client, article):
    assert offline_client.post("/api/summarize", json={}).status_code == 422
    assert offline_client.post("/api/summarize", json={"text": "   "}).status_code == 422
    r = offline_client.post("/api/summarize", json={"text": article, "url": "https://example.com"})
    assert r.status_code == 422


def test_rejects_invalid_options(offline_client, article):
    r = offline_client.post("/api/summarize", json={"text": article, "length": "huge"})
    assert r.status_code == 422


def test_rejects_too_short(offline_client):
    r = offline_client.post("/api/summarize", json={"text": "Too short to bother."})
    assert r.status_code == 422
    assert "too short" in r.json()["detail"]


def test_rejects_too_long(article):
    client = TestClient(create_app(make_settings(max_input_chars=100)))
    r = client.post("/api/summarize", json={"text": article})
    assert r.status_code == 413


def test_summarizer_error_is_422(article):
    client = TestClient(create_app(make_settings(anthropic_api_key="k"),
                                   summarizer=FakeSummarizer(SummarizerError("declined"))))
    r = client.post("/api/summarize", json={"text": article})
    assert r.status_code == 422
    assert r.json()["detail"] == "declined"


def test_transient_api_error_falls_back_to_extractive(article):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.APIConnectionError(request=req)
    client = TestClient(create_app(make_settings(anthropic_api_key="k"), summarizer=FakeSummarizer(exc)))
    r = client.post("/api/summarize", json={"text": article})
    assert r.status_code == 200
    assert r.json()["engine"] == "extractive"


def test_url_source(monkeypatch, llm_client, fake_summarizer, article):
    async def fake_fetch(url, **kwargs):
        assert url == "https://news.example.com/bikes"
        return FetchedArticle(url=url, title="Bike lanes", text=article)

    monkeypatch.setattr(main, "fetch_article", fake_fetch)
    r = llm_client.post("/api/summarize", json={"url": "https://news.example.com/bikes"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_url"] == "https://news.example.com/bikes"
    assert body["source_title"] == "Bike lanes"
    assert fake_summarizer.calls[0]["source_title"] == "Bike lanes"


def test_url_fetch_error(monkeypatch, offline_client):
    async def fake_fetch(url, **kwargs):
        raise FetchError("nope")

    monkeypatch.setattr(main, "fetch_article", fake_fetch)
    r = offline_client.post("/api/summarize", json={"url": "https://news.example.com/x"})
    assert r.status_code == 422
    assert r.json()["detail"] == "nope"
