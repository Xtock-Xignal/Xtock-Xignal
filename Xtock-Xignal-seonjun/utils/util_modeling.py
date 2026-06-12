from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATASET_CSV = DATA_DIR / "dataset.csv"
NEWS_CSV = ROOT_DIR / "datasets" / "news.csv"
DEFAULT_TEST_RATIO = 0.2
DEFAULT_SEED = 42


# ── 데이터 클래스 ──────────────────────────────────────

@dataclass(frozen=True)
class TextSample:
    text: str
    label: str


@dataclass(frozen=True)
class HierarchicalSample:
    text: str
    big_sector: str
    sub_sector: str
    company_name: str = ""


@dataclass(frozen=True)
class GICSSample:
    """GICS-based sample with sector and industry group labels."""
    text: str
    sector: str
    industry_group: str
    company_name: str = ""
    ticker: str = ""


@dataclass(frozen=True)
class DatasetSplit:
    train: list[TextSample]
    test: list[TextSample]


@dataclass(frozen=True)
class HierarchicalSplit:
    train: list[HierarchicalSample]
    test: list[HierarchicalSample]


@dataclass
class HierarchicalLabelMapping:
    """big_sector / sub_sector 양방향 매핑 + big→sub 후보 마스크."""
    big_label2id: dict[str, int]
    big_id2label: dict[int, str]
    sub_label2id: dict[str, int]
    sub_id2label: dict[int, str]
    # big_sector index → list of valid sub_sector indices
    big_to_sub_mask: dict[int, list[int]]

    @property
    def num_big_sectors(self) -> int:
        return len(self.big_label2id)

    @property
    def num_sub_sectors(self) -> int:
        return len(self.sub_label2id)


# ── 기존 단일-라벨 로더 (하위 호환) ──────────────────────────

def load_dataset(csv_path: Path = DATASET_CSV) -> list[TextSample]:
    """공통 CSV 데이터셋을 샘플 객체 목록으로 로드한다."""
    samples: list[TextSample] = []
    with csv_path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            samples.append(TextSample(text=row["text"], label=row["label"]))
    return samples


def stratified_split(
    samples: Iterable[TextSample],
    test_ratio: float = DEFAULT_TEST_RATIO,
    seed: int = DEFAULT_SEED,
) -> DatasetSplit:
    """라벨 분포를 유지하며 train 과 test 로 나눈다."""
    rng = random.Random(seed)
    grouped: dict[str, list[TextSample]] = defaultdict(list)

    for sample in samples:
        grouped[sample.label].append(sample)

    train: list[TextSample] = []
    test: list[TextSample] = []

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
    return DatasetSplit(train=train, test=test)


# ── 계층형 데이터 로더 ──────────────────────────────────

def load_hierarchical_dataset(csv_path: Path = NEWS_CSV) -> list[HierarchicalSample]:
    """news.csv(article, company_name, sub_sector, big_sector)를 계층형 샘플로 로드한다."""
    samples: list[HierarchicalSample] = []
    with csv_path.open("r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            samples.append(HierarchicalSample(
                text=row["article"],
                big_sector=row["big_sector"].strip(),
                sub_sector=row["sub_sector"].strip(),
                company_name=row.get("company_name", "").strip(),
            ))
    return samples


# ── GICS 데이터 로더 ────────────────────────────────────

def load_gics_dataset(csv_path: Path = NEWS_CSV) -> list[GICSSample]:
    """news.csv(article, company_name, ticker, sector, industry_group)를 GICS 샘플로 로드한다."""
    samples: list[GICSSample] = []
    with csv_path.open("r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            sector = row.get("sector", "").strip() or row.get("big_sector", "").strip()
            ig = row.get("industry_group", "").strip() or row.get("sub_sector", "").strip()
            samples.append(GICSSample(
                text=row["article"],
                sector=sector,
                industry_group=ig,
                company_name=row.get("company_name", "").strip(),
                ticker=row.get("ticker", "").strip(),
            ))
    return samples


def build_hierarchical_label_mapping(
    samples: list[HierarchicalSample],
    prod_yaml_path: Path | None = None,
) -> HierarchicalLabelMapping:
    """샘플 목록으로부터 big/sub 매핑과 big→sub 후보 마스크를 구축한다.

    prod_yaml_path 가 주어지면 YAML의 계층 구조로 big→sub 마스크를 결정한다.
    없으면 샘플 데이터에서 추론한다.
    """
    big_sectors = sorted({s.big_sector for s in samples})
    sub_sectors = sorted({s.sub_sector for s in samples})

    big_label2id = {s: i for i, s in enumerate(big_sectors)}
    big_id2label = {i: s for s, i in big_label2id.items()}
    sub_label2id = {s: i for i, s in enumerate(sub_sectors)}
    sub_id2label = {i: s for s, i in sub_label2id.items()}

    # big → sub 후보 마스크 구축
    big_to_sub_mask: dict[int, list[int]] = {i: [] for i in range(len(big_sectors))}

    if prod_yaml_path and prod_yaml_path.exists():
        _build_mask_from_yaml(prod_yaml_path, big_label2id, sub_label2id, big_to_sub_mask)
    else:
        for s in samples:
            big_id = big_label2id[s.big_sector]
            sub_id = sub_label2id[s.sub_sector]
            if sub_id not in big_to_sub_mask[big_id]:
                big_to_sub_mask[big_id].append(sub_id)

    return HierarchicalLabelMapping(
        big_label2id=big_label2id,
        big_id2label=big_id2label,
        sub_label2id=sub_label2id,
        sub_id2label=sub_id2label,
        big_to_sub_mask=big_to_sub_mask,
    )


def _build_mask_from_yaml(
    path: Path,
    big_label2id: dict[str, int],
    sub_label2id: dict[str, int],
    big_to_sub_mask: dict[int, list[int]],
) -> None:
    """products_and_services.yaml 의 계층 구조로 big→sub 마스크를 채운다."""
    current_big: str | None = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if stripped.startswith("# "):
                current_big = stripped[2:].strip()
            elif current_big and not line.startswith(" ") and ":" in stripped:
                sub_key = stripped.rstrip(":").strip()
                if current_big in big_label2id and sub_key in sub_label2id:
                    big_id = big_label2id[current_big]
                    sub_id = sub_label2id[sub_key]
                    if sub_id not in big_to_sub_mask[big_id]:
                        big_to_sub_mask[big_id].append(sub_id)


def hierarchical_stratified_split(
    samples: list[HierarchicalSample],
    test_ratio: float = DEFAULT_TEST_RATIO,
    seed: int = DEFAULT_SEED,
) -> HierarchicalSplit:
    """big_sector 기준으로 stratified split을 수행한다."""
    rng = random.Random(seed)
    grouped: dict[str, list[HierarchicalSample]] = defaultdict(list)

    for s in samples:
        grouped[s.big_sector].append(s)

    train: list[HierarchicalSample] = []
    test: list[HierarchicalSample] = []

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
    return HierarchicalSplit(train=train, test=test)


# ── 공통 유틸 ──────────────────────────────────────────

def ensure_dir(path: Path) -> Path:
    """필요한 디렉터리를 만들고 같은 경로를 반환한다."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, payload: dict) -> None:
    """딕셔너리 결과를 사람이 읽기 쉬운 JSON으로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def save_split_preview(path: Path, split: DatasetSplit) -> None:
    """데이터 분할 결과의 일부 예시와 크기를 기록한다."""
    payload = {
        "train_size": len(split.train),
        "test_size": len(split.test),
        "train_examples": [asdict(sample) for sample in split.train[:5]],
        "test_examples": [asdict(sample) for sample in split.test[:5]],
    }
    save_json(path, payload)
