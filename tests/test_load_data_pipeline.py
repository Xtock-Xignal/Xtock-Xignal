import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.load_data.build_news_datasets import (
    NewsRecord,
    build_article_id,
    build_article_text,
    build_fasttext_rows,
    build_raw_rows,
    build_tfidf_rows,
    load_gemini_api_key,
)


class LoadDataPipelineHelpersTest(unittest.TestCase):
    def test_build_article_text_combines_unique_text_parts(self):
        article_text = build_article_text(
            {
                "title": "Stocks rally on rate hopes",
                "summary": "Investors pushed equities higher.",
                "content": {
                    "summary": "Investors pushed equities higher.",
                    "description": "Treasury yields fell after the inflation report.",
                },
            }
        )
        self.assertIn("Stocks rally on rate hopes", article_text)
        self.assertIn("Treasury yields fell after the inflation report.", article_text)

    def test_build_article_id_is_stable(self):
        first = build_article_id("MSFT", "https://example.com/a", "Headline")
        second = build_article_id("MSFT", "https://example.com/a", "Headline")
        self.assertEqual(first, second)

    def test_build_preprocessed_rows(self):
        records = [
            NewsRecord(
                article_id="abc123",
                ticker="MSFT",
                company_name="Microsoft",
                title="Microsoft cloud revenue rises",
                summary="Azure demand remained strong.",
                article_text="Microsoft cloud revenue rises. Azure demand remained strong.",
                publisher="Reuters",
                link="https://example.com/news",
                published_at="2026-04-06T00:00:00+00:00",
                gemini_sector="Information Technology",
                gemini_rationale="The article focuses on software and cloud infrastructure.",
                retrieval_query="MSFT Microsoft",
                retrieved_at="2026-04-06T00:00:00+00:00",
            )
        ]
        raw_rows = build_raw_rows(records)
        fasttext_rows = build_fasttext_rows(records)
        tfidf_rows = build_tfidf_rows(records)

        self.assertEqual(raw_rows, [{"text": records[0].article_text, "label": "Information Technology"}])
        self.assertEqual(len(fasttext_rows), 1)
        self.assertEqual(len(tfidf_rows), 1)
        self.assertEqual(
            set(fasttext_rows[0].keys()),
            {"text", "label", "normalized_text", "normalized_label", "fasttext_line"},
        )
        self.assertEqual(
            set(tfidf_rows[0].keys()),
            {"text", "label", "tfidf_text_max_df", "tfidf_text_custom_stopwords"},
        )
        self.assertTrue(fasttext_rows[0]["fasttext_line"].startswith("__label__Information_Technology"))
        self.assertIn("tfidf_text_max_df", tfidf_rows[0])
        self.assertIn("tfidf_text_custom_stopwords", tfidf_rows[0])

    def test_load_gemini_api_key_uses_env_first(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
            self.assertEqual(load_gemini_api_key(), "env-key")

    def test_load_gemini_api_key_reads_file_when_env_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("pipelines.load_data.build_news_datasets.DEFAULT_GEMINI_KEY_PATH", ROOT_DIR / "geminiAPI.txt"):
                self.assertTrue(load_gemini_api_key())


if __name__ == "__main__":
    unittest.main()
