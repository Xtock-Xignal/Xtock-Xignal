"""
IndustryCorpus2 Classifier Wrapper
============================================================
Model: BAAI/IndustryCorpus2_Classifier
Base:  BAAI/bge-m3 (0.5B params)
Task:  31-category industry classification (single-label)

This module provides:
  1. IndustryCorpus2Classifier — inference wrapper with label mapping
  2. Label mapping tables to three label spaces:
     - BAAI_TO_SUB_SECTOR → project sub_sector (legacy, 29 classes)
     - BAAI_TO_BIG_SECTOR → GICS sector (11 classes)
     - BAAI_TO_INDUSTRY_GROUP → GICS industry group (25 classes)
  3. Evaluation helpers

Category → label mapping is defined in BAAI_TO_* dictionaries for
zero-shot classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

# ──────────────────────────────────────────────
# BAAI 31 categories → project sub_sector mapping
# ──────────────────────────────────────────────
# Each BAAI category maps to 0+ project sub_sectors.
# Unrelated categories (Math, Literature, Education, etc.) map to empty set.

BAAI_TO_SUB_SECTOR: dict[str, set[str]] = {
    "Automobiles":                 {"automobiles"},
    "Finance & Economics":         {"banking", "insurance", "asset management"},
    "Computing & Telecommunications": {"software", "hardware and IT equipment", "telecom"},
    "Health & Medicine":           {"pharmaceuticals and biotech", "medical devices", "health services"},
    "Manufacturing":               {"manufacturing"},
    "Media & Journalism":          {"media and entertainment"},
    "Petrochemicals":              {"oil and gas", "chemicals"},
    "Power & Energy":              {"electric utilities", "renewable energy", "oil and gas"},
    "Mining":                      {"metals and mining"},
    "Agriculture & Fisheries":     {"agriculture", "food and beverage"},
    "Aerospace":                   {"aerospace and defense"},
    "Transportation":              {"transportation and logistics"},
    "Hospitality & Catering":      {"hotels and leisure", "food and beverage"},
    "Real Estate & Construction":  {"REITs", "real estate services", "manufacturing"},
    "Technology & Research":       {"software", "semiconductors", "hardware and IT equipment"},
    "Artificial Intelligence":     {"software"},
    "Programming":                 {"software"},
    "Information Services":        {"software"},
    "Film & Entertainment":        {"media and entertainment"},
    "Gaming":                      {"media and entertainment"},
    "Sports":                      {"media and entertainment"},
    "Travel & Geography":          {"hotels and leisure"},
    "Biopharmaceuticals":          {"pharmaceuticals and biotech"},
    # ── no reasonable mapping to project sub-sectors ──
    "Others":                      set(),
    "Math & Statistics":           set(),
    "Literature & Emotions":       set(),
    "Water Resources & Marine":    set(),
    "Politics & Administration":   set(),
    "Safety Management":           set(),
    "Subject Education":           set(),
    "Law & Justice":               set(),
}

BAAI_TO_BIG_SECTOR: dict[str, set[str]] = {
    "Automobiles":                 {"Consumer Discretionary"},
    "Finance & Economics":         {"Financials"},
    "Computing & Telecommunications": {"Information Technology", "Communication Services"},
    "Health & Medicine":           {"Health Care"},
    "Manufacturing":               {"Industrials"},
    "Media & Journalism":          {"Communication Services"},
    "Petrochemicals":              {"Energy", "Materials"},
    "Power & Energy":              {"Utilities", "Energy"},
    "Mining":                      {"Materials"},
    "Agriculture & Fisheries":     {"Consumer Staples"},
    "Aerospace":                   {"Industrials"},
    "Transportation":              {"Industrials"},
    "Hospitality & Catering":      {"Consumer Discretionary", "Consumer Staples"},
    "Real Estate & Construction":  {"Real Estate", "Industrials"},
    "Technology & Research":       {"Information Technology"},
    "Artificial Intelligence":     {"Information Technology"},
    "Programming":                 {"Information Technology"},
    "Information Services":        {"Information Technology"},
    "Film & Entertainment":        {"Communication Services"},
    "Gaming":                      {"Communication Services"},
    "Sports":                      {"Communication Services"},
    "Travel & Geography":          {"Consumer Discretionary"},
    "Biopharmaceuticals":          {"Health Care"},
    "Others":                      set(),
    "Math & Statistics":           set(),
    "Literature & Emotions":       set(),
    "Water Resources & Marine":    set(),
    "Politics & Administration":   set(),
    "Safety Management":           set(),
    "Subject Education":           set(),
    "Law & Justice":               set(),
}

# ──────────────────────────────────────────────
# BAAI 31 categories → GICS Industry Group mapping
# ──────────────────────────────────────────────
# GICS has 25 Industry Groups (between Sector and Industry levels).
# Each BAAI category maps to 0+ GICS Industry Groups.
# Unrelated categories map to empty set.

BAAI_TO_INDUSTRY_GROUP: dict[str, set[str]] = {
    "Automobiles":                 {"Automobiles & Components"},
    "Finance & Economics":         {"Banks", "Financial Services", "Insurance"},
    "Computing & Telecommunications": {"Software & Services", "Technology Hardware & Equipment", "Telecommunication Services"},
    "Health & Medicine":           {"Health Care Equipment & Services"},
    "Manufacturing":               {"Capital Goods"},
    "Media & Journalism":          {"Media & Entertainment"},
    "Petrochemicals":              {"Energy", "Materials"},
    "Power & Energy":              {"Utilities", "Energy"},
    "Mining":                      {"Materials"},
    "Agriculture & Fisheries":     {"Food, Beverage & Tobacco"},
    "Aerospace":                   {"Capital Goods"},
    "Transportation":              {"Transportation"},
    "Hospitality & Catering":      {"Consumer Services", "Food, Beverage & Tobacco"},
    "Real Estate & Construction":  {"Equity Real Estate Investment Trusts (REITs)", "Real Estate Management & Development", "Capital Goods"},
    "Technology & Research":       {"Software & Services", "Semiconductors & Semiconductor Equipment", "Technology Hardware & Equipment"},
    "Artificial Intelligence":     {"Software & Services"},
    "Programming":                 {"Software & Services"},
    "Information Services":        {"Software & Services"},
    "Film & Entertainment":        {"Media & Entertainment"},
    "Gaming":                      {"Media & Entertainment"},
    "Sports":                      {"Media & Entertainment"},
    "Travel & Geography":          {"Consumer Services"},
    "Biopharmaceuticals":          {"Pharmaceuticals, Biotechnology & Life Sciences"},
    # ── no reasonable mapping to GICS industry groups ──
    "Others":                      set(),
    "Math & Statistics":           set(),
    "Literature & Emotions":       set(),
    "Water Resources & Marine":    set(),
    "Politics & Administration":   set(),
    "Safety Management":           set(),
    "Subject Education":           set(),
    "Law & Justice":               set(),
}

# Chinese key → English name lookup
BAAI_LABEL_EN: dict[str, str] = {
    "数学_统计": "Math & Statistics",
    "体育": "Sports",
    "农林牧渔": "Agriculture & Fisheries",
    "房地产_建筑": "Real Estate & Construction",
    "时政_政务_行政": "Politics & Administration",
    "消防安全_食品安全": "Safety Management",
    "石油化工": "Petrochemicals",
    "计算机_通信": "Computing & Telecommunications",
    "交通运输": "Transportation",
    "其他": "Others",
    "医学_健康_心理_中医": "Health & Medicine",
    "文学_情感": "Literature & Emotions",
    "水利_海洋": "Water Resources & Marine",
    "游戏": "Gaming",
    "科技_科学研究": "Technology & Research",
    "采矿": "Mining",
    "人工智能_机器学习": "Artificial Intelligence",
    "其他信息服务_信息安全": "Information Services",
    "学科教育_教育": "Subject Education",
    "新闻传媒": "Media & Journalism",
    "汽车": "Automobiles",
    "生物医药": "Biopharmaceuticals",
    "航空航天": "Aerospace",
    "金融_经济": "Finance & Economics",
    "住宿_餐饮_酒店": "Hospitality & Catering",
    "其他制造": "Manufacturing",
    "影视_娱乐": "Film & Entertainment",
    "旅游_地理": "Travel & Geography",
    "法律_司法": "Law & Justice",
    "电力能源": "Power & Energy",
    "计算机编程_代码": "Programming",
}


class IndustryCorpus2Classifier:
    """Wrapper for BAAI/IndustryCorpus2_Classifier (31 industry categories)."""

    def __init__(
        self,
        model_name: str = "BAAI/IndustryCorpus2_Classifier",
        device: Optional[torch.device] = None,
        use_half: bool = True,
    ):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.config = AutoConfig.from_pretrained(
            model_name,
            finetuning_task="text-classification",
        )
        self.id2label = {int(k): v for k, v in self.config.id2label.items()}
        self.label2id = self.config.label2id

        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            trust_remote_code=False,
            ignore_mismatched_sizes=False,
        )
        if use_half and self.device.type == "cuda":
            self.model = self.model.half()
        self.model.to(self.device)
        self.model.eval()

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            use_fast=True,
            trust_remote_code=False,
        )

    @torch.no_grad()
    def predict(self, text: str) -> tuple[str, str]:
        """Predict industry category.

        Returns:
            (chinese_label_key, english_name)
            e.g. ("汽车", "Automobiles")
        """
        encoded = self.tokenizer(
            [text],
            padding=False,
            max_length=2048,
            truncation=True,
            return_tensors="pt",
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        outputs = self.model(**encoded)
        pred_id = torch.argmax(outputs.logits, dim=-1).tolist()[0]

        label_key = self.id2label[pred_id]
        en_name = BAAI_LABEL_EN.get(label_key, label_key)
        return label_key, en_name

    @torch.no_grad()
    def predict_batch(
        self, texts: list[str], batch_size: int = 16
    ) -> list[tuple[str, str]]:
        """Batch prediction.

        Returns:
            list of (chinese_label_key, english_name)
        """
        results: list[tuple[str, str]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            encoded = self.tokenizer(
                batch,
                padding=True,
                max_length=2048,
                truncation=True,
                return_tensors="pt",
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            outputs = self.model(**encoded)
            pred_ids = torch.argmax(outputs.logits, dim=-1).tolist()

            for pid in pred_ids:
                label_key = self.id2label[pid]
                en_name = BAAI_LABEL_EN.get(label_key, label_key)
                results.append((label_key, en_name))
        return results

    def predict_sub_sector(self, text: str) -> Optional[str]:
        """Predict and map to the best project sub_sector."""
        _, en_name = self.predict(text)
        candidates = BAAI_TO_SUB_SECTOR.get(en_name, set())
        if not candidates:
            return None
        return next(iter(candidates))

    def predict_big_sector(self, text: str) -> Optional[str]:
        """Predict and map to the best project big_sector."""
        _, en_name = self.predict(text)
        candidates = BAAI_TO_BIG_SECTOR.get(en_name, set())
        if not candidates:
            return None
        return next(iter(candidates))

    def predict_sub_sector_all_candidates(self, text: str) -> set[str]:
        """Return ALL candidate sub_sectors for the predicted category."""
        _, en_name = self.predict(text)
        return BAAI_TO_SUB_SECTOR.get(en_name, set())

    def predict_big_sector_all_candidates(self, text: str) -> set[str]:
        """Return ALL candidate big_sectors for the predicted category."""
        _, en_name = self.predict(text)
        return BAAI_TO_BIG_SECTOR.get(en_name, set())

    # ── GICS Industry Group methods ──────────────────────────────

    def predict_industry_group(self, text: str) -> Optional[str]:
        """Predict and map to the best GICS industry group."""
        _, en_name = self.predict(text)
        candidates = BAAI_TO_INDUSTRY_GROUP.get(en_name, set())
        if not candidates:
            return None
        return next(iter(candidates))

    def predict_industry_group_all_candidates(self, text: str) -> set[str]:
        """Return ALL candidate GICS industry groups for the predicted category."""
        _, en_name = self.predict(text)
        return BAAI_TO_INDUSTRY_GROUP.get(en_name, set())


# ── GICS Evaluation Helpers ──────────────────────────────

@torch.no_grad()
def evaluate_gics(
    model: IndustryCorpus2Classifier,
    samples: list,
) -> dict:
    """Evaluate IndustryCorpus2 on GICS sector + industry group.
    
    Args:
        model: IndustryCorpus2Classifier instance.
        samples: list of objects with .text, .sector, .industry_group attributes.
    
    Returns:
        dict with sector_acc, industry_group_acc, coverage, etc.
    """
    all_sector_true: list[str] = []
    all_sector_pred: list[str] = []
    all_ig_true: list[str] = []
    all_ig_pred: list[str] = []
    mapped_count = 0
    unmapped_count = 0

    for sample in samples:
        _, en_name = model.predict(sample.text)

        # GICS sector prediction
        sector_candidates = BAAI_TO_BIG_SECTOR.get(en_name, set())
        sector_pred = next(iter(sector_candidates)) if sector_candidates else "__UNMAPPED__"

        # Industry group prediction
        ig_candidates = BAAI_TO_INDUSTRY_GROUP.get(en_name, set())
        if ig_candidates:
            ig_pred = next(iter(ig_candidates))
            mapped_count += 1
        else:
            ig_pred = "__UNMAPPED__"
            unmapped_count += 1

        all_sector_true.append(sample.sector)
        all_sector_pred.append(sector_pred)
        all_ig_true.append(sample.industry_group)
        all_ig_pred.append(ig_pred)

    n = len(all_sector_true)
    mapped_n = mapped_count

    sector_correct = sum(1 for t, p in zip(all_sector_true, all_sector_pred) if t == p and p != "__UNMAPPED__")
    sector_acc = sector_correct / max(mapped_n, 1)
    sector_acc_overall = sum(1 for t, p in zip(all_sector_true, all_sector_pred) if t == p) / max(n, 1)

    ig_correct = sum(1 for t, p in zip(all_ig_true, all_ig_pred) if t == p and p != "__UNMAPPED__")
    ig_acc = ig_correct / max(mapped_n, 1)
    ig_acc_overall = sum(1 for t, p in zip(all_ig_true, all_ig_pred) if t == p) / max(n, 1)

    coverage = mapped_count / max(n, 1)

    return {
        "sector_acc": round(sector_acc, 4),
        "sector_acc_overall": round(sector_acc_overall, 4),
        "industry_group_acc": round(ig_acc, 4),
        "industry_group_acc_overall": round(ig_acc_overall, 4),
        "coverage": round(coverage, 4),
        "total_samples": n,
        "mapped_samples": mapped_count,
        "unmapped_samples": unmapped_count,
    }


@torch.no_grad()
def evaluate_gics_recall(
    model: IndustryCorpus2Classifier,
    samples: list,
) -> dict:
    """Evaluate IndustryCorpus2 recall@set for GICS labels.
    
    Checks if the TRUE label is contained in the candidate set
    (not just the first candidate).
    """
    total = len(samples)
    sector_recall = 0
    ig_recall = 0
    mapped_total = 0

    for sample in samples:
        _, en_name = model.predict(sample.text)

        sector_candidates = BAAI_TO_BIG_SECTOR.get(en_name, set())
        ig_candidates = BAAI_TO_INDUSTRY_GROUP.get(en_name, set())

        if sector_candidates or ig_candidates:
            mapped_total += 1

        if sample.sector in sector_candidates:
            sector_recall += 1
        if sample.industry_group in ig_candidates:
            ig_recall += 1

    return {
        "sector_recall_at_set": round(sector_recall / max(total, 1), 4),
        "industry_group_recall_at_set": round(ig_recall / max(total, 1), 4),
        "total_samples": total,
        "mapped_samples": mapped_total,
    }
