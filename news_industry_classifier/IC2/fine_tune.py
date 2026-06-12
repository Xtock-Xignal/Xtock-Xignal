"""
IC2 Fine-tuning: sector → industry_group (GICS hierarchical)
============================================================
Fine-tunes BAAI/bge-m3 backbone on project's GICS-labeled dataset:

  Sector classification (11 GICS sectors)
  Industry group classification (25 GICS industry groups, given sector)

Architecture:
  Shared backbone (BAAI/bge-m3) + 2 Linear heads

Usage:
  python IC2/fine_tune.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluate.compare_models import (
    GICSLabelMapping,
    gics_stratified_split,
)
from utils.util_modeling import (
    NEWS_CSV,
    ensure_dir,
    load_gics_dataset,
    save_json,
)
from utils.util_eval import precision_recall_f1

IC2_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = ensure_dir(IC2_DIR / "train_history")
CHECKPOINT_DIR = ensure_dir(ARTIFACT_DIR / "checkpoint")
LABEL_MAP_PATH = ARTIFACT_DIR / "labels.json"
HPARAMS_PATH = IC2_DIR / "config" / "model_config.yaml"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── 모델 정의 ──────────────────────────────────────────


class GICSBertModel(nn.Module):
    """BGE-M3 backbone + sector / industry_group 2개 분류 헤드.

    IPTC의 HierarchicalBertModel과 동일한 구조:
      - 공유 backbone (BAAI/bge-m3 → XLMRobertaModel)
      - sector 분류 Linear 헤드
      - industry_group 분류 Linear 헤드

    load_from_ic2=True 시 BAAI/IndustryCorpus2_Classifier 의
    backbone 가중치로 초기화 (industry 도메인 사전학습 활용).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        num_sectors: int = 11,
        num_igs: int = 25,
        sector_to_ig_mask: dict[int, list[int]] | None = None,
        load_from_ic2: bool = True,
    ):
        super().__init__()

        if load_from_ic2:
            from transformers import AutoModelForSequenceClassification
            ic2 = AutoModelForSequenceClassification.from_pretrained(
                "BAAI/IndustryCorpus2_Classifier",
                trust_remote_code=False,
            )
            # IndustryCorpus2_Classifier = XLMRobertaForSequenceClassification
            # → backbone = .roberta
            self.backbone = ic2.base_model
        else:
            from transformers import AutoModel
            self.backbone = AutoModel.from_pretrained(model_name)

        hidden_size = self.backbone.config.hidden_size

        self.sector_classifier = nn.Linear(hidden_size, num_sectors)
        self.ig_classifier = nn.Linear(hidden_size, num_igs)

        self.num_sectors = num_sectors
        self.num_igs = num_igs
        self.sector_to_ig_mask = sector_to_ig_mask  # sector_id → [ig_id, ...]

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """(sector_logits, ig_logits) 반환."""
        outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        # BGE-M3 (XLMRoberta): [CLS] 토큰 = 첫번째 토큰
        cls_repr = outputs.last_hidden_state[:, 0, :]  # (batch, hidden)
        sector_logits = self.sector_classifier(cls_repr)  # (batch, num_sectors)
        ig_logits = self.ig_classifier(cls_repr)           # (batch, num_igs)
        return sector_logits, ig_logits

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
        """계층형 예측: sector → masked industry_group.

        Returns:
            sector_pred: (batch,) long tensor
            ig_pred: (batch,) long tensor (-1 = threshold 미달)
        """
        self.eval()
        sector_logits, ig_logits = self(input_ids, attention_mask)
        sector_pred = torch.argmax(sector_logits, dim=-1)  # (batch,)

        ig_probs = torch.softmax(ig_logits, dim=-1)  # (batch, num_igs)

        # sector→ig 마스크 적용: 후보가 아닌 IG의 확률을 0으로
        batch_size = ig_probs.size(0)
        mask = torch.zeros_like(ig_probs)
        if self.sector_to_ig_mask is not None:
            for i in range(batch_size):
                b_id = int(sector_pred[i].item())
                valid_ids = self.sector_to_ig_mask.get(b_id, [])
                if valid_ids:
                    mask[i, valid_ids] = 1.0
        else:
            mask = torch.ones_like(ig_probs)

        masked_probs = ig_probs * mask
        max_probs, ig_pred = torch.max(masked_probs, dim=-1)

        # threshold 미달 → -1 (None)
        ig_pred[max_probs < threshold] = -1

        return sector_pred, ig_pred


# ── GICS 데이터셋 ──────────────────────────────────────


class GICSBertDataset(Dataset):
    """sector, industry_group 두 라벨을 반환하는 데이터셋."""

    def __init__(
        self,
        texts: list[str],
        sector_labels: list[int],
        ig_labels: list[int],
        tokenizer,
        max_length: int = 512,
    ):
        self.texts = texts
        self.sector_labels = sector_labels
        self.ig_labels = ig_labels
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
        item["big_labels"] = torch.tensor(self.sector_labels[index], dtype=torch.long)
        item["sub_labels"] = torch.tensor(self.ig_labels[index], dtype=torch.long)
        return item


# ── 유틸 ────────────────────────────────────────────────


def load_hparams(path: Path = HPARAMS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_ig_class_weights(
    ig_labels: list[int],
    num_classes: int,
    clipping: float = 5.0,
) -> torch.FloatTensor:
    """IPTC의 compute_sub_class_weights 와 동일."""
    y = np.array(ig_labels, dtype=int)
    classes = np.arange(num_classes)
    weights = compute_class_weight("balanced", classes=classes, y=y)
    weights = np.clip(weights, None, clipping)
    return torch.FloatTensor(weights)


# ── 검증 ────────────────────────────────────────────────


@torch.no_grad()
def validate(
    model: GICSBertModel,
    loader: DataLoader,
    label_mapping: GICSLabelMapping,
    threshold: float = 0.0,
) -> dict:
    model.eval()
    all_sector_true: list[str] = []
    all_sector_pred: list[str] = []
    all_ig_true: list[str] = []
    all_ig_pred: list[str] = []

    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)

        sector_pred_ids, ig_pred_ids = model.predict_hierarchical(
            input_ids, attention_mask, threshold=threshold,
        )

        sector_true_ids = batch["big_labels"].numpy()
        ig_true_ids = batch["sub_labels"].numpy()

        for i in range(len(sector_true_ids)):
            all_sector_true.append(label_mapping.sector_id2label[int(sector_true_ids[i])])
            all_sector_pred.append(label_mapping.sector_id2label[int(sector_pred_ids[i].item())])
            all_ig_true.append(label_mapping.ig_id2label[int(ig_true_ids[i])])
            ip_id = int(ig_pred_ids[i].item())
            all_ig_pred.append("__NONE__" if ip_id == -1 else label_mapping.ig_id2label[ip_id])

    sector_metrics = precision_recall_f1(all_sector_true, all_sector_pred)
    sector_acc = sum(1 for t, p in zip(all_sector_true, all_sector_pred) if t == p) / max(len(all_sector_true), 1)

    # IG: sector가 맞은 샘플만 평가
    ig_when_sector_true = [it for st, sp, it in zip(all_sector_true, all_sector_pred, all_ig_true) if st == sp]
    ig_when_sector_pred = [ip for st, sp, ip in zip(all_sector_true, all_sector_pred, all_ig_pred) if st == sp]
    ig_ws_metrics = precision_recall_f1(ig_when_sector_true, ig_when_sector_pred) if ig_when_sector_true else {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    ig_ws_metrics["accuracy"] = round(sum(1 for t, p in zip(ig_when_sector_true, ig_when_sector_pred) if t == p) / max(len(ig_when_sector_true), 1), 4)

    # IG overall
    ig_overall = precision_recall_f1(all_ig_true, all_ig_pred)
    ig_overall["accuracy"] = round(sum(1 for t, p in zip(all_ig_true, all_ig_pred) if t == p) / max(len(all_ig_true), 1), 4)

    return {
        "sector_acc": round(sector_acc, 4),
        "sector_metrics": sector_metrics,
        "ig_when_sector_metrics": ig_ws_metrics,
        "ig_overall_metrics": ig_overall,
    }


# ── 시각화 ──────────────────────────────────────────────


def plot_training_metrics(
    epoch_sector: list[dict],
    epoch_ig_when_sector: list[dict],
    epoch_ig_overall: list[dict],
    save_dir: Path,
) -> None:
    epochs = list(range(1, len(epoch_sector) + 1))

    def _plot(ax, epochs_vals, metrics_list, title):
        f1 = [m["f1"] for m in metrics_list]
        prec = [m["precision"] for m in metrics_list]
        rec = [m["recall"] for m in metrics_list]
        ax.plot(epochs_vals, f1, "o-", label="F1")
        ax.plot(epochs_vals, prec, "s--", label="Precision")
        ax.plot(epochs_vals, rec, "d-.", label="Recall")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Score")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4))
    _plot(ax1, epochs, epoch_sector, "GICS Sector")
    _plot(ax2, epochs, epoch_ig_when_sector, "Industry Group (Sector Correct)")
    _plot(ax3, epochs, epoch_ig_overall, "Industry Group (Overall)")
    plt.tight_layout()

    path = save_dir / "training_metrics.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Metrics plot saved: {path}")


# ── 메인 ────────────────────────────────────────────────


def main() -> None:
    hparams = load_hparams()
    training = hparams["training"]
    loss_cfg = hparams["loss"]
    eval_cfg = hparams["evaluation"]
    opt_cfg = hparams["optimizer"]

    set_seed(training["seed"])

    print("Loading GICS dataset (news.csv)...")
    samples = load_gics_dataset(NEWS_CSV)
    print(f"  Total samples: {len(samples)}")

    label_mapping = GICSLabelMapping(
        sector_label2id={},
        sector_id2label={},
        ig_label2id={},
        ig_id2label={},
        sector_to_ig_mask={},
    )

    # ── label mapping 구축 ────────────────────────────
    sectors = sorted({s.sector for s in samples})
    igs = sorted({s.industry_group for s in samples})

    label_mapping.sector_label2id = {s: i for i, s in enumerate(sectors)}
    label_mapping.sector_id2label = {i: s for s, i in label_mapping.sector_label2id.items()}
    label_mapping.ig_label2id = {s: i for i, s in enumerate(igs)}
    label_mapping.ig_id2label = {i: s for s, i in label_mapping.ig_label2id.items()}

    # sector → IG 후보 마스크 (샘플 데이터에서 추론)
    sector_to_ig_mask: dict[int, list[int]] = {i: [] for i in range(len(sectors))}
    for s in samples:
        sec_id = label_mapping.sector_label2id[s.sector]
        ig_id = label_mapping.ig_label2id[s.industry_group]
        if ig_id not in sector_to_ig_mask[sec_id]:
            sector_to_ig_mask[sec_id].append(ig_id)
    label_mapping.sector_to_ig_mask = sector_to_ig_mask

    print(f"  Sectors: {label_mapping.num_sectors}")
    print(f"  Industry groups: {label_mapping.num_industry_groups}")

    train_samples, test_samples = gics_stratified_split(
        samples, training["test_ratio"], training["seed"],
    )
    print(f"  Train: {len(train_samples)} | Test: {len(test_samples)}")

    # IG 클래스 가중치 계산
    all_ig_ids = [label_mapping.ig_label2id[s.industry_group] for s in samples]
    ig_class_weights = compute_ig_class_weights(
        all_ig_ids,
        label_mapping.num_industry_groups,
        loss_cfg["class_weight_clipping"],
    ).to(DEVICE)

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(training["model_name"])

    train_dataset = GICSBertDataset(
        texts=[s.text for s in train_samples],
        sector_labels=[label_mapping.sector_label2id[s.sector] for s in train_samples],
        ig_labels=[label_mapping.ig_label2id[s.industry_group] for s in train_samples],
        tokenizer=tokenizer,
        max_length=training["max_length"],
    )
    test_dataset = GICSBertDataset(
        texts=[s.text for s in test_samples],
        sector_labels=[label_mapping.sector_label2id[s.sector] for s in test_samples],
        ig_labels=[label_mapping.ig_label2id[s.industry_group] for s in test_samples],
        tokenizer=tokenizer,
        max_length=training["max_length"],
    )

    train_loader = DataLoader(train_dataset, batch_size=training["batch_size"], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=training["batch_size"])

    model = GICSBertModel(
        model_name=training["model_name"],
        num_sectors=label_mapping.num_sectors,
        num_igs=label_mapping.num_industry_groups,
        sector_to_ig_mask=label_mapping.sector_to_ig_mask,
        load_from_ic2=training.get("load_from_ic2", True),
    ).to(DEVICE)

    sector_loss_fn = nn.CrossEntropyLoss()
    ig_loss_fn = nn.CrossEntropyLoss(weight=ig_class_weights)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training["learning_rate"],
        weight_decay=opt_cfg["weight_decay"],
        eps=opt_cfg["adam_epsilon"],
    )

    epoch_sector_metrics: list[dict] = []
    epoch_ig_when_sector_metrics: list[dict] = []
    epoch_ig_overall_metrics: list[dict] = []

    num_epochs = training["num_epochs"]
    for epoch in range(1, num_epochs + 1):
        model.train()
        total_loss = 0.0
        steps = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{num_epochs}", leave=False)
        for batch in pbar:
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            sector_labels = batch["big_labels"].to(DEVICE)
            ig_labels = batch["sub_labels"].to(DEVICE)

            sector_logits, ig_logits = model(input_ids, attention_mask)

            sector_loss = sector_loss_fn(sector_logits, sector_labels)
            ig_loss = ig_loss_fn(ig_logits, ig_labels)
            loss = loss_cfg["sector_loss_weight"] * sector_loss + loss_cfg["ig_loss_weight"] * ig_loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), opt_cfg["max_grad_norm"])
            optimizer.step()
            optimizer.zero_grad()

            total_loss += float(loss.item())
            steps += 1
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        avg_loss = total_loss / max(steps, 1)

        val_results = validate(model, test_loader, label_mapping, threshold=0.0)
        epoch_sector_metrics.append(val_results["sector_metrics"])
        epoch_ig_when_sector_metrics.append(val_results["ig_when_sector_metrics"])
        epoch_ig_overall_metrics.append(val_results["ig_overall_metrics"])

        print(
            f"Epoch {epoch}/{num_epochs} | Loss: {avg_loss:.4f} | "
            f"Sector Acc: {val_results['sector_acc']:.4f} | "
            f"IG@Sector F1: {val_results['ig_when_sector_metrics']['f1']:.4f}"
        )

    # ── Threshold Evaluation ──────────────────────────────
    print("\n" + "=" * 80)
    print("Threshold Evaluation (on test set)")
    print("=" * 80)
    header = (
        f"{'Threshold':>10} {'Sector Acc':>11} {'IG@Sector F1':>13} "
        f"{'IG@Sector Prec':>15} {'IG@Sector Rec':>14} {'IG@Sector Acc':>14}"
    )
    print(header)
    print("-" * 80)

    threshold_results: list[dict] = []
    for thresh in eval_cfg["thresholds"]:
        vr = validate(model, test_loader, label_mapping, threshold=thresh)
        ig_ws = vr["ig_when_sector_metrics"]
        print(
            f"{thresh:>10.1f} {vr['sector_acc']:>11.4f} {ig_ws['f1']:>13.4f} "
            f"{ig_ws['precision']:>15.4f} {ig_ws['recall']:>14.4f} {ig_ws['accuracy']:>14.4f}"
        )
        threshold_results.append({"threshold": thresh, **ig_ws})
    print("=" * 80)

    best_threshold = max(threshold_results, key=lambda x: x["f1"])["threshold"]
    print(f"\nBest threshold: {best_threshold} (IG@Sector F1={max(r['f1'] for r in threshold_results):.4f})")

    # ── 시각화 저장 ──────────────────────────────────────
    plot_training_metrics(
        epoch_sector_metrics,
        epoch_ig_when_sector_metrics,
        epoch_ig_overall_metrics,
        ARTIFACT_DIR,
    )

    # ── 라벨 매핑 저장 ──────────────────────────────────
    save_json(
        LABEL_MAP_PATH,
        {
            "sector_label2id": label_mapping.sector_label2id,
            "sector_id2label": {str(k): v for k, v in label_mapping.sector_id2label.items()},
            "ig_label2id": label_mapping.ig_label2id,
            "ig_id2label": {str(k): v for k, v in label_mapping.ig_id2label.items()},
            "sector_to_ig_mask": {str(k): v for k, v in label_mapping.sector_to_ig_mask.items()},
        },
    )

    # ── 체크포인트 저장 ──────────────────────────────────
    torch.save(model.state_dict(), CHECKPOINT_DIR / "model.pt")
    tokenizer.save_pretrained(CHECKPOINT_DIR)

    save_json(
        ARTIFACT_DIR / "train_config.json",
        {
            "model_name": training["model_name"],
            "load_from_ic2": training.get("load_from_ic2", True),
            "epochs": num_epochs,
            "batch_size": training["batch_size"],
            "learning_rate": training["learning_rate"],
            "max_length": training["max_length"],
            "checkpoint_dir": str(CHECKPOINT_DIR.relative_to(ROOT_DIR)),
            "loss_weights": {
                "sector": loss_cfg["sector_loss_weight"],
                "ig": loss_cfg["ig_loss_weight"],
            },
            "class_weight_clipping": loss_cfg["class_weight_clipping"],
            "thresholds": eval_cfg["thresholds"],
            "best_threshold": best_threshold,
        },
    )
    print(f"\nTraining complete. Checkpoint saved to {CHECKPOINT_DIR}")


if __name__ == "__main__":
    main()
