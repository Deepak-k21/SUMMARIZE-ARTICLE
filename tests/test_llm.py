import asyncio
import json

import anthropic
import httpx2
import pytest

from app.llm import ClaudeSummarizer, SummarizerError, build_user_prompt
from app.schemas import SummaryLength, SummaryStyle


def make(stop_reason="end_turn", payload=None, seen=None):
    payload = payload or {"title": "T", "summary": "S", "key_points": ["a", "b"]}

    def handler(request):
        if seen is not None:
            seen["body"] = json.loads(request.content)
            seen["headers"] = dict(request.headers)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    client = anthropic.AsyncAnthropic(
        api_key="test", max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeSummarizer(client, model="claude-opus-5-5", effort="medium")


def summarize(s, include_key_points=True):
    return asyncio.run(s.summarize("Article body here.", SummaryLength.short, SummaryStyle.bullets,
                                   include_key_points, "Page title"))


def test_request_shape():
    seen = {}
    content, model = summarize(make(seen=seen))
    assert content.title == "T" and content.key_points == ["a", "b"]
    assert model == "claude-opus-5-5"
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    user = body["messages"][0]["content"]
    assert "<article>\nArticle body here.\n</article>" in user
    assert "Page title" in user


def test_key_points_dropped_when_disabled():
    content, _ = summarize(make(), include_key_points=False)
    assert content.key_points == []


@pytest.mark.parametrize("reason,match", [("refusal", "declined"), ("max_tokens", "cut off")])
def test_bad_stop_reasons(reason, match):
    with pytest.raises(SummarizerError, match=match):
        summarize(make(stop_reason=reason))


def test_prompt_mentions_options():
    p = build_user_prompt("x", SummaryLength.long, SummaryStyle.executive, True)
    assert "250-400 words" in p
    assert "executive brief" in p
    assert "6-8 key points" in p
    p = build_user_prompt("x", SummaryLength.short, SummaryStyle.simple, False)
    assert "empty list" in p
