"""Collect dated article cards from Anthropic's News and Research pages.

Anthropic currently renders these pages as HTML rather than exposing a stable
RSS feed.  The parser intentionally uses only article links that contain a
visible ``time`` element.  It therefore covers the cards rendered on the
current page and does not attempt to discover pagination or JavaScript-only
results.
"""

from __future__ import annotations

import html
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Callable


Fetch = Callable[[str], bytes | str]


class AnthropicSourceError(ValueError):
    """Raised when an Anthropic listing has no recognizable dated cards."""


def _clean(value: str | None) -> str:
    """Return visible text with markup, entities, and excess whitespace removed."""

    return " ".join(html.unescape(value or "").split())


def _as_text(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    raise TypeError("Anthropic fetcher must return bytes or str")


def _parse_date(value: str | None) -> date | None:
    value = _clean(value)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            parsed = None
    if parsed is not None:
        return parsed.date()
    for pattern in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _title_class(value: str) -> bool:
    lowered = value.lower()
    # The live site uses both ``featuredTitle`` and ``...__title``.
    return "title" in lowered and "subtitle" not in lowered


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    text_parts: list[str] = field(default_factory=list)
    times: list[tuple[str, str]] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    titled: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return _clean(" ".join(self.text_parts))


class _ListingParser(HTMLParser):
    """Capture anchor descendants without depending on generated CSS names."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[_Node] = []
        self.anchors: list[_Node] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {key.lower(): value or "" for key, value in attrs}
        self.nodes.append(_Node(tag.lower(), normalized))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        for node in self.nodes:
            node.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.nodes) - 1, -1, -1):
            if self.nodes[index].tag != lowered:
                continue
            closing = self.nodes[index:]
            del self.nodes[index:]
            for node in reversed(closing):
                self._finish(node)
            return

    def _finish(self, node: _Node) -> None:
        active_anchors = [candidate for candidate in self.nodes if candidate.tag == "a"]
        if node.tag == "time":
            value = (node.attrs.get("datetime", ""), node.text)
            for anchor in active_anchors:
                anchor.times.append(value)
        elif node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            for anchor in active_anchors:
                anchor.headings.append(node.text)
                if _title_class(node.attrs.get("class", "")):
                    anchor.titled.append(node.text)
        elif _title_class(node.attrs.get("class", "")):
            for anchor in active_anchors:
                anchor.titled.append(node.text)
        elif node.tag == "p":
            for anchor in active_anchors:
                anchor.paragraphs.append(node.text)
        elif node.tag == "a":
            self.anchors.append(node)


class _ArticleParser(HTMLParser):
    """Extract the first useful body paragraph and standard description tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[_Node] = []
        self.paragraphs: list[str] = []
        self.descriptions: list[str] = []
        self._article_depth = 0
        self._main_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "meta":
            name = normalized.get("name", "").lower()
            prop = normalized.get("property", "").lower()
            if name in {"description", "twitter:description"} or prop == "og:description":
                value = _clean(normalized.get("content"))
                if value:
                    self.descriptions.append(value)
            return
        lowered = tag.lower()
        self.nodes.append(_Node(lowered, normalized))
        if lowered == "article":
            self._article_depth += 1
        elif lowered == "main":
            self._main_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        for node in self.nodes:
            node.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        for index in range(len(self.nodes) - 1, -1, -1):
            if self.nodes[index].tag != lowered:
                continue
            closing = self.nodes[index:]
            del self.nodes[index:]
            for node in reversed(closing):
                self._finish(node)
            return

    def _finish(self, node: _Node) -> None:
        if node.tag in {"p", "li"} and node.text:
            # Anthropic's post paragraphs are inside article/main.  The
            # fallback keeps simple hand-written pages testable as well.
            if self._article_depth or self._main_depth or not self.paragraphs:
                self.paragraphs.append(node.text)
        if node.tag == "article":
            self._article_depth -= 1
        elif node.tag == "main":
            self._main_depth -= 1


def _section(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.rstrip("/")
    if path.endswith("/news"):
        return "news"
    if path.endswith("/research"):
        return "research"
    raise AnthropicSourceError("Anthropic source URL must end in /news or /research")


def _article_url(listing_url: str, href: str, section: str) -> str | None:
    if not href:
        return None
    resolved = urllib.parse.urljoin(listing_url, html.unescape(href.strip()))
    parsed = urllib.parse.urlsplit(resolved)
    listing = urllib.parse.urlsplit(listing_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != listing.netloc:
        return None
    if not parsed.path.startswith(f"/{section}/") or parsed.path.rstrip("/") == f"/{section}":
        return None
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _card_title(card: _Node) -> str:
    candidates = [value for value in (*card.titled, *card.headings) if _clean(value)]
    if candidates:
        return _clean(candidates[0])
    fallback = card.text
    for raw_datetime, raw_text in card.times:
        for value in (raw_datetime, raw_text):
            value = _clean(value)
            if value:
                fallback = fallback.replace(value, " ", 1)
    for paragraph in card.paragraphs:
        if paragraph:
            fallback = fallback.replace(paragraph, " ", 1)
    return _clean(fallback)


def _card_date(card: _Node) -> str | None:
    for raw_datetime, raw_text in card.times:
        parsed = _parse_date(raw_datetime) or _parse_date(raw_text)
        if parsed:
            return parsed.isoformat()
    return None


def _metadata_summary(value: bytes | str) -> str:
    parser = _ArticleParser()
    parser.feed(_as_text(value))
    parser.close()
    generic_description = "anthropic is an ai safety and research company that's working to build reliable, interpretable, and steerable ai systems."
    for description in parser.descriptions:
        if description.lower() != generic_description:
            return description
    for paragraph in parser.paragraphs:
        # A few Anthropic posts begin with a translation byline such as
        # ``Le français suit.``.  Prefer a real body paragraph when available.
        if len(paragraph) >= 40:
            return paragraph
    if parser.descriptions:
        return parser.descriptions[0]
    if parser.paragraphs:
        return parser.paragraphs[0]
    return ""


def anthropic_entries(url: str, fetch: Fetch) -> list[dict[str, str]]:
    """Return dated Anthropic article cards from a News or Research listing.

    ``fetch`` is injected so callers can reuse their network policy and tests
    can provide fixtures.  It is deliberately allowed to raise: a failed
    listing or article request must reach the collector's source error
    reporting instead of becoming an unexplained partial result.
    """

    section = _section(url)
    payload = fetch(url)
    text = _as_text(payload)
    if not text.strip():
        raise AnthropicSourceError(f"Anthropic {section} page is empty")

    parser = _ListingParser()
    parser.feed(text)
    parser.close()
    cards: list[tuple[str, _Node, str, str]] = []
    seen_urls: set[str] = set()
    for card in parser.anchors:
        article_url = _article_url(url, card.attrs.get("href", ""), section)
        published_at = _card_date(card)
        title = _card_title(card)
        if not article_url or not published_at or not title or article_url in seen_urls:
            continue
        seen_urls.add(article_url)
        cards.append((article_url, card, title, published_at))

    if not cards:
        raise AnthropicSourceError(
            f"Anthropic {section} page has no recognizable dated article cards; markup may have changed"
        )

    entries: list[dict[str, str]] = []
    for article_url, card, title, published_at in cards:
        summary = " ".join(value for value in (_clean(item) for item in card.paragraphs) if value)
        if not summary:
            # This request is intentionally outside a try/except.  A broken
            # article fetch is a visible source failure, never a silent drop.
            summary = _metadata_summary(fetch(article_url))
        entries.append({
            "title": title,
            "url": article_url,
            "summary": summary,
            "published_at": published_at,
        })
    return entries


__all__ = ["AnthropicSourceError", "anthropic_entries"]
