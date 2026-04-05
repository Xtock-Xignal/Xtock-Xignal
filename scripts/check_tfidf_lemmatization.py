from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.tfidf_randomforest.preprocessing import _ensure_nltk_resources, lemmatize_tokens, preprocess_text, tokenize  # noqa: E402


SAMPLES = [
    "Markets were running quickly while profits jumped.",
    "Analysts said companies are improving earnings forecasts.",
]


def main() -> None:
    print(f"nltk_resources_ready: {_ensure_nltk_resources()}")
    for sample in SAMPLES:
        print("---")
        print(f"raw: {sample}")
        print(f"tokens: {tokenize(sample)}")
        print(f"lemmas: {lemmatize_tokens(sample)}")
        print(f"preprocessed: {preprocess_text(sample)}")


if __name__ == "__main__":
    main()
