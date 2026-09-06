"""Collect the current article cards embedded in Uber's Engineering page.

Uber's current blog renders its listing as HTML and embeds the server-side
article state in a percent-encoded JSON script.  There is no stable public RSS
endpoint, so this adapter reads the bounded current-page list and fetches
article metadata when a card has no summary.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Callable


Fetch = Callable[[str], bytes | str]
MAX_ENTRIES = 20
_STATE_MARKER = "article feed store"


class UberSourceError(ValueError):
    """Raised when Uber's current article-list markup is unavailable."""


def _as_text(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    raise TypeError("Uber fetcher must return bytes or str")


def _clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(html.unescape(value).split())


class _StateParser(HTMLParser):
    """Capture JSON scripts for the article-feed store."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.states: list[list[str]] = []
        self._current: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        identifier = attributes.get("id", "")
        if _STATE_MARKER in identifier.lower():
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._current is not None:
            self.states.append(self._current)
            self._current = None


class _MetadataParser(HTMLParser):
    """Capture standard descriptions from an article page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.descriptions: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        name = values.get("name", "").lower()
        prop = values.get("property", "").lower()
        if name not in {"description", "twitter:description"} and prop != "og:description":
            return
        description = _clean(values.get("content"))
        if description:
            self.descriptions.append(description)


def _state_payload(parts: list[str]) -> dict[str, Any] | None:
    raw = html.unescape("".join(parts)).strip()
    if not raw:
        return None
    try:
        value = json.loads(urllib.parse.unquote(raw))
    except (json.JSONDecodeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _article_url(listing_url: str, value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = html.unescape(value.strip())
    if candidate.startswith("www.uber.com/"):
        candidate = "https://" + candidate
    resolved = urllib.parse.urljoin(listing_url, candidate)
    parsed = urllib.parse.urlsplit(resolved)
    host = parsed.netloc.lower().split(":", 1)[0]
    if parsed.scheme not in {"http", "https"} or not parsed.path.strip("/"):
        return None
    if host != "uber.com" and not host.endswith(".uber.com"):
        return None
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _articles(state: dict[str, Any]) -> list[dict[str, Any]]:
    related = state.get("relatedPages")
    if not isinstance(related, dict):
        return []
    values = related.get("relatedPages")
    return values if isinstance(values, list) else []


def _metadata_summary(value: bytes | str) -> str:
    parser = _MetadataParser()
    parser.feed(_as_text(value))
    parser.close()
    return parser.descriptions[0] if parser.descriptions else ""


def uber_entries(url: str, fetch: Fetch) -> list[dict[str, str]]:
    """Return the dated article cards rendered on an Uber Engineering page.

    The injected ``fetch`` is called once for the listing.  Summaries are read
    from the embedded card data when available; otherwise the article's
    standard metadata is fetched to avoid returning title-only candidates.
    """

    payload = fetch(url)
    text = _as_text(payload)
    if not text.strip():
        raise UberSourceError("Uber Engineering page is empty")

    parser = _StateParser()
    parser.feed(text)
    parser.close()
    states = [_state_payload(script) for script in parser.states]
    states = [state for state in states if state is not None]
    if not states:
        raise UberSourceError(
            "Uber Engineering page has no embedded article-feed state; markup may have changed"
        )

    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for state in states:
        for article in _articles(state)[:MAX_ENTRIES]:
            if not isinstance(article, dict):
                continue
            title = _clean(article.get("title") or article.get("ogTitle"))
            article_url = _article_url(
                url,
                article.get("fullURL") or article.get("url") or article.get("href"),
            )
            published_at = _clean(article.get("publishedAt") or article.get("published_at"))
            if not title or not article_url or not published_at or article_url in seen_urls:
                continue
            seen_urls.add(article_url)
            summary = _clean(
                article.get("summary")
                or article.get("description")
                or article.get("excerpt")
                or article.get("ogDescription")
            )
            if not summary:
                summary = _metadata_summary(fetch(article_url))
            entries.append({
                "title": title,
                "url": article_url,
                "summary": summary,
                "published_at": published_at,
            })
            if len(entries) >= MAX_ENTRIES:
                return entries

    if not entries:
        raise UberSourceError(
            "Uber Engineering page has no recognizable dated article cards; markup may have changed"
        )
    return entries


__all__ = ["UberSourceError", "uber_entries"]
