"""Fetch an article from a URL and extract its readable text.

Includes basic SSRF protection: only http(s), only hosts that resolve to public
IP addresses, a bounded number of redirects (each re-checked), a timeout and a
maximum download size.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .text_utils import normalize_whitespace

MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (compatible; ArticleSummarizer/1.0; +https://github.com/Deepak-k21/SUMMARIZE-ARTICLE)"
_NOISE_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "aside", "form",
               "iframe", "svg", "button", "figure", "template"]
_TEXT_TAGS = ["h1", "h2", "h3", "p", "li", "blockquote", "pre"]


class FetchError(Exception):
    """Raised when an article can't be fetched or has no readable text."""


@dataclass
class FetchedArticle:
    url: str
    title: str | None
    text: str


async def _assert_public_host(host: str) -> None:
    if not host:
        raise FetchError("URL has no host.")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Could not resolve host {host!r}.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise FetchError("URLs pointing to private or local network addresses are not allowed.")


def _check_scheme(url: str) -> None:
    if urlparse(url).scheme not in ("http", "https"):
        raise FetchError("Only http:// and https:// URLs are supported.")


def extract_article(html: str) -> tuple[str | None, str]:
    """Return (title, text) extracted from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")

    title = None
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    candidates = soup.find_all("article") or soup.find_all("main") or ([soup.body] if soup.body else [soup])
    root = max(candidates, key=lambda el: len(el.get_text(" ", strip=True)))

    blocks: list[str] = []
    for el in root.find_all(_TEXT_TAGS):
        # Skip elements nested inside another text block we already take.
        if el.find_parent(_TEXT_TAGS):
            continue
        text = el.get_text(" ", strip=True)
        if len(text.split()) >= 3 or el.name.startswith("h"):
            blocks.append(text)

    text = "\n\n".join(blocks) if blocks else root.get_text("\n", strip=True)
    return title, normalize_whitespace(text)


async def fetch_article(
    url: str,
    *,
    timeout: float = 15,
    max_bytes: int = 5_000_000,
    client: httpx.AsyncClient | None = None,
    check_host: bool = True,
) -> FetchedArticle:
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                         headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            _check_scheme(current)
            if check_host:
                await _assert_public_host(urlparse(current).hostname or "")
            try:
                async with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("Redirect without a Location header.")
                        current = urljoin(current, location)
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"The page returned HTTP {resp.status_code}.")
                    ctype = resp.headers.get("content-type", "").lower()
                    if ctype and not any(t in ctype for t in ("html", "text/plain", "xml")):
                        raise FetchError(f"Unsupported content type: {ctype.split(';')[0]}.")
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise FetchError("The page is too large to summarize.")
                    raw = body.decode(resp.encoding or "utf-8", errors="replace")
            except httpx.TimeoutException as exc:
                raise FetchError("Timed out while fetching the page.") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not fetch the page: {exc.__class__.__name__}.") from exc

            if "text/plain" in ctype:
                title, text = None, normalize_whitespace(raw)
            else:
                title, text = extract_article(raw)
            if len(text.split()) < 30:
                raise FetchError("Couldn't find enough readable article text on that page. "
                                 "Try pasting the article text instead.")
            return FetchedArticle(url=current, title=title, text=text)
        raise FetchError("Too many redirects.")
    finally:
        if own_client:
            await client.aclose()
