import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.fasttext.preprocessing import normalize_text as normalize_fasttext_text
from pipelines.fasttext.preprocessing import to_fasttext_line
from pipelines.tfidf_randomforest.preprocessing import (
    BASE_STOPWORDS,
    derive_custom_stopwords_by_tfidf,
    lemmatize_tokens,
    preprocess_text,
)


class FastTextPreprocessingTest(unittest.TestCase):
    def test_fasttext_preprocessing_matches_tutorial_style(self):
        self.assertEqual(
            normalize_fasttext_text("Hello, WORLD!"),
            "hello , world !",
        )

    def test_fasttext_line_contains_label_prefix(self):
        self.assertEqual(
            to_fasttext_line("Cloud demand rises", "Information Technology"),
            "__label__Information_Technology cloud demand rises",
        )


class TfidfPreprocessingTest(unittest.TestCase):
    def test_tfidf_preprocessing_lowercases_removes_punctuation_and_filters_stopwords(self):
        processed = preprocess_text("The markets were running quickly, and profits jumped!")
        tokens = processed.split()
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)
        self.assertTrue("market" in tokens or "markets" in tokens)
        self.assertTrue(processed)

    def test_tfidf_uses_lemmatization_when_nltk_resources_are_available(self):
        lemmas = lemmatize_tokens("markets running profits jumped")
        self.assertIsInstance(lemmas, list)
        self.assertTrue(all(isinstance(token, str) for token in lemmas))

    def test_custom_stopword_builder_keeps_base_stopwords_and_selects_common_terms(self):
        result = derive_custom_stopwords_by_tfidf(
            [
                "Market market banks rally",
                "Market shares banks rise",
                "Market banks outlook improves",
            ],
            top_k=1,
            min_doc_frequency=0.6,
        )
        self.assertTrue(BASE_STOPWORDS.issubset(result.stopwords))
        self.assertEqual(len(result.metadata["selected_terms"]), 1)
        self.assertIn("lemmatization_enabled", result.metadata)


if __name__ == "__main__":
    unittest.main()
