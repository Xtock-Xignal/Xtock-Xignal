from __future__ import annotations


# ── 메트릭 유틸 ──────────────────────────────────────────

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


def precision_recall_f1(
    y_true: list[str],
    y_pred: list[str],
) -> dict[str, float]:
    """macro precision, recall, F1을 계산한다."""
    labels = sorted(set(y_true) | set(y_pred))
    if not labels:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    precisions: list[float] = []
    recalls: list[float] = []

    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)

        precisions.append(tp / (tp + fp) if (tp + fp) else 0.0)
        recalls.append(tp / (tp + fn) if (tp + fn) else 0.0)

    avg_precision = sum(precisions) / len(precisions)
    avg_recall = sum(recalls) / len(recalls)
    avg_f1 = 2 * avg_precision * avg_recall / (avg_precision + avg_recall) if (avg_precision + avg_recall) else 0.0

    return {
        "precision": round(avg_precision, 4),
        "recall": round(avg_recall, 4),
        "f1": round(avg_f1, 4),
    }


def summarize_classification(y_true: list[str], y_pred: list[str]) -> dict[str, float | int]:
    """분류 결과를 공통 메트릭 딕셔너리로 요약한다."""
    return {
        "samples": len(y_true),
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(macro_f1_score(y_true, y_pred), 4),
    }
