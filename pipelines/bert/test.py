from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.common import DEFAULT_SEED, DEFAULT_TEST_RATIO, load_dataset, stratified_split, summarize_classification  # noqa: E402


PIPELINE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = PIPELINE_DIR / "artifacts"
CHECKPOINT_DIR = ARTIFACT_DIR / "checkpoint"
LABEL_MAP_PATH = ARTIFACT_DIR / "labels.json"


def main() -> None:
    """저장된 BERT 체크포인트로 테스트 예측 성능을 평가한다."""
    if not CHECKPOINT_DIR.exists():
        raise FileNotFoundError(f"Checkpoint not found: {CHECKPOINT_DIR}. Run pipelines/bert/train.py first.")
    if not LABEL_MAP_PATH.exists():
        raise FileNotFoundError(f"Label mapping not found: {LABEL_MAP_PATH}. Run pipelines/bert/train.py first.")

    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)
    with LABEL_MAP_PATH.open("r", encoding="utf-8") as file:
        saved_mapping = json.load(file)
    id2label = {int(key): value for key, value in saved_mapping["id2label"].items()}

    tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(CHECKPOINT_DIR)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    predictions: list[str] = []
    with torch.no_grad():
        for sample in split.test:
            encoded = tokenizer(
                sample.text,
                truncation=True,
                padding=True,
                max_length=256,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            logits = model(**encoded).logits
            label_id = int(torch.argmax(logits, dim=-1).item())
            predictions.append(id2label[label_id])

    metrics = summarize_classification([sample.label for sample in split.test], predictions)
    print("BERT test metrics")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
