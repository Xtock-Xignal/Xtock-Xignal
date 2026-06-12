"""
GICS Model Comparison: IPTC (checkpoint) vs IC2 (checkpoint)
===============================================================
Loads fine-tuned checkpoints for both models and compares on GICS labels:

  Model A: classla/multilingual-IPTC-news-topic-classifier
    → HierarchicalBertModel (shared backbone + 2 heads)
    → Checkpoint: IPTC/artifacts/checkpoint/model.pt

  Model B: BAAI/bge-m3 (fine-tuned via IC2/fine_tune.py)
    → GICSBertModel (BGE-M3 backbone + 2 heads)
    → Checkpoint: IC2/train_history/checkpoint/model.pt

If a checkpoint is missing, that model is skipped gracefully.

Usage:
  python evaluate/compare_models.py
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from IPTC.runtime import (
    HierarchicalBertModel,
    compute_sub_class_weights,
)
from utils.util_modeling import (
    NEWS_CSV,
    GICSSample,
    load_gics_dataset,
)
from utils.util_eval import precision_recall_f1

# ── Checkpoint paths ────────────────────────────────
IPTC_CHECKPOINT = ROOT_DIR / "IPTC" / "artifacts" / "checkpoint" / "model.pt"
IPTC_CHECKPOINT_DIR = IPTC_CHECKPOINT.parent
IPTC_LABEL_MAP = ROOT_DIR / "IPTC" / "artifacts" / "labels.json"

IC2_CHECKPOINT = ROOT_DIR / "IC2" / "train_history" / "checkpoint" / "model.pt"
IC2_CHECKPOINT_DIR = IC2_CHECKPOINT.parent
IC2_TRAIN_CONFIG = ROOT_DIR / "IC2" / "train_history" / "train_config.json"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ──────────────────────────────────────────────
# GICS label mapping (sector → industry_group)
# ──────────────────────────────────────────────

@dataclass
class GICSLabelMapping:
    """sector (big) / industry_group (sub) 양방향 매핑 + sector→ig 후보 마스크."""
    sector_label2id: dict[str, int]
    sector_id2label: dict[int, str]
    ig_label2id: dict[str, int]
    ig_id2label: dict[int, str]
    sector_to_ig_mask: dict[int, list[int]]  # sector_id → [ig_id, ...]

    @property
    def num_sectors(self) -> int:
        return len(self.sector_label2id)

    @property
    def num_industry_groups(self) -> int:
        return len(self.ig_label2id)


def build_gics_label_mapping(samples: list[GICSSample]) -> GICSLabelMapping:
    """GICSSample 목록에서 sector → industry_group 매핑을 구축한다."""
    sectors = sorted({s.sector for s in samples})
    igs = sorted({s.industry_group for s in samples})

    sector_label2id = {s: i for i, s in enumerate(sectors)}
    sector_id2label = {i: s for s, i in sector_label2id.items()}
    ig_label2id = {s: i for i, s in enumerate(igs)}
    ig_id2label = {i: s for s, i in ig_label2id.items()}

    # sector → industry_group 후보 마스크 (샘플 데이터에서 추론)
    sector_to_ig_mask: dict[int, list[int]] = {i: [] for i in range(len(sectors))}
    for s in samples:
        sec_id = sector_label2id[s.sector]
        ig_id = ig_label2id[s.industry_group]
        if ig_id not in sector_to_ig_mask[sec_id]:
            sector_to_ig_mask[sec_id].append(ig_id)

    return GICSLabelMapping(
        sector_label2id=sector_label2id,
        sector_id2label=sector_id2label,
        ig_label2id=ig_label2id,
        ig_id2label=ig_id2label,
        sector_to_ig_mask=sector_to_ig_mask,
    )


# ──────────────────────────────────────────────
# GICS stratified split
# ──────────────────────────────────────────────

def gics_stratified_split(
    samples: list[GICSSample],
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[GICSSample], list[GICSSample]]:
    """sector 기준으로 stratified split."""
    import random
    rng = random.Random(seed)
    grouped: dict[str, list[GICSSample]] = defaultdict(list)
    for s in samples:
        grouped[s.sector].append(s)

    train: list[GICSSample] = []
    test: list[GICSSample] = []

    for group in grouped.values():
        group = list(group)
        rng.shuffle(group)
        if len(group) == 1:
            train.extend(group)
            continue
        n_test = max(1, int(round(len(group) * test_ratio)))
        n_test = min(n_test, len(group) - 1)
        test.extend(group[:n_test])
        train.extend(group[n_test:])

    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


# ──────────────────────────────────────────────
# Dataset
# ──────────────────────────────────────────────

class GICSBertDataset:
    """sector, industry_group 두 라벨을 반환하는 데이터셋."""

    def __init__(
        self,
        texts: list[str],
        sector_labels: list[int],
        ig_labels: list[int],
        tokenizer,
        max_length: int = 256,
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


# ──────────────────────────────────────────────
# IPTC checkpoint loading & evaluation
# ──────────────────────────────────────────────

def load_iptc_from_checkpoint(
    label_mapping: GICSLabelMapping,
) -> HierarchicalBertModel | None:
    """IPTC 체크포인트를 로드한다. 없으면 None 반환."""
    if not IPTC_CHECKPOINT.exists():
        print(f"  ⚠ IPTC checkpoint not found: {IPTC_CHECKPOINT}")
        return None

    model = HierarchicalBertModel(
        model_name="classla/multilingual-IPTC-news-topic-classifier",
        num_big_sectors=label_mapping.num_sectors,
        num_sub_sectors=label_mapping.num_industry_groups,
        big_to_sub_mask=label_mapping.sector_to_ig_mask,
    )
    state = torch.load(IPTC_CHECKPOINT, map_location=DEVICE)
    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()
    print(f"  ✅ IPTC checkpoint loaded: {IPTC_CHECKPOINT}")
    return model


@torch.no_grad()
def evaluate_iptc_gics(
    model: HierarchicalBertModel,
    loader: DataLoader,
    label_mapping: GICSLabelMapping,
) -> tuple[float, float, dict]:
    """GICS IPTC 모델 평가. (sector_acc, ig_acc_when_sector_correct, detailed_metrics) 반환"""
    model.eval()
    all_sector_true: list[str] = []
    all_sector_pred: list[str] = []
    all_ig_true: list[str] = []
    all_ig_pred: list[str] = []

    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)

        sector_pred_ids, ig_pred_ids = model.predict_hierarchical(
            input_ids, attention_mask, threshold=0.0,
        )

        sector_true_ids = batch["big_labels"].numpy()
        ig_true_ids = batch["sub_labels"].numpy()

        for i in range(len(sector_true_ids)):
            all_sector_true.append(label_mapping.sector_id2label[int(sector_true_ids[i])])
            all_sector_pred.append(label_mapping.sector_id2label[int(sector_pred_ids[i].item())])
            all_ig_true.append(label_mapping.ig_id2label[int(ig_true_ids[i])])
            ig_id = int(ig_pred_ids[i].item())
            all_ig_pred.append("__NONE__" if ig_id == -1 else label_mapping.ig_id2label[ig_id])

    n = len(all_sector_true)
    sector_acc = sum(1 for t, p in zip(all_sector_true, all_sector_pred) if t == p) / max(n, 1)

    # industry group when sector correct
    swb_true = [it for st, sp, it in zip(all_sector_true, all_sector_pred, all_ig_true) if st == sp]
    swb_pred = [ip for st, sp, ip in zip(all_sector_true, all_sector_pred, all_ig_pred) if st == sp]
    ig_when_sector_acc = sum(1 for t, p in zip(swb_true, swb_pred) if t == p) / max(len(swb_true), 1) if swb_true else 0.0

    # industry group overall
    ig_overall_acc = sum(1 for t, p in zip(all_ig_true, all_ig_pred) if t == p) / max(n, 1)
    ig_overall_f1 = precision_recall_f1(all_ig_true, all_ig_pred)["f1"]

    return sector_acc, ig_when_sector_acc, {
        "sector_acc": round(sector_acc, 4),
        "ig_when_sector_acc": round(ig_when_sector_acc, 4),
        "ig_overall_acc": round(ig_overall_acc, 4),
        "ig_overall_f1": round(ig_overall_f1, 4),
        "samples": n,
    }


# ──────────────────────────────────────────────
# IC2 checkpoint loading & evaluation
# ──────────────────────────────────────────────

def load_ic2_from_checkpoint(
    label_mapping: GICSLabelMapping,
) -> nn.Module | None:
    """IC2 (GICSBertModel) 체크포인트를 로드한다. 없으면 None 반환."""
    if not IC2_CHECKPOINT.exists():
        print(f"  ⚠ IC2 checkpoint not found: {IC2_CHECKPOINT}")
        return None

    from IC2.fine_tune import GICSBertModel

    model = GICSBertModel(
        model_name="BAAI/bge-m3",
        num_sectors=label_mapping.num_sectors,
        num_igs=label_mapping.num_industry_groups,
        sector_to_ig_mask=label_mapping.sector_to_ig_mask,
        load_from_ic2=False,  # checkpoint has trained weights, no init needed
    )
    state = torch.load(IC2_CHECKPOINT, map_location=DEVICE)
    model.load_state_dict(state)
    model.to(DEVICE)
    model.eval()
    print(f"  ✅ IC2 checkpoint loaded: {IC2_CHECKPOINT}")
    return model


@torch.no_grad()
def evaluate_ic2_checkpoint(
    model: nn.Module,
    loader: DataLoader,
    label_mapping: GICSLabelMapping,
) -> tuple[float, float, dict]:
    """IC2 fine-tuned 모델 평가. (sector_acc, ig_acc_when_sector_correct, detailed_metrics) 반환"""
    model.eval()
    all_sector_true: list[str] = []
    all_sector_pred: list[str] = []
    all_ig_true: list[str] = []
    all_ig_pred: list[str] = []

    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)

        sector_pred_ids, ig_pred_ids = model.predict_hierarchical(
            input_ids, attention_mask, threshold=0.0,
        )

        sector_true_ids = batch["big_labels"].numpy()
        ig_true_ids = batch["sub_labels"].numpy()

        for i in range(len(sector_true_ids)):
            all_sector_true.append(label_mapping.sector_id2label[int(sector_true_ids[i])])
            all_sector_pred.append(label_mapping.sector_id2label[int(sector_pred_ids[i].item())])
            all_ig_true.append(label_mapping.ig_id2label[int(ig_true_ids[i])])
            ig_id = int(ig_pred_ids[i].item())
            all_ig_pred.append("__NONE__" if ig_id == -1 else label_mapping.ig_id2label[ig_id])

    n = len(all_sector_true)
    sector_acc = sum(1 for t, p in zip(all_sector_true, all_sector_pred) if t == p) / max(n, 1)

    # industry group when sector correct
    swb_true = [it for st, sp, it in zip(all_sector_true, all_sector_pred, all_ig_true) if st == sp]
    swb_pred = [ip for st, sp, ip in zip(all_sector_true, all_sector_pred, all_ig_pred) if st == sp]
    ig_when_sector_acc = sum(1 for t, p in zip(swb_true, swb_pred) if t == p) / max(len(swb_true), 1) if swb_true else 0.0

    # industry group overall
    ig_overall_acc = sum(1 for t, p in zip(all_ig_true, all_ig_pred) if t == p) / max(n, 1)
    ig_overall_f1 = precision_recall_f1(all_ig_true, all_ig_pred)["f1"]

    return sector_acc, ig_when_sector_acc, {
        "sector_acc": round(sector_acc, 4),
        "ig_when_sector_acc": round(ig_when_sector_acc, 4),
        "ig_overall_acc": round(ig_overall_acc, 4),
        "ig_overall_f1": round(ig_overall_f1, 4),
        "samples": n,
    }


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def print_separator(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def create_test_loader(
    test_samples: list[GICSSample],
    label_mapping: GICSLabelMapping,
    tokenizer,
    max_length: int,
    batch_size: int = 8,
) -> DataLoader:
    """GICS test samples → DataLoader"""
    dataset = GICSBertDataset(
        texts=[s.text for s in test_samples],
        sector_labels=[label_mapping.sector_label2id[s.sector] for s in test_samples],
        ig_labels=[label_mapping.ig_label2id[s.industry_group] for s in test_samples],
        tokenizer=tokenizer,
        max_length=max_length,
    )
    return DataLoader(dataset, batch_size=batch_size)


def main():
    print(f"Device: {DEVICE}")
    print(f"PyTorch: {torch.__version__}")

    # ── Load dataset ──
    print_separator("Loading GICS Dataset")
    samples = load_gics_dataset(NEWS_CSV)
    print(f"  Total samples: {len(samples)}")
    print(f"  Sectors: {len({s.sector for s in samples})}")
    print(f"  Industry groups: {len({s.industry_group for s in samples})}")

    label_mapping = build_gics_label_mapping(samples)
    print(f"  Sector classes: {label_mapping.num_sectors}")
    print(f"  Industry group classes: {label_mapping.num_industry_groups}")

    for sec_id in range(label_mapping.num_sectors):
        sec_name = label_mapping.sector_id2label[sec_id]
        ig_ids = label_mapping.sector_to_ig_mask[sec_id]
        ig_names = [label_mapping.ig_id2label[i] for i in ig_ids]
        print(f"    {sec_name}: {ig_names}")

    # Stratified split (80/20)
    train_samples, test_samples = gics_stratified_split(samples, test_ratio=0.2, seed=42)
    print(f"  Train: {len(train_samples)} | Test: {len(test_samples)}")

    # Industry group class weights (for reference)
    all_ig_ids = [label_mapping.ig_label2id[s.industry_group] for s in samples]
    ig_class_weights = compute_sub_class_weights(
        all_ig_ids,
        label_mapping.num_industry_groups,
        clipping=5.0,
    )
    _ = ig_class_weights  # available if needed

    # ── Track which models are evaluated ──
    iptc_metrics = None
    ic2_metrics = None

    # ─────────────────────────────────────────────
    # IPTC Model Evaluation
    # ─────────────────────────────────────────────
    print_separator("IPTC Model (checkpoint)")
    iptc_model = load_iptc_from_checkpoint(label_mapping)

    if iptc_model is not None:
        iptc_tokenizer = AutoTokenizer.from_pretrained(
            "classla/multilingual-IPTC-news-topic-classifier",
        )
        iptc_loader = create_test_loader(
            test_samples, label_mapping, iptc_tokenizer,
            max_length=256, batch_size=8,
        )
        t0 = time.time()
        iptc_sector_acc, iptc_ig_acc, iptc_metrics = evaluate_iptc_gics(
            iptc_model, iptc_loader, label_mapping,
        )
        eval_time = time.time() - t0
        for k, v in iptc_metrics.items():
            print(f"  {k}: {v}")
        print(f"  Evaluation time: {eval_time:.1f}s")
    else:
        print("  Skipping IPTC evaluation.")

    # ─────────────────────────────────────────────
    # IC2 Model Evaluation
    # ─────────────────────────────────────────────
    print_separator("IC2 Model (checkpoint)")
    ic2_model = load_ic2_from_checkpoint(label_mapping)

    if ic2_model is not None:
        ic2_tokenizer = AutoTokenizer.from_pretrained(str(IC2_CHECKPOINT_DIR))
        ic2_loader = create_test_loader(
            test_samples, label_mapping, ic2_tokenizer,
            max_length=512, batch_size=8,
        )
        t0 = time.time()
        ic2_sector_acc, ic2_ig_acc, ic2_metrics = evaluate_ic2_checkpoint(
            ic2_model, ic2_loader, label_mapping,
        )
        eval_time = time.time() - t0
        for k, v in ic2_metrics.items():
            print(f"  {k}: {v}")
        print(f"  Evaluation time: {eval_time:.1f}s")
    else:
        print("  Skipping IC2 evaluation.")

    # ─────────────────────────────────────────────
    # Comparison Summary (if both available)
    # ─────────────────────────────────────────────
    have_iptc = iptc_metrics is not None
    have_ic2 = ic2_metrics is not None

    if have_iptc and have_ic2:
        print_separator("COMPARISON SUMMARY (GICS Labels)")
        print(f"\n  {'Metric':<50s} {'IPTC':>10s} {'IC2':>12s}")
        print(f"  {'-'*50} {'-'*10} {'-'*12}")
        print(f"  {'Sector accuracy':<50s} {iptc_metrics['sector_acc']:>10.4f} {ic2_metrics['sector_acc']:>12.4f}")
        print(f"  {'Industry group (when sector correct)':<50s} {iptc_metrics['ig_when_sector_acc']:>10.4f} {ic2_metrics['ig_when_sector_acc']:>12.4f}")
        print(f"  {'Industry group overall accuracy':<50s} {iptc_metrics['ig_overall_acc']:>10.4f} {ic2_metrics['ig_overall_acc']:>12.4f}")
        print(f"  {'Industry group overall F1':<50s} {iptc_metrics['ig_overall_f1']:>10.4f} {ic2_metrics['ig_overall_f1']:>12.4f}")
        print(f"\n  {'─'*50} {'─'*10} {'─'*12}")
        print(f"  {'Total test samples':<50s} {iptc_metrics['samples']:>10d} {ic2_metrics['samples']:>12d}")

        # Verdict
        print_separator("VERDICT")
        if iptc_metrics['sector_acc'] >= ic2_metrics['sector_acc'] and iptc_metrics['ig_overall_acc'] >= ic2_metrics['ig_overall_acc']:
            print("  ✅ IPTC performs better on GICS labels.")
        else:
            print("  ✅ IC2 (fine-tuned) performs better on GICS labels.")
    elif have_iptc:
        print_separator("IPTC ONLY — Summary")
        print(f"  Sector accuracy: {iptc_metrics['sector_acc']:.4f}")
        print(f"  IG overall accuracy: {iptc_metrics['ig_overall_acc']:.4f}")
        print(f"  IG overall F1: {iptc_metrics['ig_overall_f1']:.4f}")
    elif have_ic2:
        print_separator("IC2 ONLY — Summary")
        print(f"  Sector accuracy: {ic2_metrics['sector_acc']:.4f}")
        print(f"  IG overall accuracy: {ic2_metrics['ig_overall_acc']:.4f}")
        print(f"  IG overall F1: {ic2_metrics['ig_overall_f1']:.4f}")
    else:
        print_separator("NO CHECKPOINTS FOUND")
        print("  Run IPTC/train.py and/or IC2/fine_tune.py first to create checkpoints.")


if __name__ == "__main__":
    main()
