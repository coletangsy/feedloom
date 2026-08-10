from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.ai_news_collect import FEEDS, TLDR_AI_FEED, canonical_url, load_state, save_seen, score_item, tldr_issue_entries


class NewsCollectorTests(unittest.TestCase):
    def test_curated_feeds_include_tldr_and_have_unique_urls(self):
        feeds = {feed.name: feed for feed in (*FEEDS, TLDR_AI_FEED)}

        self.assertEqual(feeds["AWS Machine Learning Blog"].url, "https://aws.amazon.com/blogs/machine-learning/feed/")
        self.assertEqual(feeds["Apple ML Research"].url, "https://machinelearning.apple.com/rss.xml")
        self.assertEqual(feeds["Microsoft Research"].url, "https://www.microsoft.com/en-us/research/feed/")
        self.assertEqual(feeds["Databricks"].url, "https://www.databricks.com/feed")
        self.assertEqual(feeds["PyTorch"].url, "https://pytorch.org/blog/feed.xml")
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

    def test_low_heat_hn_item_is_not_high_signal(self):
        score = score_item("New AI model", "https://example.com/post", "", 1, hn_points=2, hn_comments=1)
        self.assertLess(score, 4)

    def test_routine_version_bump_is_below_the_output_threshold(self):
        score = score_item("OpenAI Python v2.52.1", "https://github.com/openai/openai-python/releases/tag/v2.52.1", "Chores: pin a CI action", 4, github_release=True)
        self.assertLess(score, 4)

    def test_seen_state_expires_after_two_weeks(self):
        now = datetime.now(UTC)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            save_seen(path, ["current"], now)
            path.write_text('{"items": [{"id": "old", "seen_at": "2000-01-01T00:00:00Z"}, {"id": "current", "seen_at": "' + now.isoformat().replace("+00:00", "Z") + '"}]}')
            self.assertEqual(load_state(path, now + timedelta(days=1)), {"current"})


if __name__ == "__main__":
    unittest.main()
