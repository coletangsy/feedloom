import unittest

from scripts.anthropic_sources import AnthropicSourceError, anthropic_entries


NEWS_PAGE = """
<html><body>
  <nav><a href="/research/team/alignment">Alignment</a></nav>
  <a href="/about/team"><time>Jan 2, 2026</time>Team</a>
  <a href="/news/first-post" class="card">
    <div><span class="category">Announcements</span><time>Sep 1, 2026</time></div>
    <h2 class="featuredTitle">First post</h2><p>A useful announcement summary.</p>
  </a>
  <a href="/news/first-post" class="duplicate">
    <time>Sep 1, 2026</time><span class="title">First post</span>
  </a>
  <a href="/news/second-post"><time datetime="2026-08-21">Aug 21, 2026</time>
    <span class="title">Second post</span><p>Another summary.</p>
  </a>
</body></html>
"""


class AnthropicSourceTests(unittest.TestCase):
    def test_news_uses_visible_dated_cards_and_deduplicates_links(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return NEWS_PAGE

        entries = anthropic_entries("https://www.anthropic.com/news", fetch)

        self.assertEqual(
            entries,
            [
                {
                    "title": "First post",
                    "url": "https://www.anthropic.com/news/first-post",
                    "summary": "A useful announcement summary.",
                    "published_at": "2026-09-01",
                },
                {
                    "title": "Second post",
                    "url": "https://www.anthropic.com/news/second-post",
                    "summary": "Another summary.",
                    "published_at": "2026-08-21",
                },
            ],
        )
        self.assertEqual(calls, ["https://www.anthropic.com/news"])

    def test_research_fetches_description_when_card_has_no_summary(self):
        page = b'<a href="/research/evals"><time>Aug 20, 2026</time><h3>Evaluation lessons</h3></a>'
        article = b'<html><head><meta property="og:description" content="Lessons from a new evaluation study." /></head><article><p>Le fran\xc3\xa7ais suit.</p><p>A longer body paragraph that should only be used when the page has no useful description.</p></article></html>'
        calls = []

        def fetch(url):
            calls.append(url)
            return page if url.endswith("/research") else article

        entries = anthropic_entries("https://www.anthropic.com/research", fetch)

        self.assertEqual(entries[0]["summary"], "Lessons from a new evaluation study.")
        self.assertEqual(entries[0]["published_at"], "2026-08-20")
        self.assertEqual(
            calls,
            [
                "https://www.anthropic.com/research",
                "https://www.anthropic.com/research/evals",
            ],
        )

    def test_article_fetch_errors_are_not_hidden(self):
        page = '<a href="/news/post"><time>Aug 20, 2026</time><h2>Post</h2></a>'

        def fetch(url):
            if url.endswith("/news"):
                return page
            raise OSError("article unavailable")

        with self.assertRaisesRegex(OSError, "article unavailable"):
            anthropic_entries("https://www.anthropic.com/news", fetch)

    def test_empty_or_changed_markup_fails_visibly(self):
        for page in ("", "<html><body><a href='/news/post'>Post</a></body></html>"):
            with self.subTest(page=page), self.assertRaisesRegex(AnthropicSourceError, "Anthropic"):
                anthropic_entries("https://www.anthropic.com/news", lambda _: page)

    def test_invalid_listing_url_is_rejected(self):
        with self.assertRaisesRegex(AnthropicSourceError, "must end in /news or /research"):
            anthropic_entries("https://www.anthropic.com/blog", lambda _: NEWS_PAGE)


if __name__ == "__main__":
    unittest.main()
