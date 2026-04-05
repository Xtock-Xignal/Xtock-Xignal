from __future__ import annotations

import sys
from pathlib import Path

import fasttext

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
from pipelines.fasttext.preprocessing import decode_label, normalize_text, to_fasttext_line  # noqa: E402


PIPELINE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = ensure_dir(PIPELINE_DIR / "artifacts")
TRAIN_FILE = ARTIFACT_DIR / "train.txt"
TEST_FILE = ARTIFACT_DIR / "test.txt"
MODEL_PATH = ARTIFACT_DIR / "model.bin"
METRICS_PATH = ARTIFACT_DIR / "train_metrics.json"
SPLIT_PREVIEW_PATH = ARTIFACT_DIR / "split_preview.json"


def write_lines(path: Path, lines: list[str]) -> None:
    """fastText 입력용 문자열 목록을 파일로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for line in lines:
            file.write(line + "\n")


def build_lines(samples) -> list[str]:
    """샘플 목록을 fastText 학습 라인 목록으로 변환한다."""
    lines: list[str] = []
    for sample in samples:
        line = to_fasttext_line(sample.text, sample.label)
        if line:
            lines.append(line)
    return lines


def predict_labels(model, samples) -> list[str]:
    """테스트 샘플에 대한 예측 라벨 목록을 생성한다."""
    predictions: list[str] = []
    for sample in samples:
        raw_predictions = model.f.predict(normalize_text(sample.text) + "\n", 1, 0.0, "strict")
        labels = [label for _, label in raw_predictions]
        predictions.append(decode_label(labels[0]))
    return predictions


def main() -> None:
    """fastText 데이터 준비, 학습, 평가, 저장을 모두 수행한다."""
    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)
    train_lines = build_lines(split.train)
    test_lines = build_lines(split.test)

    if not train_lines:
        raise ValueError("No valid fastText training rows were generated.")

    write_lines(TRAIN_FILE, train_lines)
    write_lines(TEST_FILE, test_lines)
    save_split_preview(SPLIT_PREVIEW_PATH, split)

    model = fasttext.train_supervised(
        input=str(TRAIN_FILE),
        epoch=25,
        lr=1.0,
        wordNgrams=2,
        dim=100,
        minn=2,
        maxn=5,
        loss="softmax",
        thread=4,
    )
    model.save_model(str(MODEL_PATH))

    n, precision_at_1, recall_at_1 = model.test(str(TEST_FILE))
    y_true = [sample.label for sample in split.test]
    y_pred = predict_labels(model, split.test)
    metrics = summarize_classification(y_true, y_pred)
    metrics.update(
        {
            "precision_at_1": round(float(precision_at_1), 4),
            "recall_at_1": round(float(recall_at_1), 4),
            "test_examples": int(n),
            "model_path": str(MODEL_PATH.relative_to(ROOT_DIR)),
            "train_file": str(TRAIN_FILE.relative_to(ROOT_DIR)),
            "test_file": str(TEST_FILE.relative_to(ROOT_DIR)),
        }
    )
    save_json(METRICS_PATH, metrics)

    print("fastText training complete")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
