# Evaluate 개요

## compare_models.py

**실행**: `python evaluate/compare_models.py`

IPTC(재학습) vs IC2(zero-shot) 성능 비교. **GICS 라벨(sector/industry_group)** 기준.

| 메트릭 | 설명 |
|---|---|
| Sector accuracy | 11개 GICS 섹터 분류 정확도 |
| Industry group accuracy | 25개 IG 분류 정확도 (sector가 맞은 경우 / 전체) |
| Coverage | IC2가 GICS 매핑 가능한 샘플 비율 |
| Recall@candidate-set | IC2 후보군 내에 정답 섹터/IG 포함 여부 (set recall) |

---

## analyze_gics.py

**실행**: `python evaluate/analyze_gics.py`

compare_models.py의 확장 — **상세 분석 + 시각화**.

1. **메트릭**: sector/IG 정확도, Weighted F1, Macro F1 (두 모델)
2. **혼동 행렬**: IPTC + IC2의 섹터 혼동 행렬 (count + normalized, PNG)
3. **IC2 상세**: 섹터별 정확도, Top-3 정확도, confidence 분포 히스토그램

**출력**: `figures/` 디렉터리에 PNG 7개 저장