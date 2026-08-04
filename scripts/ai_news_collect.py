#!/usr/bin/env python3
"""Collect high-signal AI and data-science news into deterministic JSON."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


LOOKBACK_HOURS = 36
STATE_DAYS = 14
USER_AGENT = "feedloom/1.0 (+local Codex briefing)"
SCOPED_TERMS = (
    "ai", "artificial intelligence", "llm", "language model", "gpt", "gemini",
    "claude", "agent", "machine learning", "deep learning", "data science",
    "mlops", "inference", "embedding", "benchmark", "transformer", "rag",
    "hugging face", "openai", "anthropic", "deepmind", "model",
)
IMPACT_TERMS = (
    "release", "launch", "api", "model", "benchmark", "open source", "security",
    "safety", "privacy", "policy", "regulation", "governance", "inference",
    "training", "research", "agent", "breaking", "deprecat", "performance",
)


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    weight: int


FEEDS = (
    Feed("OpenAI", "https://openai.com/news/rss.xml", 5),
    Feed("Google AI", "https://blog.google/technology/ai/rss/", 5),
    Feed("Google DeepMind", "https://deepmind.google/blog/rss.xml", 5),
    Feed("Hugging Face", "https://huggingface.co/blog/feed.xml", 5),
    Feed("AWS Machine Learning Blog", "https://aws.amazon.com/blogs/machine-learning/feed/", 4),
    Feed("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", 2),
    Feed("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", 2),
    Feed("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", 2),
    Feed("NVIDIA Blog", "https://blogs.nvidia.com/feed/", 3),
    Feed("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/", 3),
)
TLDR_AI_FEED = Feed("TLDR AI", "https://tldr.tech/api/rss/ai", 2)
GITHUB_RELEASES = (
    ("vLLM", "vllm-project/vllm"),
    ("Hugging Face Transformers", "huggingface/transformers"),
    ("OpenAI Python", "openai/openai-python"),
)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


def clean_text(value: str | None) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    return parser.text()


def canonical_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    kept_query = urllib.parse.urlencode(
        [(key, val) for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
         if not key.lower().startswith(("utm_", "ref", "source"))],
        doseq=True,
    )
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, kept_query, ""))


def item_id(url: str, title: str) -> str:
    basis = canonical_url(url) if url else "title:" + " ".join(title.lower().split())
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def title_id(title: str) -> str:
    return hashlib.sha256(("title:" + " ".join(title.lower().split())).encode("utf-8")).hexdigest()[:20]


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def is_article_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.path not in {"", "/"}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml, application/rss+xml, text/xml, text/html, */*"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def text_at(element: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def feed_entries(feed: Feed) -> list[dict[str, str]]:
    root = ET.fromstring(fetch(feed.url))
    entries: list[dict[str, str]] = []
    for element in root.findall(".//item") + root.findall("{http://www.w3.org/2005/Atom}entry"):
        atom = element.tag.endswith("entry")
        title = text_at(element, ("title", "{http://www.w3.org/2005/Atom}title"))
        if atom:
            link = next((node.attrib.get("href", "") for node in element.findall("{http://www.w3.org/2005/Atom}link") if node.attrib.get("rel", "alternate") == "alternate"), "")
            summary = text_at(element, ("{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
            published = text_at(element, ("{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"))
        else:
            link = text_at(element, ("link",))
            summary = text_at(element, ("description", "{http://purl.org/rss/1.0/modules/content/}encoded"))
            published = text_at(element, ("pubDate", "date"))
        entries.append({"title": clean_text(title), "url": link, "summary": clean_text(summary), "published_at": published})
    return entries


def tldr_issue_entries(value: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for article in re.findall(r"<article\b[^>]*>(.*?)</article>", value, re.I | re.S):
        link_match = re.search(
            r'<a\b(?=[^>]*\bclass=["\'][^"\']*\bfont-bold\b[^"\']*["\'])(?=[^>]*\bhref=["\']([^"\']+)["\'])[^>]*>',
            article,
            re.I | re.S,
        )
        title_match = re.search(r"<h3>(.*?)</h3>", article, re.I | re.S)
        summary_match = re.search(r'<div\b[^>]*class=["\'][^"\']*\bnewsletter-html\b[^"\']*["\'][^>]*>(.*?)</div>', article, re.I | re.S)
        title = clean_text(title_match.group(1) if title_match else "")
        summary = clean_text(summary_match.group(1) if summary_match else "")
        if not link_match or not title or not summary or "sponsor" in title.lower():
            continue
        entries.append({"title": title, "url": html.unescape(link_match.group(1)), "summary": summary})
    return entries


def tldr_entries(cutoff: datetime) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for issue in feed_entries(TLDR_AI_FEED):
        published = parse_date(issue["published_at"])
        if not published or published < cutoff:
            continue
        for article in tldr_issue_entries(fetch(issue["url"]).decode("utf-8", errors="replace")):
            article["published_at"] = issue["published_at"]
            entries.append(article)
    return entries


def score_item(title: str, url: str, summary: str, source_weight: int, *, hn_points: int = 0, hn_comments: int = 0, github_release: bool = False) -> int | None:
    corpus = f"{title} {url} {summary}".lower()
    scoped_hits = sum(term in corpus for term in SCOPED_TERMS)
    if not scoped_hits:
        return None
    score = source_weight + min(scoped_hits, 3)
    score += min(sum(term in corpus for term in IMPACT_TERMS), 3)
    if hn_points or hn_comments:
        score += 2 if hn_points >= 100 or hn_comments >= 30 else 1 if hn_points >= 30 or hn_comments >= 10 else -2
    release_signals = ("breaking", "security", "performance", "api", "model", "inference", "deprecat", "support")
    if github_release and re.search(r"\bv?\d+(?:\.\d+){1,4}\b", title, re.I) and not any(term in corpus for term in release_signals):
        score -= 4
    return score


def candidate(source: str, title: str, url: str, published_at: str, summary: str, score: int, **extra: Any) -> dict[str, Any] | None:
    published = parse_date(published_at)
    if not title or not is_article_url(url) or not published:
        return None
    data: dict[str, Any] = {
        "id": item_id(url, title),
        "title_id": title_id(title),
        "title": title,
        "url": canonical_url(url),
        "source": source,
        "published_at": published.isoformat().replace("+00:00", "Z"),
        "summary_or_snippet": summary[:1200],
        "score": score,
    }
    data.update(extra)
    return data


def hn_entries(cutoff: datetime) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"query": "AI OR LLM OR model OR agent OR data science", "tags": "story", "hitsPerPage": 100, "numericFilters": f"created_at_i>{int(cutoff.timestamp())}"})
    payload = json.loads(fetch(f"https://hn.algolia.com/api/v1/search_by_date?{query}"))
    entries: list[dict[str, Any]] = []
    for hit in payload.get("hits", []):
        title = clean_text(hit.get("title") or hit.get("story_title"))
        original_url = hit.get("url") or hit.get("story_url") or ""
        discussion_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        points = int(hit.get("points") or 0)
        comments = int(hit.get("num_comments") or 0)
        corpus = f"{title} {original_url}".lower()
        if not any(term in corpus for term in SCOPED_TERMS):
            continue
        if not original_url and (points < 100 and comments < 30):
            continue
        entries.append({"title": title, "url": original_url or discussion_url, "summary": clean_text(hit.get("story_text") or ""), "published_at": hit.get("created_at"), "points": points, "comments": comments, "discussion_url": discussion_url})
    return entries


def github_entries(name: str, repository: str) -> list[dict[str, str]]:
    payload = json.loads(fetch(f"https://api.github.com/repos/{repository}/releases?per_page=10"))
    return [{
        "title": f"{name} {release.get('name') or release.get('tag_name')}",
        "url": release.get("html_url", ""),
        "summary": clean_text(release.get("body") or ""),
        "published_at": release.get("published_at") or release.get("created_at") or "",
    } for release in payload if not release.get("draft")]


def load_state(path: Path, now: datetime) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    cutoff = now - timedelta(days=STATE_DAYS)
    return {entry["id"] for entry in payload.get("items", []) if entry.get("id") and parse_date(entry.get("seen_at")) and parse_date(entry["seen_at"]) >= cutoff}


def save_seen(path: Path, ids: list[str], now: datetime) -> None:
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text()).get("items", [])
        except (OSError, json.JSONDecodeError):
            pass
    cutoff = now - timedelta(days=STATE_DAYS)
    retained = [entry for entry in existing if entry.get("id") and parse_date(entry.get("seen_at")) and parse_date(entry["seen_at"]) >= cutoff and entry["id"] not in ids]
    retained.extend({"id": value, "seen_at": now.isoformat().replace("+00:00", "Z")} for value in ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump({"items": retained}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def selected_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text())
    values = payload.get("selected_ids", []) if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError("expected a JSON list of IDs or an object with selected_ids")
    return values


def collect(state_path: Path, lookback_hours: int, max_items: int) -> dict[str, Any]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    seen = load_state(state_path, now)
    errors: list[dict[str, str]] = []
    raw_candidates: list[dict[str, Any]] = []

    for feed in FEEDS:
        try:
            entries = feed_entries(feed)
        except Exception as error:  # One feed must not prevent the rest of the briefing.
            errors.append({"source": feed.name, "error": str(error)[:300]})
            continue
        for entry in entries:
            published = parse_date(entry["published_at"])
            score = score_item(entry["title"], entry["url"], entry["summary"], feed.weight)
            if published and published >= cutoff and score is not None:
                item = candidate(feed.name, entry["title"], entry["url"], entry["published_at"], entry["summary"], score)
                if item:
                    raw_candidates.append(item)

    try:
        entries = tldr_entries(cutoff)
        for entry in entries:
            score = score_item(entry["title"], entry["url"], entry["summary"], TLDR_AI_FEED.weight)
            if score is not None:
                item = candidate(TLDR_AI_FEED.name, entry["title"], entry["url"], entry["published_at"], entry["summary"], score)
                if item:
                    raw_candidates.append(item)
    except Exception as error:
        errors.append({"source": TLDR_AI_FEED.name, "error": str(error)[:300]})

    try:
        entries = hn_entries(cutoff)
        for entry in entries:
            score = score_item(entry["title"], entry["url"], entry["summary"], 1, hn_points=entry["points"], hn_comments=entry["comments"])
            if score is not None:
                item = candidate("Hacker News", entry["title"], entry["url"], entry["published_at"], entry["summary"], score, points=entry["points"], comments=entry["comments"], discussion_url=entry["discussion_url"])
                if item:
                    raw_candidates.append(item)
    except Exception as error:
        errors.append({"source": "Hacker News", "error": str(error)[:300]})

    for name, repository in GITHUB_RELEASES:
        try:
            entries = github_entries(name, repository)
        except Exception as error:
            errors.append({"source": name, "error": str(error)[:300]})
            continue
        for entry in entries:
            published = parse_date(entry["published_at"])
            score = score_item(entry["title"], entry["url"], entry["summary"], 4, github_release=True)
            if published and published >= cutoff and score is not None:
                item = candidate(name, entry["title"], entry["url"], entry["published_at"], entry["summary"], score, tags=["github-release"])
                if item:
                    raw_candidates.append(item)

    deduplicated: list[dict[str, Any]] = []
    known_titles: set[str] = set()
    for item in sorted(raw_candidates, key=lambda value: (-value["score"], value["published_at"]), reverse=False):
        if item["id"] in seen or item["title_id"] in seen or item["title_id"] in known_titles or item["score"] < 4:
            continue
        known_titles.add(item["title_id"])
        deduplicated.append(item)
    return {"collected_at": now.isoformat().replace("+00:00", "Z"), "lookback_hours": lookback_hours, "candidates": deduplicated[:max_items], "collection_errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("state/ai_news_seen.json"))
    parser.add_argument("--lookback-hours", type=int, default=LOOKBACK_HOURS)
    parser.add_argument("--max-items", type=int, default=40)
    parser.add_argument("--mark-seen", type=Path, metavar="JSON")
    args = parser.parse_args()
    if args.mark_seen:
        try:
            ids = selected_ids(args.mark_seen)
            save_seen(args.state, ids, datetime.now(UTC))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"Cannot update seen state: {error}", file=sys.stderr)
            return 1
        print(json.dumps({"marked_seen": len(ids)}, ensure_ascii=False))
        return 0
    print(json.dumps(collect(args.state, args.lookback_hours, args.max_items), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
