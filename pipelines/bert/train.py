from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.bert.runtime import BertTextDataset, build_label_mapping  # noqa: E402
from pipelines.common import (  # noqa: E402
    DEFAULT_SEED,
    DEFAULT_TEST_RATIO,
    ensure_dir,
    load_dataset,
    save_json,
    save_split_preview,
    stratified_split,
)


PIPELINE_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = ensure_dir(PIPELINE_DIR / "artifacts")
CHECKPOINT_DIR = ARTIFACT_DIR / "checkpoint"
LABEL_MAP_PATH = ARTIFACT_DIR / "labels.json"


def main() -> None:
    """BERT 학습용 데이터 준비와 최소 학습 루프를 실행한다."""
    split = stratified_split(load_dataset(), test_ratio=DEFAULT_TEST_RATIO, seed=DEFAULT_SEED)
    save_split_preview(ARTIFACT_DIR / "split_preview.json", split)

    label_mapping = build_label_mapping([sample.label for sample in split.train + split.test])
    save_json(
        LABEL_MAP_PATH,
        {
            "label2id": label_mapping.label2id,
            "id2label": {str(key): value for key, value in label_mapping.id2label.items()},
        },
    )

    model_name = "bert-base-multilingual-cased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(label_mapping.label2id),
        label2id=label_mapping.label2id,
        id2label=label_mapping.id2label,
    )

    train_dataset = BertTextDataset(
        [sample.text for sample in split.train],
        [label_mapping.label2id[sample.label] for sample in split.train],
        tokenizer=tokenizer,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.train()

    dataloader = torch.utils.data.DataLoader(train_dataset, batch_size=8, shuffle=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5)

    for epoch in range(2):
        total_loss = 0.0
        for batch in dataloader:
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total_loss += float(loss.item())

        print(f"epoch={epoch + 1} loss={total_loss / max(len(dataloader), 1):.4f}")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(CHECKPOINT_DIR)
    tokenizer.save_pretrained(CHECKPOINT_DIR)

    save_json(
        ARTIFACT_DIR / "train_config.json",
        {
            "model_name": model_name,
            "epochs": 2,
            "batch_size": 8,
            "learning_rate": 5e-5,
            "checkpoint_dir": str(CHECKPOINT_DIR.relative_to(ROOT_DIR)),
        },
    )
    print("BERT training skeleton complete")


if __name__ == "__main__":
    main()
