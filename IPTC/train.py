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
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from IPTC.runtime import (
    HierarchicalBertDataset,
    HierarchicalBertModel,
    compute_sub_class_weights,
)
from utils.util_modeling import (
    NEWS_CSV,
    build_hierarchical_label_mapping,
    ensure_dir,
    hierarchical_stratified_split,
    load_hierarchical_dataset,
    save_json,
)
from utils.util_eval import precision_recall_f1

BERT_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = ensure_dir(BERT_DIR / "train_history")
CHECKPOINT_DIR = ensure_dir(ARTIFACT_DIR / "checkpoint")
LABEL_MAP_PATH = ARTIFACT_DIR / "labels.json"
HPARAMS_PATH = BERT_DIR / "config" / "bert_hparams.yaml"
PROD_YAML_PATH = BERT_DIR / "config" / "products_and_services.yaml"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_hparams(path: Path = HPARAMS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def validate(
    model: HierarchicalBertModel,
    loader: DataLoader,
    label_mapping,
    threshold: float = 0.0,
) -> dict:
    model.eval()
    all_big_true: list[str] = []
    all_big_pred: list[str] = []
    all_sub_true: list[str] = []
    all_sub_pred: list[str] = []

    for batch in loader:
        input_ids = batch["input_ids"].to(DEVICE)
        attention_mask = batch["attention_mask"].to(DEVICE)

        big_pred_ids, sub_pred_ids = model.predict_hierarchical(
            input_ids, attention_mask, threshold=threshold,
        )

        big_true_ids = batch["big_labels"].numpy()
        sub_true_ids = batch["sub_labels"].numpy()

        for i in range(len(big_true_ids)):
            all_big_true.append(label_mapping.big_id2label[int(big_true_ids[i])])
            all_big_pred.append(label_mapping.big_id2label[int(big_pred_ids[i].item())])
            all_sub_true.append(label_mapping.sub_id2label[int(sub_true_ids[i])])
            sp_id = int(sub_pred_ids[i].item())
            all_sub_pred.append("__NONE__" if sp_id == -1 else label_mapping.sub_id2label[sp_id])

    big_metrics = precision_recall_f1(all_big_true, all_big_pred)
    big_acc = sum(1 for t, p in zip(all_big_true, all_big_pred) if t == p) / max(len(all_big_true), 1)

    swb_true = [st for bt, bp, st in zip(all_big_true, all_big_pred, all_sub_true) if bt == bp]
    swb_pred = [sp for bt, bp, sp in zip(all_big_true, all_big_pred, all_sub_pred) if bt == bp]
    swb_metrics = precision_recall_f1(swb_true, swb_pred) if swb_true else {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    swb_metrics["accuracy"] = round(sum(1 for t, p in zip(swb_true, swb_pred) if t == p) / max(len(swb_true), 1), 4)

    sub_overall = precision_recall_f1(all_sub_true, all_sub_pred)
    sub_overall["accuracy"] = round(sum(1 for t, p in zip(all_sub_true, all_sub_pred) if t == p) / max(len(all_sub_true), 1), 4)

    return {
        "big_acc": round(big_acc, 4),
        "big_metrics": big_metrics,
        "sub_when_big_metrics": swb_metrics,
        "sub_overall_metrics": sub_overall,
    }


def plot_training_metrics(
    epoch_big: list[dict],
    epoch_sub_when_big: list[dict],
    epoch_sub_overall: list[dict],
    save_dir: Path,
) -> None:
    epochs = list(range(1, len(epoch_big) + 1))

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
    _plot(ax1, epochs, epoch_big, "Big Sector")
    _plot(ax2, epochs, epoch_sub_when_big, "Sub Sector (Big Correct)")
    _plot(ax3, epochs, epoch_sub_overall, "Sub Sector (Overall)")
    plt.tight_layout()

    path = save_dir / "training_metrics.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Metrics plot saved: {path}")


def main() -> None:
    hparams = load_hparams()
    training = hparams["training"]
    loss_cfg = hparams["loss"]
    eval_cfg = hparams["evaluation"]
    opt_cfg = hparams["optimizer"]

    set_seed(training["seed"])

    print("Loading hierarchical dataset...")
    samples = load_hierarchical_dataset(NEWS_CSV)
    print(f"  Total samples: {len(samples)}")

    label_mapping = build_hierarchical_label_mapping(samples, PROD_YAML_PATH)
    print(f"  Big sectors: {label_mapping.num_big_sectors}")
    print(f"  Sub sectors: {label_mapping.num_sub_sectors}")

    split = hierarchical_stratified_split(samples, training["test_ratio"], training["seed"])
    print(f"  Train: {len(split.train)} | Test: {len(split.test)}")

    all_sub_ids = [label_mapping.sub_label2id[s.sub_sector] for s in samples]
    sub_class_weights = compute_sub_class_weights(
        all_sub_ids,
        label_mapping.num_sub_sectors,
        loss_cfg["class_weight_clipping"],
    ).to(DEVICE)

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(training["model_name"])

    train_dataset = HierarchicalBertDataset(
        texts=[s.text for s in split.train],
        big_labels=[label_mapping.big_label2id[s.big_sector] for s in split.train],
        sub_labels=[label_mapping.sub_label2id[s.sub_sector] for s in split.train],
        tokenizer=tokenizer,
        max_length=training["max_length"],
    )
    test_dataset = HierarchicalBertDataset(
        texts=[s.text for s in split.test],
        big_labels=[label_mapping.big_label2id[s.big_sector] for s in split.test],
        sub_labels=[label_mapping.sub_label2id[s.sub_sector] for s in split.test],
        tokenizer=tokenizer,
        max_length=training["max_length"],
    )

    train_loader = DataLoader(train_dataset, batch_size=training["batch_size"], shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=training["batch_size"])

    model = HierarchicalBertModel(
        model_name=training["model_name"],
        num_big_sectors=label_mapping.num_big_sectors,
        num_sub_sectors=label_mapping.num_sub_sectors,
        big_to_sub_mask=label_mapping.big_to_sub_mask,
    ).to(DEVICE)

    big_loss_fn = nn.CrossEntropyLoss()
    sub_loss_fn = nn.CrossEntropyLoss(weight=sub_class_weights)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training["learning_rate"],
        weight_decay=opt_cfg["weight_decay"],
        eps=opt_cfg["adam_epsilon"],
    )

    epoch_big_metrics: list[dict] = []
    epoch_sub_when_big_metrics: list[dict] = []
    epoch_sub_overall_metrics: list[dict] = []

    num_epochs = training["num_epochs"]
    for epoch in range(1, num_epochs + 1):
        model.train()
        total_loss = 0.0
        steps = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch}/{num_epochs}", leave=False)
        for batch in pbar:
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            big_labels = batch["big_labels"].to(DEVICE)
            sub_labels = batch["sub_labels"].to(DEVICE)

            big_logits, sub_logits = model(input_ids, attention_mask)

            big_loss = big_loss_fn(big_logits, big_labels)
            sub_loss = sub_loss_fn(sub_logits, sub_labels)
            loss = loss_cfg["big_loss_weight"] * big_loss + loss_cfg["sub_loss_weight"] * sub_loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), opt_cfg["max_grad_norm"])
            optimizer.step()
            optimizer.zero_grad()

            total_loss += float(loss.item())
            steps += 1
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        avg_loss = total_loss / max(steps, 1)

        val_results = validate(model, test_loader, label_mapping, threshold=0.0)
        epoch_big_metrics.append(val_results["big_metrics"])
        epoch_sub_when_big_metrics.append(val_results["sub_when_big_metrics"])
        epoch_sub_overall_metrics.append(val_results["sub_overall_metrics"])

        print(
            f"Epoch {epoch}/{num_epochs} | Loss: {avg_loss:.4f} | "
            f"Big Acc: {val_results['big_acc']:.4f} | "
            f"Sub@Big F1: {val_results['sub_when_big_metrics']['f1']:.4f}"
        )

    print("\n" + "=" * 80)
    print("Threshold Evaluation (on test set)")
    print("=" * 80)
    header = (
        f"{'Threshold':>10} {'Big Acc':>8} {'Sub@Big F1':>10} "
        f"{'Sub@Big Prec':>12} {'Sub@Big Rec':>11} {'Sub@Big Acc':>11}"
    )
    print(header)
    print("-" * 80)

    for thresh in eval_cfg["thresholds"]:
        vr = validate(model, test_loader, label_mapping, threshold=thresh)
        swb = vr["sub_when_big_metrics"]
        print(
            f"{thresh:>10.1f} {vr['big_acc']:>8.4f} {swb['f1']:>10.4f} "
            f"{swb['precision']:>12.4f} {swb['recall']:>11.4f} {swb['accuracy']:>11.4f}"
        )
    print("=" * 80)

    plot_training_metrics(
        epoch_big_metrics,
        epoch_sub_when_big_metrics,
        epoch_sub_overall_metrics,
        ARTIFACT_DIR,
    )

    save_json(
        LABEL_MAP_PATH,
        {
            "big_label2id": label_mapping.big_label2id,
            "big_id2label": {str(k): v for k, v in label_mapping.big_id2label.items()},
            "sub_label2id": label_mapping.sub_label2id,
            "sub_id2label": {str(k): v for k, v in label_mapping.sub_id2label.items()},
            "big_to_sub_mask": {str(k): v for k, v in label_mapping.big_to_sub_mask.items()},
        },
    )

    torch.save(model.state_dict(), CHECKPOINT_DIR / "model.pt")
    tokenizer.save_pretrained(CHECKPOINT_DIR)

    save_json(
        ARTIFACT_DIR / "train_config.json",
        {
            "model_name": training["model_name"],
            "epochs": num_epochs,
            "batch_size": training["batch_size"],
            "learning_rate": training["learning_rate"],
            "max_length": training["max_length"],
            "checkpoint_dir": str(CHECKPOINT_DIR.relative_to(ROOT_DIR)),
            "loss_weights": {
                "big": loss_cfg["big_loss_weight"],
                "sub": loss_cfg["sub_loss_weight"],
            },
            "class_weight_clipping": loss_cfg["class_weight_clipping"],
            "thresholds": eval_cfg["thresholds"],
        },
    )
    print(f"\nTraining complete. Checkpoint saved to {CHECKPOINT_DIR}")


if __name__ == "__main__":
    main()
