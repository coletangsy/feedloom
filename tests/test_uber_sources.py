import json
from urllib.parse import quote
import unittest

from scripts.uber_sources import UberSourceError, uber_entries


LISTING_URL = "https://www.uber.com/us/en/blog/engineering/?uber_client_name=784"


def listing_page(articles: list[dict[str, str]]) -> str:
    state = {"relatedPages": {"relatedPages": articles, "totalCount": len(articles)}}
    encoded = quote(json.dumps(state, ensure_ascii=False), safe="")
    return (
        '<html><script type="application/json" '
        'id="__LOCAL_REDUX_STATE_Newsroom_Article Feed Store_%2Fus%2Fen%2Fblog%2Fengineering%2F__">'
        f"{encoded}</script></html>"
    )


class UberSourceTests(unittest.TestCase):
    def test_reads_current_cards_and_uses_embedded_summary_without_article_fetch(self):
        page = listing_page([
            {
                "fullURL": "www.uber.com/us/en/blog/first/",
                "title": "Scaling AI at Uber",
                "publishedAt": "2026-09-01T13:15:00Z",
                "summary": "A practical look at the production architecture.",
            },
            {
                "fullURL": "https://www.uber.com/us/en/blog/second/",
                "ogTitle": "Data platform lessons",
                "publishedAt": "2026-08-27T12:30:00Z",
                "summary": "Data platform summary.",
            },
        ])
        calls: list[str] = []

        def fetch(url: str) -> str:
            calls.append(url)
            return page

        entries = uber_entries(LISTING_URL, fetch)

        self.assertEqual(calls, [LISTING_URL])
        self.assertEqual(entries, [
            {
                "title": "Scaling AI at Uber",
                "url": "https://www.uber.com/us/en/blog/first/",
                "summary": "A practical look at the production architecture.",
                "published_at": "2026-09-01T13:15:00Z",
            },
            {
                "title": "Data platform lessons",
                "url": "https://www.uber.com/us/en/blog/second/",
                "summary": "Data platform summary.",
                "published_at": "2026-08-27T12:30:00Z",
            },
        ])

    def test_fills_missing_summary_from_article_metadata(self):
        article_url = "https://www.uber.com/us/en/blog/first/"
        page = listing_page([
            {
                "fullURL": article_url,
                "title": "Scaling AI at Uber",
                "publishedAt": "2026-09-01T13:15:00Z",
            },
        ])
        calls: list[str] = []

        def fetch(url: str) -> str:
            calls.append(url)
            if url == article_url:
                return '<meta property="og:description" content="Metadata summary.">'
            return page

        entries = uber_entries(LISTING_URL, fetch)

        self.assertEqual(calls, [LISTING_URL, article_url])
        self.assertEqual(entries[0]["summary"], "Metadata summary.")

    def test_raises_when_embedded_state_is_missing_or_empty(self):
        with self.assertRaisesRegex(UberSourceError, "empty"):
            uber_entries(LISTING_URL, lambda _: "")
        with self.assertRaisesRegex(UberSourceError, "markup may have changed"):
            uber_entries(LISTING_URL, lambda _: "<html><body>Challenge</body></html>")

    def test_keeps_the_current_list_bounded(self):
        cards = [
            {
                "fullURL": f"www.uber.com/us/en/blog/{index}/",
                "title": f"AI article {index}",
                "publishedAt": "2026-09-01T13:15:00Z",
                "summary": "Summary",
            }
            for index in range(25)
        ]

        entries = uber_entries(LISTING_URL, lambda _: listing_page(cards))

        self.assertEqual(len(entries), 20)


if __name__ == "__main__":
    unittest.main()
