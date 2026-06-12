"""
GICS Model Analysis: detailed metrics, confusion matrices, confidence distributions.

Computes:
  1. Sector/IG accuracy, weighted F1, macro F1 (both models)
  2. Sector confusion matrices (IPTC + IC2)
  3. IC2 per-sector accuracy, top-3 accuracy, confidence distribution
"""

from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from IC2.industry_model import (
    BAAI_TO_BIG_SECTOR,
    BAAI_TO_INDUSTRY_GROUP,
    IndustryCorpus2Classifier,
)
from evaluate.compare_models import (
    GICSLabelMapping,
    GICSBertDataset,
    TRAIN_CONFIG,
    DEVICE,
    build_gics_label_mapping,
    gics_stratified_split,
    evaluate_iptc_gics,
    train_iptc_gics,
)
from IPTC.runtime import compute_sub_class_weights
from utils.util_modeling import NEWS_CSV, load_gics_dataset

FIGS_DIR = ROOT_DIR / "figures"
FIGS_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# Detailed IPTC evaluation (per-sample)
# ──────────────────────────────────────────────

@torch.no_grad()
def evaluate_iptc_detailed(
    model: nn.Module,
    loader: DataLoader,
    label_mapping: GICSLabelMapping,
) -> dict:
    """IPTC per-sample detailed evaluation.

    Returns dict with per-sample predictions and aggregated metrics.
    """
    model.eval()
    records = []

    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)

        # Get logits for confidence
        big_logits, sub_logits = model(input_ids, attention_mask)
        big_probs = torch.softmax(big_logits, dim=-1)
        sub_probs = torch.softmax(sub_logits, dim=-1)

        # Mask sub_probs with sector_to_ig_mask
        sector_pred_ids = torch.argmax(big_logits, dim=-1)
        batch_size = sub_probs.size(0)
        mask = torch.zeros_like(sub_probs)
        for i in range(batch_size):
            b_id = int(sector_pred_ids[i].item())
            valid_ids = label_mapping.sector_to_ig_mask.get(b_id, [])
            if valid_ids:
                mask[i, valid_ids] = 1.0
        masked_sub_probs = sub_probs * mask
        ig_pred_ids = torch.argmax(masked_sub_probs, dim=-1)

        big_true_ids = batch["big_labels"].numpy()
        ig_true_ids = batch["sub_labels"].numpy()

        for i in range(len(big_true_ids)):
            sector_true = label_mapping.sector_id2label[int(big_true_ids[i])]
            sector_pred = label_mapping.sector_id2label[int(sector_pred_ids[i].item())]
            ig_true = label_mapping.ig_id2label[int(ig_true_ids[i])]
            ig_pred_id = int(ig_pred_ids[i].item())
            ig_pred = label_mapping.ig_id2label[ig_pred_id] if ig_pred_id != -1 else "__NONE__"

            records.append({
                "sector_true": sector_true,
                "sector_pred": sector_pred,
                "ig_true": ig_true,
                "ig_pred": ig_pred,
                "sector_conf": float(big_probs[i, sector_pred_ids[i]].item()),
                "ig_conf": float(masked_sub_probs[i, ig_pred_id].item()) if ig_pred_id != -1 else 0.0,
            })

    return _compute_metrics_from_records(records, label_mapping, records)


# ──────────────────────────────────────────────
# Detailed IC2 evaluation (per-sample)
# ──────────────────────────────────────────────

@torch.no_grad()
def evaluate_ic2_detailed(
    model: IndustryCorpus2Classifier,
    samples: list,
    label_mapping: GICSLabelMapping,
) -> dict:
    """IC2 per-sample detailed evaluation with confidence and top-3.

    Returns dict with per-sample records, aggregated metrics, and confidence distributions.
    """
    records = []
    all_scores = []

    # For top-3: get softmax over 31 categories, map each to candidates
    for sample in tqdm(samples, desc="IC2 Detailed"):
        # Full softmax for top-3
        encoded = model.tokenizer(
            [sample.text],
            padding=False,
            max_length=2048,
            truncation=True,
            return_tensors="pt",
        )
        encoded = {k: v.to(model.device) for k, v in encoded.items()}
        outputs = model.model(**encoded)
        probs = torch.softmax(outputs.logits, dim=-1)[0]  # 31-dim

        # Top-1 prediction
        top1_id = int(torch.argmax(probs))
        top1_label = model.id2label[top1_id]
        top1_en = model.BAAI_LABEL_EN.get(top1_label, top1_label) if hasattr(model, 'BAAI_LABEL_EN') else (getattr(model, 'BAAI_LABEL_EN') if hasattr(model, 'BAAI_LABEL_EN') else model.id2label[top1_id])
        pass

    # Proper implementation with BAAI_LABEL_EN access
    model_ref = model
    baai_label_en = sys.modules['bert.industry_model'].BAAI_LABEL_EN

    for sample in tqdm(samples, desc="IC2 Detailed"):
        encoded = model.tokenizer(
            [sample.text],
            padding=False,
            max_length=2048,
            truncation=True,
            return_tensors="pt",
        )
        encoded = {k: v.to(model.device) for k, v in encoded.items()}
        outputs = model.model(**encoded)
        probs = torch.softmax(outputs.logits, dim=-1)[0]

        # Get top-3 BAAI category indices
        top3_ids = torch.topk(probs, k=min(3, len(probs))).indices.tolist()
        top3_probs = torch.topk(probs, k=min(3, len(probs))).values.tolist()

        # Top-1
        top1_id = top3_ids[0]
        top1_label = model.id2label[top1_id]
        top1_en = baai_label_en.get(top1_label, top1_label)

        # Map to sector candidates
        sector_candidates = BAAI_TO_BIG_SECTOR.get(top1_en, set())
        sector_pred = next(iter(sector_candidates)) if sector_candidates else "__UNMAPPED__"
        ig_candidates = BAAI_TO_INDUSTRY_GROUP.get(top1_en, set())
        ig_pred = next(iter(ig_candidates)) if ig_candidates else "__UNMAPPED__"

        # Top-3 sector recall: is true sector in ANY top-3 candidate set?
        top3_sector_hit = False
        top3_ig_hit = False
        for tid in top3_ids:
            t_label = model.id2label[tid]
            t_en = baai_label_en.get(t_label, t_label)
            sec_cands = BAAI_TO_BIG_SECTOR.get(t_en, set())
            ig_cands = BAAI_TO_INDUSTRY_GROUP.get(t_en, set())
            if sample.sector in sec_cands:
                top3_sector_hit = True
            if sample.industry_group in ig_cands:
                top3_ig_hit = True

        confidence = float(probs[top1_id].item())

        records.append({
            "sector_true": sample.sector,
            "sector_pred": sector_pred,
            "ig_true": sample.industry_group,
            "ig_pred": ig_pred,
            "sector_conf": confidence,
            "ig_conf": confidence,  # Same model-level confidence
            "top3_sector_hit": top3_sector_hit,
            "top3_ig_hit": top3_ig_hit,
            "top1_en": top1_en,
            "top1_prob": confidence,
            "mapped": sector_candidates or ig_candidates,
        })
        all_scores.append(confidence)

    return _compute_metrics_from_records(records, label_mapping, all_scores)


# ──────────────────────────────────────────────
# Metrics computation
# ──────────────────────────────────────────────

def _compute_metrics_from_records(records, label_mapping, all_scores_or_records):
    """Compute all metrics from per-sample records."""
    n = len(records)
    if n == 0:
        return {"error": "no records"}

    sector_true = [r["sector_true"] for r in records]
    sector_pred = [r["sector_pred"] for r in records]
    ig_true = [r["ig_true"] for r in records]
    ig_pred = [r["ig_pred"] for r in records]

    # Sector accuracy
    sector_acc = sum(1 for t, p in zip(sector_true, sector_pred) if t == p) / n

    # IG when sector correct
    swb_true = [it for st, sp, it in zip(sector_true, sector_pred, ig_true) if st == sp]
    swb_pred = [ip for st, sp, ip in zip(sector_true, sector_pred, ig_pred) if st == sp]
    ig_when_sector_acc = sum(1 for t, p in zip(swb_true, swb_pred) if t == p) / max(len(swb_true), 1) if swb_true else 0.0

    # IG overall accuracy
    ig_overall_acc = sum(1 for t, p in zip(ig_true, ig_pred) if t == p) / n

    # Weighted F1 (weighted by class support)
    sector_weighted_f1 = f1_score(sector_true, sector_pred, average="weighted", zero_division=0)
    ig_weighted_f1 = f1_score(ig_true, ig_pred, average="weighted", zero_division=0)

    # Macro F1 (unweighted average across classes)
    sector_macro_f1 = f1_score(sector_true, sector_pred, average="macro", zero_division=0)
    ig_macro_f1 = f1_score(ig_true, ig_pred, average="macro", zero_division=0)

    # Per-sector accuracy
    sectors = sorted(set(sector_true))
    per_sector_correct = defaultdict(int)
    per_sector_total = defaultdict(int)
    for t, p in zip(sector_true, sector_pred):
        per_sector_total[t] += 1
        if t == p:
            per_sector_correct[t] += 1
    per_sector_acc = {s: per_sector_correct[s] / max(per_sector_total[s], 1) for s in sectors}

    # Confidence stats
    correct_confs = [r["sector_conf"] for r in records if r["sector_true"] == r["sector_pred"]]
    wrong_confs = [r["sector_conf"] for r in records if r["sector_true"] != r["sector_pred"]]

    result = {
        "sector_acc": round(sector_acc, 4),
        "ig_when_sector_acc": round(ig_when_sector_acc, 4),
        "ig_overall_acc": round(ig_overall_acc, 4),
        "sector_weighted_f1": round(sector_weighted_f1, 4),
        "ig_weighted_f1": round(ig_weighted_f1, 4),
        "sector_macro_f1": round(sector_macro_f1, 4),
        "ig_macro_f1": round(ig_macro_f1, 4),
        "samples": n,
        "per_sector_accuracy": per_sector_acc,
        "records": records,
        "conf_correct": correct_confs,
        "conf_wrong": wrong_confs,
        "conf_all": [r["sector_conf"] for r in records],
        "sector_labels": sectors,
        "sector_true": sector_true,
        "sector_pred": sector_pred,
        "ig_true": ig_true,
        "ig_pred": ig_pred,
    }

    # IC2-specific
    if "top3_sector_hit" in records[0]:
        result["top3_sector_hit"] = sum(1 for r in records if r["top3_sector_hit"]) / n
        result["top3_ig_hit"] = sum(1 for r in records if r["top3_ig_hit"]) / n
        result["mapped_count"] = sum(1 for r in records if r["mapped"])
        result["unmapped_count"] = sum(1 for r in records if not r["mapped"])
        result["coverage"] = result["mapped_count"] / n

    # Confusion matrix
    sector_names = sorted(set(sector_true) | set(sector_pred))
    result["sector_cm"] = confusion_matrix(
        sector_true, sector_pred,
        labels=sector_names,
    )
    result["sector_cm_labels"] = sector_names

    return result


# ──────────────────────────────────────────────
# Visualization
# ──────────────────────────────────────────────

def plot_comparison_bar(iptc_metrics, ic2_metrics, save_path: Path):
    """Grouped bar chart: sector acc, IG acc, weighted F1, macro F1."""
    metrics = ["Sector\nAccuracy", "IG\n(overall)\nAccuracy", "Sector\nWeighted F1", "IG\nWeighted F1", "Sector\nMacro F1", "IG\nMacro F1"]
    iptc_vals = [
        iptc_metrics["sector_acc"],
        iptc_metrics["ig_overall_acc"],
        iptc_metrics["sector_weighted_f1"],
        iptc_metrics["ig_weighted_f1"],
        iptc_metrics["sector_macro_f1"],
        iptc_metrics["ig_macro_f1"],
    ]
    ic2_vals = [
        ic2_metrics["sector_acc"],
        ic2_metrics["ig_overall_acc"],
        ic2_metrics["sector_weighted_f1"],
        ic2_metrics["ig_weighted_f1"],
        ic2_metrics["sector_macro_f1"],
        ic2_metrics["ig_macro_f1"],
    ]

    x = np.arange(len(metrics))
    w = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - w/2, iptc_vals, w, label="IPTC (retrained)", color="#4C72B0")
    bars2 = ax.bar(x + w/2, ic2_vals, w, label="IndustryCorpus2 (zero-shot)", color="#DD8452")

    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("IPTC vs IndustryCorpus2 — GICS Classification Performance", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.legend(fontsize=11)
    ax.set_ylim(0, 1.0)
    ax.axhline(y=0.0, color="gray", linewidth=0.5)

    # Value labels on bars
    for bar in bars1:
        h = bar.get_height()
        if h > 0.01:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.015, f"{h:.1%}", ha="center", va="bottom", fontsize=8, rotation=45)
    for bar in bars2:
        h = bar.get_height()
        if h > 0.01:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.015, f"{h:.1%}", ha="center", va="bottom", fontsize=8, rotation=45)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_confusion_matrix(cm, labels, title, save_path: Path, normalize=True):
    """Confusion matrix heatmap."""
    if normalize:
        cm_norm = cm.astype("float") / (cm.sum(axis=1, keepdims=True) + 1e-10)
        fmt = ".1%"
        annot = np.where(cm > 0, np.vectorize(lambda x: f"{x:.0f}")(cm), "")
    else:
        cm_norm = cm
        fmt = "d"

    fig, ax = plt.subplots(figsize=(10, 9))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)

    # Annotate with count (not percentage)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if cm[i, j] > 0:
                ax.text(j, i, str(int(cm[i, j])), ha="center", va="center", fontsize=7,
                        color="white" if cm_norm[i, j] > 0.5 else "black")

    ax.set_xlabel("Predicted", fontsize=11)
    ax.set_ylabel("True", fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    plt.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_per_sector_accuracy(ic2_records, iptc_records, save_path: Path):
    """Per-sector accuracy comparison bar chart."""
    sectors = sorted(set(r["sector_true"] for r in ic2_records) |
                     set(r["sector_true"] for r in iptc_records))

    ic2_acc = {}
    iptc_acc = {}
    for sec in sectors:
        ic2_sec = [r for r in ic2_records if r["sector_true"] == sec]
        iptc_sec = [r for r in iptc_records if r["sector_true"] == sec]
        ic2_acc[sec] = sum(1 for r in ic2_sec if r["sector_true"] == r["sector_pred"]) / max(len(ic2_sec), 1)
        iptc_acc[sec] = sum(1 for r in iptc_sec if r["sector_true"] == r["sector_pred"]) / max(len(iptc_sec), 1)

    x = np.arange(len(sectors))
    w = 0.35

    fig, ax = plt.subplots(figsize=(14, 6))
    bars1 = ax.bar(x - w/2, [iptc_acc[s] for s in sectors], w, label="IPTC", color="#4C72B0")
    bars2 = ax.bar(x + w/2, [ic2_acc[s] for s in sectors], w, label="IndustryCorpus2", color="#DD8452")

    ax.set_ylabel("Accuracy", fontsize=12)
    ax.set_title("Per-Sector Accuracy Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(sectors, rotation=45, ha="right", fontsize=9)
    ax.legend(fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.axhline(y=0.0, color="gray", linewidth=0.5)

    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.02, f"{h:.0%}", ha="center", va="bottom", fontsize=7)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 0.02, f"{h:.0%}", ha="center", va="bottom", fontsize=7)

    # Sample count per sector
    for i, sec in enumerate(sectors):
        n = sum(1 for r in ic2_records if r["sector_true"] == sec)
        ax.text(i, -0.08, f"n={n}", ha="center", va="top", fontsize=7, color="gray")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_confidence_distribution(ic2_metrics, save_path: Path):
    """Histogram of IC2 confidence for correct vs wrong predictions."""
    correct = ic2_metrics["conf_correct"]
    wrong = ic2_metrics["conf_wrong"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    axes[0].hist(correct, bins=20, color="#4C72B0", alpha=0.8, edgecolor="white")
    axes[0].set_title(f"Correct Predictions (n={len(correct)})", fontsize=12)
    axes[0].set_xlabel("Confidence (max softmax)", fontsize=10)
    axes[0].set_ylabel("Count", fontsize=10)
    axes[0].axvline(x=np.mean(correct) if correct else 0, color="red", linestyle="--",
                    label=f"mean={np.mean(correct):.2f}" if correct else "")

    axes[1].hist(wrong, bins=20, color="#DD8452", alpha=0.8, edgecolor="white")
    axes[1].set_title(f"Wrong Predictions (n={len(wrong)})", fontsize=12)
    axes[1].set_xlabel("Confidence (max softmax)", fontsize=10)
    axes[1].axvline(x=np.mean(wrong) if wrong else 0, color="red", linestyle="--",
                    label=f"mean={np.mean(wrong):.2f}" if wrong else "")

    for ax in axes:
        ax.legend(fontsize=9)

    fig.suptitle("IC2 Confidence Distribution: Correct vs Wrong", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {save_path}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def print_separator(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def main():
    print(f"Device: {DEVICE}")
    print(f"PyTorch: {torch.__version__}")

    # ── Load dataset ──
    print_separator("Loading GICS Dataset")
    samples = load_gics_dataset(NEWS_CSV)
    print(f"  Total samples: {len(samples)}")

    label_mapping = build_gics_label_mapping(samples)
    print(f"  Sectors: {label_mapping.num_sectors}")
    print(f"  Industry groups: {label_mapping.num_industry_groups}")

    train_samples, test_samples = gics_stratified_split(samples, test_ratio=0.2, seed=42)
    print(f"  Train: {len(train_samples)} | Test: {len(test_samples)}")

    # ── IPTC: retrain + evaluate ──
    print_separator("IPTC Model — Training")
    tokenizer = AutoTokenizer.from_pretrained(TRAIN_CONFIG["model_name"])
    train_dataset = GICSBertDataset(
        texts=[s.text for s in train_samples],
        sector_labels=[label_mapping.sector_label2id[s.sector] for s in train_samples],
        ig_labels=[label_mapping.ig_label2id[s.industry_group] for s in train_samples],
        tokenizer=tokenizer,
        max_length=TRAIN_CONFIG["max_length"],
    )
    test_dataset = GICSBertDataset(
        texts=[s.text for s in test_samples],
        sector_labels=[label_mapping.sector_label2id[s.sector] for s in test_samples],
        ig_labels=[label_mapping.ig_label2id[s.industry_group] for s in test_samples],
        tokenizer=tokenizer,
        max_length=TRAIN_CONFIG["max_length"],
    )
    train_loader = DataLoader(train_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=TRAIN_CONFIG["batch_size"])

    all_ig_ids = [label_mapping.ig_label2id[s.industry_group] for s in samples]
    ig_class_weights = compute_sub_class_weights(
        all_ig_ids,
        label_mapping.num_industry_groups,
        TRAIN_CONFIG["class_weight_clipping"],
    )

    t0 = time.time()
    iptc_model = train_iptc_gics(train_loader, test_loader, label_mapping, ig_class_weights)
    iptc_train_time = time.time() - t0
    print(f"  Training time: {iptc_train_time:.1f}s")

    # IPTC detailed evaluation
    print_separator("IPTC Model — Detailed Evaluation")
    iptc_metrics = evaluate_iptc_detailed(iptc_model, test_loader, label_mapping)
    print(f"  Sector acc: {iptc_metrics['sector_acc']:.4f}")
    print(f"  IG overall acc: {iptc_metrics['ig_overall_acc']:.4f}")
    print(f"  Sector weighted F1: {iptc_metrics['sector_weighted_f1']:.4f}")
    print(f"  Sector macro F1: {iptc_metrics['sector_macro_f1']:.4f}")
    print(f"  IG weighted F1: {iptc_metrics['ig_weighted_f1']:.4f}")
    print(f"  IG macro F1: {iptc_metrics['ig_macro_f1']:.4f}")

    # ── IC2: load + evaluate ──
    print_separator("IndustryCorpus2 — Load & Detailed Evaluation")
    t0 = time.time()
    ic2_model = IndustryCorpus2Classifier()
    print(f"  Load time: {time.time() - t0:.1f}s")

    t0 = time.time()
    ic2_metrics = evaluate_ic2_detailed(ic2_model, test_samples, label_mapping)
    print(f"  Evaluation time: {time.time() - t0:.1f}s")
    print(f"  Sector acc: {ic2_metrics['sector_acc']:.4f}")
    print(f"  IG overall acc: {ic2_metrics['ig_overall_acc']:.4f}")
    print(f"  Sector weighted F1: {ic2_metrics['sector_weighted_f1']:.4f}")
    print(f"  Sector macro F1: {ic2_metrics['sector_macro_f1']:.4f}")
    print(f"  Coverage: {ic2_metrics['coverage']:.4f}")
    print(f"  Top-3 sector hit: {ic2_metrics.get('top3_sector_hit', 0):.4f}")
    print(f"  Top-3 IG hit: {ic2_metrics.get('top3_ig_hit', 0):.4f}")

    # ── Print comparison table ──
    print_separator("COMPARISON TABLE")
    print(f"\n  {'Metric':<50s} {'IPTC':>10s} {'IC2':>12s}")
    print(f"  {'-'*50} {'-'*10} {'-'*12}")
    rows = [
        ("Sector accuracy", iptc_metrics["sector_acc"], ic2_metrics["sector_acc"]),
        ("IG overall accuracy", iptc_metrics["ig_overall_acc"], ic2_metrics["ig_overall_acc"]),
        ("IG when sector correct", iptc_metrics["ig_when_sector_acc"], ic2_metrics.get("ig_when_sector_acc", 0)),
        ("Sector weighted F1", iptc_metrics["sector_weighted_f1"], ic2_metrics["sector_weighted_f1"]),
        ("Sector macro F1", iptc_metrics["sector_macro_f1"], ic2_metrics["sector_macro_f1"]),
        ("IG weighted F1", iptc_metrics["ig_weighted_f1"], ic2_metrics["ig_weighted_f1"]),
        ("IG macro F1", iptc_metrics["ig_macro_f1"], ic2_metrics["ig_macro_f1"]),
        ("Coverage (mapped %)", 1.0, ic2_metrics["coverage"]),
        ("Top-3 sector recall", 0.0, ic2_metrics.get("top3_sector_hit", 0)),
        ("Top-3 IG recall", 0.0, ic2_metrics.get("top3_ig_hit", 0)),
    ]
    for name, iptc_v, ic2_v in rows:
        print(f"  {name:<50s} {iptc_v:>10.4f} {ic2_v:>12.4f}")
    print(f"  {'Samples':<50s} {iptc_metrics['samples']:>10d} {ic2_metrics['samples']:>12d}")
    iptc_mapped = f"{iptc_metrics['samples']} / 0"
    ic2_mapped_count = ic2_metrics.get('mapped_count', 0)
    ic2_unmapped_count = ic2_metrics.get('unmapped_count', 0)
    ic2_mapped = f"{ic2_mapped_count} / {ic2_unmapped_count}"
    print(f"  {'Mapped / Unmapped':<50s} {iptc_mapped:>10s} {ic2_mapped:>12s}")

    # ── Per-sector accuracy ──
    print_separator("PER-SECTOR ACCURACY (IC2)")
    for sec in sorted(ic2_metrics["per_sector_accuracy"]):
        acc = ic2_metrics["per_sector_accuracy"][sec]
        n = sum(1 for r in ic2_metrics["records"] if r["sector_true"] == sec)
        print(f"  {sec:45s} {acc:.1%} (n={n})")

    # ── Generate figures ──
    print_separator("Generating Figures")
    plot_comparison_bar(iptc_metrics, ic2_metrics, FIGS_DIR / "comparison_bar.png")

    # Sector confusion matrices
    cm_labels = [s for s in iptc_metrics["sector_cm_labels"]]
    plot_confusion_matrix(
        iptc_metrics["sector_cm"], cm_labels,
        "IPTC — Sector Confusion Matrix (counts)",
        FIGS_DIR / "iptc_sector_cm.png",
        normalize=False,
    )
    plot_confusion_matrix(
        iptc_metrics["sector_cm"], cm_labels,
        "IPTC — Sector Confusion Matrix (normalized)",
        FIGS_DIR / "iptc_sector_cm_norm.png",
        normalize=True,
    )
    plot_confusion_matrix(
        ic2_metrics["sector_cm"], cm_labels,
        "IndustryCorpus2 — Sector Confusion Matrix (counts)",
        FIGS_DIR / "ic2_sector_cm.png",
        normalize=False,
    )
    plot_confusion_matrix(
        ic2_metrics["sector_cm"], cm_labels,
        "IndustryCorpus2 — Sector Confusion Matrix (normalized)",
        FIGS_DIR / "ic2_sector_cm_norm.png",
        normalize=True,
    )

    plot_per_sector_accuracy(
        ic2_metrics["records"], iptc_metrics["records"],
        FIGS_DIR / "per_sector_accuracy.png",
    )
    plot_confidence_distribution(
        ic2_metrics,
        FIGS_DIR / "ic2_confidence_dist.png",
    )

    print(f"\n✅ All figures saved to {FIGS_DIR}")


if __name__ == "__main__":
    main()
