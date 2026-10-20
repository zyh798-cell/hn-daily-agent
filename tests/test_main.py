import unittest
from main import is_ai_related, build_records


class MainTests(unittest.TestCase):
    def test_ai_keyword_match(self):
        self.assertTrue(is_ai_related({"title": "New open source LLM released", "url": "https://example.com"}))

    def test_non_ai_story(self):
        self.assertFalse(is_ai_related({"title": "A guide to growing tomatoes", "url": "https://example.com"}))

    def test_build_records(self):
        records = build_records([{
            "id": 123, "title": "Example AI tool", "score": 10,
            "descendants": 2, "url": "https://example.com", "time": 1700000000
        }], None)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rank"], 1)
        self.assertIn("news.ycombinator.com/item?id=123", records[0]["hacker_news_url"])


if __name__ == "__main__":
    unittest.main()
