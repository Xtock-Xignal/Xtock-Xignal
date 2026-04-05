from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import sklearn  # noqa: F401

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.common import DEFAULT_SEED, DEFAULT_TEST_RATIO, load_dataset, stratified_split, summarize_classification  # noqa: E402
from pipelines.tfidf_randomforest.preprocessing import preprocess_text  # noqa: E402


PIPELINE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PIPELINE_DIR / "artifacts"


def build_argument_parser() -> argparse.ArgumentParser:
    """평가 스크립트용 stopword 전략 인자를 정의한다."""
    parser = argparse.ArgumentParser(description="Evaluate TF-IDF + RandomForest baseline.")
    parser.add_argument("--stopword-strategy", choices=["max_df", "custom_tfidf"], default="max_df")
    return parser


def main() -> None:
    """저장된 TF-IDF 모델 아티팩트로 테스트 성능을 계산한다."""
    args = build_argument_parser().parse_args()
    artifact_path = ARTIFACT_DIR / f"model_{args.stopword_strategy}.pkl"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}. Run the matching train.py first.")

    with artifact_path.open("rb") as file:
        artifact = pickle.load(file)

    vectorizer = artifact["vectorizer"]
    classifier = artifact["classifier"]

    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)
    test_texts = [preprocess_text(sample.text, stopwords=set()) for sample in split.test]
    y_true = [sample.label for sample in split.test]
    predictions = classifier.predict(vectorizer.transform(test_texts)).tolist()

    metrics = summarize_classification(y_true, predictions)
    print("TF-IDF + RandomForest test metrics")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
