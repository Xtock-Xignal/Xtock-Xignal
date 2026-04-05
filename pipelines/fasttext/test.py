from __future__ import annotations

import sys
from pathlib import Path

import fasttext

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.common import DEFAULT_SEED, DEFAULT_TEST_RATIO, load_dataset, stratified_split, summarize_classification  # noqa: E402
from pipelines.fasttext.preprocessing import decode_label, normalize_text  # noqa: E402


PIPELINE_DIR = Path(__file__).resolve().parent
MODEL_PATH = PIPELINE_DIR / "artifacts" / "model.bin"


def main() -> None:
    """저장된 fastText 모델로 테스트 세트를 다시 평가한다."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}. Run pipelines/fasttext/train.py first.")

    model = fasttext.load_model(str(MODEL_PATH))
    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)

    y_true = [sample.label for sample in split.test]
    y_pred: list[str] = []

    for sample in split.test:
        raw_predictions = model.f.predict(normalize_text(sample.text) + "\n", 1, 0.0, "strict")
        labels = [label for _, label in raw_predictions]
        y_pred.append(decode_label(labels[0]))

    metrics = summarize_classification(y_true, y_pred)
    print("fastText test metrics")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
