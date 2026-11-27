# 📝 Article Summarizer

Paste an article (or a link to one) and get a clear, faithful summary with key points, in the length and style you choose.

- **AI summaries with Claude**: abstractive summaries from Anthropic's Claude (`claude-opus-5-5` by default), returned as structured JSON (title, summary, key points).
- **Works from text or a URL**: URLs are fetched server-side and the readable article text is extracted (nav bars, footers and scripts are stripped).
- **Adjustable output**: three lengths (short / medium / long) and five styles (paragraph, bullet points, TL;DR, executive brief, explain simply), with key points on or off.
- **Offline mode**: with no API key, an extractive engine picks the most important sentences from the article, so the app still works (and the test suite needs no network).
- **Clean, responsive web UI** with dark mode, copy to clipboard, download as Markdown, word count and reading-time stats.
- **Safe by default**: URL fetching blocks private and local network addresses (SSRF protection), limits redirects, size and time; article text is passed to the model as data, not instructions.
- **Tested**: 40+ pytest tests, ruff linting and GitHub Actions CI.

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/Deepak-k21/SUMMARIZE-ARTICLE.git
cd SUMMARIZE-ARTICLE

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...  # Windows (PowerShell): $env:ANTHROPIC_API_KEY="sk-ant-..."
uvicorn app.main:app --reload
```

Open <http://localhost:8000>. Get an API key from the [Claude Console](https://platform.claude.com/). Without a key the app starts in **offline mode** (badge in the top-right corner) and uses the extractive engine.

### Docker

```bash
docker build -t article-summarizer .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... article-summarizer
```

## Configuration

All settings are environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables Claude summaries. Unset means offline extractive mode. |
| `SUMMARIZER_MODEL` | `claude-opus-5-5` | Claude model ID. |
| `SUMMARIZER_EFFORT` | `medium` | Reasoning effort: `low`, `medium`, `high`, `xhigh`, `max`. |
| `SUMMARIZER_MAX_INPUT_CHARS` | `200000` | Longest article accepted. |
| `SUMMARIZER_FETCH_TIMEOUT` | `15` | Seconds to wait when fetching a URL. |
| `SUMMARIZER_FETCH_MAX_BYTES` | `5000000` | Largest page downloaded when fetching a URL. |

## API

Interactive docs are at `/docs` while the server runs.

### `POST /api/summarize`

Send exactly one of `text` or `url`:

```bash
curl -X POST http://localhost:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{
        "url": "https://example.com/some-article",
        "length": "medium",
        "style": "bullets",
        "include_key_points": true
      }'
```

| Field | Values | Default |
|---|---|---|
| `text` | article text | |
| `url` | public `http(s)` URL | |
| `length` | `short`, `medium`, `long` | `medium` |
| `style` | `paragraph`, `bullets`, `tldr`, `executive`, `simple` | `paragraph` |
| `include_key_points` | `true` / `false` | `true` |

Response:

```json
{
  "title": "Council expands downtown bike lanes",
  "summary": "- The city council approved 40 km of protected bike lanes…",
  "key_points": ["40 km of protected lanes over three years", "…"],
  "engine": "claude",
  "model": "claude-opus-5-5",
  "source_url": "https://example.com/some-article",
  "source_title": "Council expands bike lanes",
  "stats": {
    "original_words": 1240,
    "summary_words": 132,
    "compression_ratio": 0.106,
    "reading_time_minutes": 5.2
  }
}
```

Errors return `{"detail": "..."}` with status `422` (bad input, page couldn't be read, too short), `413` (too long) or `502` (upstream API problem). If Claude is temporarily unreachable or rate limited, the API falls back to the extractive engine and reports `"engine": "extractive"`.

### `GET /api/health`

Returns `{"status": "ok", "engine": "claude" | "extractive", "model": ...}`.

## Project structure

```
app/
  main.py         FastAPI app: routes, validation, error handling, static UI
  llm.py          Claude summarizer (prompting + structured output)
  extractive.py   Offline extractive summarizer (fallback)
  fetcher.py      URL fetching, SSRF protection, article text extraction
  schemas.py      Request/response models
  text_utils.py   Sentence splitting, word counts, reading time
  config.py       Environment-based settings
  static/         Web UI (HTML, CSS, vanilla JS; no build step)
tests/            pytest suite (no network or API key needed)
```

## How it works

1. **Input**: pasted text is normalised, or the URL is fetched (each redirect hop is re-checked against private address ranges) and the main article body is extracted with BeautifulSoup.
2. **Summarize**: with an API key, the text goes to Claude inside `<article>` tags with instructions for the chosen length and style. The response is constrained to a JSON schema (`title`, `summary`, `key_points`) using structured outputs, so it always parses. Server-side refusal fallbacks are enabled, so a rare safety-classifier decline is retried on a fallback model automatically.
3. **Fallback**: without a key (or if the API is down), sentences are scored by term frequency with a position bonus and the best ones are returned in their original order.
4. **Stats**: word counts, compression and estimated reading time are added to every response.

## Development

```bash
pip install -r requirements-dev.txt
pytest          # run tests
ruff check .    # lint
```

## Notes

- URL fetching only works for publicly reachable pages. Paywalled or JavaScript-only pages may not have extractable text; paste the article instead.
- The app does not store articles or summaries.
- AI summaries can contain mistakes. Check important details against the original.
