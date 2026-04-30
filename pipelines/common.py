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
DEFAULT_TEST_RATIO = 0.2
DEFAULT_SEED = 42


@dataclass(frozen=True)
class TextSample:
    text: str
    label: str


@dataclass(frozen=True)
class DatasetSplit:
    train: list[TextSample]
    test: list[TextSample]


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


def accuracy_score(y_true: list[str], y_pred: list[str]) -> float:
    """정답과 예측을 비교해 단순 정확도를 계산한다."""
    if not y_true:
        return 0.0
    correct = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred)
    return correct / len(y_true)


def macro_f1_score(y_true: list[str], y_pred: list[str]) -> float:
    """각 라벨 F1 평균으로 macro F1 점수를 계산한다."""
    labels = sorted(set(y_true) | set(y_pred))
    if not labels:
        return 0.0

    f1_values: list[float] = []
    for label in labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred != label)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision + recall == 0:
            f1_values.append(0.0)
            continue
        f1_values.append(2 * precision * recall / (precision + recall))

    return sum(f1_values) / len(f1_values)


def summarize_classification(y_true: list[str], y_pred: list[str]) -> dict[str, float | int]:
    """분류 결과를 공통 메트릭 딕셔너리로 요약한다."""
    return {
        "samples": len(y_true),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(macro_f1_score(y_true, y_pred), 4),
    }