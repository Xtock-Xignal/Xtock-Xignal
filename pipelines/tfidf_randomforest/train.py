from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.common import (  # noqa: E402
    DEFAULT_SEED,
    DEFAULT_TEST_RATIO,
    ensure_dir,
    load_dataset,
    save_json,
    save_split_preview,
    stratified_split,
    summarize_classification,
)
from pipelines.tfidf_randomforest.preprocessing import (  # noqa: E402
    build_stopword_strategy,
    preprocess_text,
)


PIPELINE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = ensure_dir(PIPELINE_DIR / "artifacts")


def build_argument_parser() -> argparse.ArgumentParser:
    """학습 스크립트용 stopword 전략 인자를 정의한다."""
    parser = argparse.ArgumentParser(description="Train TF-IDF + RandomForest baseline.")
    parser.add_argument("--stopword-strategy", choices=["max_df", "custom_tfidf"], default="max_df")
    parser.add_argument("--max-df", type=float, default=0.85)
    parser.add_argument("--custom-top-k", type=int, default=25)
    parser.add_argument("--custom-min-doc-frequency", type=float, default=0.6)
    return parser


def main() -> None:
    """TF-IDF 벡터화와 RandomForest 학습 전체 흐름을 수행한다."""
    args = build_argument_parser().parse_args()

    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)
    save_split_preview(ARTIFACT_DIR / "split_preview.json", split)

    train_texts = [sample.text for sample in split.train]
    y_train = [sample.label for sample in split.train]
    test_texts = [sample.text for sample in split.test]
    y_test = [sample.label for sample in split.test]

    stopword_result = build_stopword_strategy(
        train_texts,
        strategy=args.stopword_strategy,
        max_df=args.max_df,
        custom_top_k=args.custom_top_k,
        custom_min_doc_frequency=args.custom_min_doc_frequency,
    )

    normalized_train = [preprocess_text(text, stopwords=set()) for text in train_texts]
    normalized_test = [preprocess_text(text, stopwords=set()) for text in test_texts]

    vectorizer_kwargs = {
        "tokenizer": str.split,
        "preprocessor": None,
        "token_pattern": None,
        "lowercase": False,
        "ngram_range": (1, 2),
        "max_features": 5000,
        "stop_words": sorted(stopword_result.stopwords),
    }
    if args.stopword_strategy == "max_df":
        vectorizer_kwargs["max_df"] = args.max_df
    else:
        vectorizer_kwargs["max_df"] = 1.0

    vectorizer = TfidfVectorizer(**vectorizer_kwargs)
    x_train = vectorizer.fit_transform(normalized_train)
    x_test = vectorizer.transform(normalized_test)

    classifier = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        random_state=DEFAULT_SEED,
        n_jobs=-1,
    )
    classifier.fit(x_train, y_train)
    predictions = classifier.predict(x_test).tolist()

    metrics = summarize_classification(y_test, predictions)
    metrics.update(
        {
            "stopword_strategy": stopword_result.strategy,
            "vectorizer_vocabulary_size": int(len(vectorizer.vocabulary_)),
            "artifact_path": str((ARTIFACT_DIR / f"model_{args.stopword_strategy}.pkl").relative_to(ROOT_DIR)),
            "stopword_metadata": stopword_result.metadata,
        }
    )

    artifact_path = ARTIFACT_DIR / f"model_{args.stopword_strategy}.pkl"
    with artifact_path.open("wb") as file:
        pickle.dump(
            {
                "vectorizer": vectorizer,
                "classifier": classifier,
                "stopword_result": stopword_result,
                "config": vars(args),
            },
            file,
        )

    save_json(ARTIFACT_DIR / f"metrics_{args.stopword_strategy}.json", metrics)
    print("TF-IDF + RandomForest training complete")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
