from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch.utils.data import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer


@dataclass(frozen=True)
class LabelMapping:
    label2id: dict[str, int]
    id2label: dict[int, str]


def build_label_mapping(labels: Sequence[str]) -> LabelMapping:
    """문자열 라벨과 정수 라벨의 양방향 매핑을 만든다."""
    unique = sorted(set(labels))
    label2id = {label: index for index, label in enumerate(unique)}
    id2label = {index: label for label, index in label2id.items()}
    return LabelMapping(label2id=label2id, id2label=id2label)


class BertTextDataset(Dataset):
    def __init__(self, texts: Sequence[str], labels: Sequence[int], tokenizer, max_length: int = 256):
        """문장, 라벨, 토크나이저를 배치용 데이터셋으로 묶는다."""
        self.texts = list(texts)
        self.labels = list(labels)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        """데이터셋 전체 샘플 개수를 반환한다."""
        return len(self.texts)

    def __getitem__(self, index: int):
        """단일 샘플을 토크나이즈해 모델 입력 형식으로 반환한다."""
        encoded = self.tokenizer(
            self.texts[index],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["labels"] = torch.tensor(self.labels[index], dtype=torch.long)
        return item
