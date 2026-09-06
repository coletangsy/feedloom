from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.ai_news_collect import (
    FEEDS,
    TLDR_AI_FEED,
    canonical_url,
    collect,
    hn_entries,
    load_state,
    save_seen,
    score_item,
    score_reading_item,
    section_for,
    tldr_issue_entries,
)


class NewsCollectorTests(unittest.TestCase):
    def test_curated_feeds_include_tldr_and_have_unique_urls(self):
        feeds = {feed.name: feed for feed in (*FEEDS, TLDR_AI_FEED)}

        self.assertEqual(feeds["AWS Machine Learning Blog"].url, "https://aws.amazon.com/blogs/machine-learning/feed/")
        self.assertEqual(feeds["MIT Technology Review AI"].url, "https://www.technologyreview.com/topic/artificial-intelligence/feed/")
        self.assertEqual(feeds["TLDR AI"].url, "https://tldr.tech/api/rss/ai")
        self.assertEqual(len(feeds), len({feed.url for feed in feeds.values()}))

    def test_tldr_issue_entries_keep_exact_links_and_drop_sponsors(self):
        entries = tldr_issue_entries('<article><a class="font-bold" href="https://example.com/story"><h3>New AI model</h3></a><div class="newsletter-html">A useful summary.</div></article><article><a class="font-bold" href="https://example.com/sponsor"><h3>AI platform (Sponsor)</h3></a><div class="newsletter-html">Sponsored.</div></article>')

        self.assertEqual(entries, [{"title": "New AI model", "url": "https://example.com/story", "summary": "A useful summary."}])

    def test_canonical_url_drops_tracking_but_keeps_meaningful_query(self):
        self.assertEqual(
            canonical_url("https://Example.com/post/?utm_source=x&model=gpt#section"),
            "https://example.com/post?model=gpt",
        )

    def test_hn_discussion_heat_changes_signal(self):
        low_heat = score_item("New AI model", "https://example.com/post", "", 1, hn_points=2, hn_comments=1)
        active_discussion = score_item("New AI model", "https://example.com/post", "", 1, hn_points=100, hn_comments=30)
        most_discussed = score_item("New AI model", "https://example.com/post", "", 1, hn_points=300, hn_comments=100)

        self.assertLess(low_heat, 4)
        self.assertGreaterEqual(active_discussion, 4)
        self.assertGreater(most_discussed, active_discussion)

    def test_hn_uses_popularity_ranked_search_for_recent_stories(self):
        payload = b'{"hits": [{"title": "New AI model", "url": "https://example.com/", "points": 300, "num_comments": 100, "created_at": "2026-08-12T01:00:00Z", "objectID": "1"}]}'
        with patch("scripts.ai_news_collect.fetch", return_value=payload) as fetch:
            entries = hn_entries(datetime(2026, 8, 12, tzinfo=UTC))

        url = fetch.call_args.args[0]
        self.assertIn("/api/v1/search?", url)
        self.assertNotIn("query=", url)
        self.assertEqual(entries[0]["url"], "https://news.ycombinator.com/item?id=1")

    def test_ai_matches_a_term_not_part_of_an_unrelated_word(self):
        self.assertIsNone(score_item("Email training update", "https://example.com/post", "Paid leave changes", 2))
        self.assertIsNotNone(score_item("AI training update", "https://example.com/post", "", 2))

    def test_routine_version_bump_is_below_the_output_threshold(self):
        score = score_item("OpenAI Python v2.52.1", "https://github.com/openai/openai-python/releases/tag/v2.52.1", "Chores: pin a CI action", 4, github_release=True)
        self.assertLess(score, 4)

    def test_old_item_needs_a_reading_signal(self):
        self.assertIsNone(
            score_reading_item(
                "OpenAI model release",
                "https://example.com/release",
                "A routine model release.",
                2,
            )
        )
        self.assertIsNotNone(
            score_reading_item(
                "A deep dive into LLM evaluation",
                "https://example.com/deep-dive",
                "Research lessons from a benchmark study.",
                2,
            )
        )

    def test_section_for_keeps_recent_items_in_latest(self):
        now = datetime(2026, 8, 12, tzinfo=UTC)
        latest_cutoff = now - timedelta(hours=36)
        reading_cutoff = now - timedelta(days=30)

        self.assertEqual(section_for(now - timedelta(hours=1), latest_cutoff, reading_cutoff, 6), "latest")
        self.assertEqual(section_for(now - timedelta(days=3), latest_cutoff, reading_cutoff, 6), "reading")
        self.assertIsNone(section_for(now - timedelta(days=3), latest_cutoff, reading_cutoff, None))

    def test_collect_returns_recent_and_older_reading_candidates(self):
        now = datetime.now(UTC)
        entries = {
            "OpenAI": [
                {"title": "New AI model release", "url": "https://example.com/latest", "summary": "A new API model release.", "published_at": (now - timedelta(hours=1)).isoformat()},
                {"title": "A deep dive into LLM evaluation", "url": "https://example.com/reading", "summary": "Research lessons from a benchmark study.", "published_at": (now - timedelta(days=3)).isoformat()},
            ],
        }

        def feed_entries(feed):
            return entries.get(feed.name, [])

        with TemporaryDirectory() as directory:
            with patch("scripts.ai_news_collect.feed_entries", side_effect=feed_entries), patch("scripts.ai_news_collect.tldr_entries", return_value=[]), patch("scripts.ai_news_collect.hn_entries", return_value=[]), patch("scripts.ai_news_collect.github_entries", return_value=[]):
                result = collect(Path(directory) / "seen.json", lookback_hours=36, max_items=10, reading_lookback_days=30)

        self.assertEqual([item["section"] for item in result["candidates"]], ["latest", "reading"])

    def test_seen_state_expires_after_two_weeks(self):
        now = datetime.now(UTC)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            save_seen(path, ["current"], now)
            path.write_text('{"items": [{"id": "old", "seen_at": "2000-01-01T00:00:00Z"}, {"id": "current", "seen_at": "' + now.isoformat().replace("+00:00", "Z") + '"}]}')
            self.assertEqual(load_state(path, now + timedelta(days=1)), {"current"})

    def test_overlapping_sources_deduplicate_exact_article_with_different_titles(self):
        published = datetime.now(UTC).isoformat()
        entries = [
            {"title": "AI research report", "url": "https://example.com/study?utm_source=google", "summary": "Research findings.", "published_at": published},
            {"title": "New AI research findings", "url": "https://example.com/study/", "summary": "Research findings.", "published_at": published},
        ]
        with TemporaryDirectory() as directory:
            with patch("scripts.ai_news_collect.feed_entries", return_value=entries), patch("scripts.ai_news_collect.tldr_entries", return_value=[]), patch("scripts.ai_news_collect.hn_entries", return_value=[]), patch("scripts.ai_news_collect.github_entries", return_value=[]):
                result = collect(Path(directory) / "seen.json", 36, 40)
        self.assertEqual(len(result["candidates"]), 1)

    def test_technical_reading_accepts_data_engineering_but_not_company_news(self):
        self.assertIsNotNone(score_reading_item("Scaling a data platform", "https://example.com/post", "Architecture lessons from data engineering.", 4))
        self.assertIsNone(score_item("Opening our new office", "https://example.com/post", "Meet our team.", 4))

    def test_signals_study_can_enter_reading_lane(self):
        self.assertIsNotNone(score_reading_item("How people use ChatGPT", "https://openai.com/index/study", "A study with findings on AI adoption.", 5))

    def test_scoring_ignores_terms_outside_the_emitted_snippet(self):
        summary = "Ordinary company news. " * 100 + " AI research training benchmark"
        self.assertIsNone(score_item("Office update", "https://example.com/post", summary, 4))
        self.assertIsNone(score_reading_item("AI update", "https://example.com/post", summary, 4))


if __name__ == "__main__":
    unittest.main()
