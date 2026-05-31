from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import torch
import torch.nn as nn
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import Dataset
from transformers import AutoConfig, AutoModel, AutoTokenizer


# ── 단일-라벨 매핑 (하위 호환) ──────────────────────────

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


# ── 단일-라벨 데이터셋 (하위 호환) ──────────────────────────

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


# ── 계층형 모델 ──────────────────────────────────────────

class HierarchicalBertModel(nn.Module):
    """공유 backbone + big_sector / sub_sector 2개 분류 헤드."""

    def __init__(
        self,
        model_name: str,
        num_big_sectors: int,
        num_sub_sectors: int,
        big_to_sub_mask: dict[int, list[int]] | None = None,
    ):
        super().__init__()
        self.config = AutoConfig.from_pretrained(model_name)
        self.backbone = AutoModel.from_pretrained(model_name)
        hidden_size = self.config.hidden_size

        self.big_classifier = nn.Linear(hidden_size, num_big_sectors)
        self.sub_classifier = nn.Linear(hidden_size, num_sub_sectors)

        self.num_big_sectors = num_big_sectors
        self.num_sub_sectors = num_sub_sectors
        self.big_to_sub_mask = big_to_sub_mask  # big_id → [sub_id, ...]

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """(big_logits, sub_logits) 반환."""
        outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        # XLM-RoBERTa: [CLS] 토큰 = 첫번째 토큰
        cls_repr = outputs.last_hidden_state[:, 0, :]  # (batch, hidden)
        big_logits = self.big_classifier(cls_repr)  # (batch, num_big)
        sub_logits = self.sub_classifier(cls_repr)   # (batch, num_sub)
        return big_logits, sub_logits

    def freeze_backbone(self, freeze: bool = True) -> None:
        """백본을 고정/해제한다."""
        for param in self.backbone.parameters():
            param.requires_grad = not freeze

    @torch.no_grad()
    def predict_hierarchical(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        threshold: float = 0.0,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """계층형 예측: big_sector → masked sub_sector.

        Returns:
            big_pred: (batch,) long tensor
            sub_pred: (batch,) long tensor (-1 = threshold 미달)
        """
        self.eval()
        big_logits, sub_logits = self(input_ids, attention_mask)
        big_pred = torch.argmax(big_logits, dim=-1)  # (batch,)

        sub_probs = torch.softmax(sub_logits, dim=-1)  # (batch, num_sub)

        # big→sub 마스크 적용: 후보가 아닌 sub_sector의 확률을 0으로
        batch_size = sub_probs.size(0)
        mask = torch.zeros_like(sub_probs)  # (batch, num_sub)
        if self.big_to_sub_mask is not None:
            for i in range(batch_size):
                b_id = int(big_pred[i].item())
                valid_ids = self.big_to_sub_mask.get(b_id, [])
                if valid_ids:
                    mask[i, valid_ids] = 1.0
        else:
            # 마스크 없으면 모든 sub_sector 허용
            mask = torch.ones_like(sub_probs)

        masked_probs = sub_probs * mask  # 후보 외에는 0
        max_probs, sub_pred = torch.max(masked_probs, dim=-1)

        # threshold 미달 → -1 (None)
        sub_pred[max_probs < threshold] = -1

        return big_pred, sub_pred


# ── 계층형 데이터셋 ──────────────────────────────────────

class HierarchicalBertDataset(Dataset):
    """big_sector, sub_sector 두 라벨을 반환하는 데이터셋."""

    def __init__(
        self,
        texts: Sequence[str],
        big_labels: Sequence[int],
        sub_labels: Sequence[int],
        tokenizer,
        max_length: int = 256,
    ):
        self.texts = list(texts)
        self.big_labels = list(big_labels)
        self.sub_labels = list(sub_labels)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, index: int):
        encoded = self.tokenizer(
            self.texts[index],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["big_labels"] = torch.tensor(self.big_labels[index], dtype=torch.long)
        item["sub_labels"] = torch.tensor(self.sub_labels[index], dtype=torch.long)
        return item


# ── 클래스 가중치 ────────────────────────────────────────

def compute_sub_class_weights(
    sub_labels: Sequence[int],
    num_classes: int,
    clipping: float = 5.0,
) -> torch.FloatTensor:
    """scikit-learn의 balanced class_weight 로 sub_sector 가중치를 계산한다.

    weight = n_samples / (n_classes * np.bincount(y))
    clipping 상한을 적용한다.
    """
    y = np.array(sub_labels, dtype=int)
    classes = np.arange(num_classes)
    weights = compute_class_weight("balanced", classes=classes, y=y)
    weights = np.clip(weights, None, clipping)
    return torch.FloatTensor(weights)
