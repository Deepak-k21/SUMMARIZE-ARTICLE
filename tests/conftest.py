import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import SummaryContent

ARTICLE = (
    "The city council approved a new plan on Tuesday to expand bike lanes across downtown. "
    "The plan adds 40 kilometres of protected lanes over the next three years. "
    "Officials said the project will cost about 12 million dollars, funded mostly by a state grant. "
    "Local businesses were divided, with some worried about losing parking spaces. "
    "Cycling advocates praised the decision and said it would make streets safer for everyone. "
    "A study last year found that traffic injuries fell by a third on streets with protected lanes. "
    "Construction on the first phase is expected to begin in the spring. "
    "The council will review progress at the end of each year and publish a public report."
)


def make_settings(**overrides) -> Settings:
    base = dict(
        anthropic_api_key=None,
        model="claude-opus-5-5",
        effort="medium",
        max_input_chars=200_000,
        fetch_timeout_seconds=5,
        fetch_max_bytes=1_000_000,
    )
    base.update(overrides)
    return Settings(**base)


class FakeSummarizer:
    def __init__(self, exc: Exception | None = None):
        self.calls = []
        self.exc = exc

    async def summarize(self, text, length, style, include_key_points, source_title=None):
        self.calls.append(dict(text=text, length=length, style=style,
                               include_key_points=include_key_points, source_title=source_title))
        if self.exc:
            raise self.exc
        return (
            SummaryContent(title="Council expands bike lanes",
                           summary="The council approved 40 km of protected bike lanes.",
                           key_points=["40 km of lanes", "$12M cost"] if include_key_points else []),
            "claude-opus-5-5",
        )


@pytest.fixture
def article() -> str:
    return ARTICLE


@pytest.fixture
def offline_client() -> TestClient:
    return TestClient(create_app(make_settings()))


@pytest.fixture
def fake_summarizer() -> FakeSummarizer:
    return FakeSummarizer()


@pytest.fixture
def llm_client(fake_summarizer) -> TestClient:
    return TestClient(create_app(make_settings(anthropic_api_key="test"), summarizer=fake_summarizer))
