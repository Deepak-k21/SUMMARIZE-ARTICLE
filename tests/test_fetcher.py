import asyncio

import httpx
import pytest

from app.fetcher import FetchError, extract_article, fetch_article

BODY = " ".join(["This is a sentence of real article content."] * 10)
HTML = f"""
<html><head><title>Fallback title</title><meta property="og:title" content="Real Title"></head>
<body>
  <nav><p>Home About Contact Subscribe now</p></nav>
  <article>
    <h1>Real Title</h1>
    <p>{BODY}</p>
    <p>Second paragraph with <a href="#">a link</a> inside it.</p>
    <script>var tracking = "should not appear";</script>
  </article>
  <footer><p>Copyright notice that is not content</p></footer>
</body></html>
"""


def run(coro):
    return asyncio.run(coro)


def make_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_extract_article_prefers_article_and_drops_noise():
    title, text = extract_article(HTML)
    assert title == "Real Title"
    assert "real article content" in text
    assert "a link inside it" in text
    assert "Subscribe" not in text
    assert "Copyright" not in text
    assert "tracking" not in text


def test_fetch_follows_redirects():
    def handler(request):
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, html=HTML)

    art = run(fetch_article("https://example.com/old", client=make_client(handler), check_host=False))
    assert art.url == "https://example.com/new"
    assert art.title == "Real Title"


def test_fetch_http_error():
    client = make_client(lambda r: httpx.Response(404))
    with pytest.raises(FetchError, match="404"):
        run(fetch_article("https://example.com/", client=client, check_host=False))


def test_fetch_rejects_binary():
    client = make_client(lambda r: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"}))
    with pytest.raises(FetchError, match="Unsupported content type"):
        run(fetch_article("https://example.com/a.pdf", client=client, check_host=False))


def test_fetch_size_limit():
    client = make_client(lambda r: httpx.Response(200, html="<p>" + "x " * 5000 + "</p>"))
    with pytest.raises(FetchError, match="too large"):
        run(fetch_article("https://example.com/", client=client, check_host=False, max_bytes=1000))


def test_fetch_page_without_text():
    client = make_client(lambda r: httpx.Response(200, html="<html><body><p>Hi</p></body></html>"))
    with pytest.raises(FetchError, match="enough readable"):
        run(fetch_article("https://example.com/", client=client, check_host=False))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://localhost:8000/",
    "http://10.0.0.5/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
])
def test_blocks_private_addresses(url):
    with pytest.raises(FetchError, match="private or local"):
        run(fetch_article(url))


def test_blocks_non_http_scheme():
    with pytest.raises(FetchError, match="http"):
        run(fetch_article("file:///etc/passwd"))


def test_redirect_to_private_address_is_blocked():
    client = make_client(lambda r: httpx.Response(302, headers={"location": "http://127.0.0.1/"}))
    # The first hop is public (checked with a stubbed resolver below); the redirect must be re-checked.
    import app.fetcher as f

    async def fake_check(host):
        if host == "127.0.0.1":
            raise FetchError("URLs pointing to private or local network addresses are not allowed.")

    orig = f._assert_public_host
    f._assert_public_host = fake_check
    try:
        with pytest.raises(FetchError, match="private or local"):
            run(fetch_article("https://example.com/", client=client))
    finally:
        f._assert_public_host = orig
