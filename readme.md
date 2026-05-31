# 산업 분류 프로젝트

뉴스 기사를 GICS 산업 분류 체계에 따라 분류하는 프로젝트.

---

## 데이터 수집

- `python3 load_data/load_yfinance.py` 실행
- **설정 파일**: `IC2/config/class.yaml` — GICS 분류 체계 기반 (sector → industry_group → ticker)
  - 11개 섹터, 25개 산업군(industry group), 503개 S&P 500 티커
  - 각 티커는 하나의 (sector, industry_group) 쌍에 할당됨
- **수집 파이프라인**:
  1. yfinance `Ticker.news` + `yfinance.Search`로 기사 수집
  2. Pass 1: 제목 기반 회사명/ticker alias 관련성 필터
  3. Pass 2: `newspaper3k` 본문 추출 후 키워드 스코어링 필터
     - industry_group 키워드 비율(×10), sector 키워드 비율(×8), 회사명 매치(+5), ticker 매치(+2)
     - 임계값: min_score=4
  4. 산업군 규모별 수집 제한 (1-5개사: 10/회 → 31+개사: 2/회)
- **출력**: `datasets/news.csv` — `article, company_name, ticker, sector, industry_group, collected_at`

---

## 클래스 분류 체계

- **GICS (Global Industry Classification Standard)** 기반
  - 11개 섹터, 25개 산업군(industry group)
  - 세부 분류는 `IC2/config/class.yaml` 참조

| Sector | Industry Groups |
|---|---|
| Communication Services | Media & Entertainment, Telecommunication Services |
| Consumer Discretionary | Consumer Services, Consumer Discretionary Distribution & Retail, Automobiles & Components, Consumer Durables & Apparel |
| Consumer Staples | Food, Beverage & Tobacco, Consumer Staples Distribution & Retail, Household & Personal Products |
| Energy | Energy |
| Financials | Insurance, Financial Services, Banks |
| Health Care | Health Care Equipment & Services, Pharmaceuticals, Biotechnology & Life Sciences |
| Industrials | Capital Goods, Commercial & Professional Services, Transportation |
| Information Technology | Software & Services, Semiconductors & Semiconductor Equipment, Technology Hardware & Equipment |
| Materials | Materials |
| Real Estate | Equity Real Estate Investment Trusts (REITs), Real Estate Management & Development |
| Utilities | Utilities |

---

## Fine-tuned GICSBertModel (GICS fine-tuning)

프로젝트의 뉴스 데이터(`datasets/news.csv`)로 **BAAI/bge-m3** 백본을 fine-tuning한 GICS 계층형 분류 모델.

### 모델 구조

```
뉴스 기사 → BAAI/bge-m3 (shared backbone) → [CLS] 토큰
                                                  ↓
                      ┌────────────────────────────────────┐
                      ↓                                    ↓
              Sector Classifier (11)           IG Classifier (25)
                      ↓                                    ↓
                  Sector 예측                     IG 예측 (sector 마스킹 적용)
```

- **백본**: `BAAI/bge-m3` (XLMRoberta, 0.5B)
- **분류 헤드**: 2개의 Linear 레이어 (sector 11 class, industry group 25 class)
- **계층형 예측**: sector 예측 후, 해당 sector에 속하지 않는 IG는 softmax 확률을 0으로 마스킹
- **Confidence threshold**: IG 예측 max probability가 `best_threshold` 미만이면 `__NONE__` 반환
- **사전학습 활용**: `BAAI/IndustryCorpus2_Classifier`의 backbone 가중치로 초기화 후 fine-tuning

### 성능

| 메트릭 | 값 |
|---|---|
| Test samples | 340 |
| Sector Accuracy | 90.88% |
| **IG@Sector F1 (best threshold=0.3)** | **91.52%** |
| IG@Sector Precision | 92.44% |
| IG@Sector Recall | 90.61% |
| IG@Sector Accuracy | 94.17% |

### 학습

```bash
python IC2/fine_tune.py
```

- 학습 설정: `IC2/config/model_config.yaml`
- 체크포인트: `IC2/train_history/checkpoint/model.pt`
- 학습 결과물:
  - `IC2/train_history/training_metrics.png` — epoch별 Sector/IG F1 추이
  - `IC2/train_history/threshold_evaluation.png` — threshold별 IG@Sector F1
  - `IC2/train_history/train_config.json` — 학습 설정 + `best_threshold`
  - `IC2/train_history/labels.json` — 라벨 매핑 (sector/IG id↔label, sector→IG mask)
  - `IC2/train_history/checkpoint/tokenizer.json` — 토크나이저

### 추론 (Inference)

`model.pt`, `train_config.json`, `labels.json` 세 파일을 함께 사용한다.

```python
import json
import torch
from pathlib import Path
from transformers import AutoTokenizer

from IC2.fine_tune import GICSBertModel
from evaluate.compare_models import GICSLabelMapping

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CHECKPOINT_DIR = Path("IC2/train_history/checkpoint")
ARTIFACT_DIR = CHECKPOINT_DIR.parent

# 1. Config → best threshold
with open(ARTIFACT_DIR / "train_config.json") as f:
    config = json.load(f)
best_threshold = config["best_threshold"]  # 0.3

# 2. Label mapping
with open(ARTIFACT_DIR / "labels.json") as f:
    lm_raw = json.load(f)
label_mapping = GICSLabelMapping(
    sector_label2id=lm_raw["sector_label2id"],
    sector_id2label={int(k): v for k, v in lm_raw["sector_id2label"].items()},
    ig_label2id=lm_raw["ig_label2id"],
    ig_id2label={int(k): v for k, v in lm_raw["ig_id2label"].items()},
    sector_to_ig_mask={int(k): v for k, v in lm_raw["sector_to_ig_mask"].items()},
)

# 3. Model load
model = GICSBertModel(
    model_name=config["model_name"],
    num_sectors=label_mapping.num_sectors,
    num_igs=label_mapping.num_industry_groups,
    sector_to_ig_mask=label_mapping.sector_to_ig_mask,
    load_from_ic2=False,  # checkpoint 자체 weights 사용
)
state = torch.load(
    CHECKPOINT_DIR / "model.pt", map_location=DEVICE, weights_only=True
)
model.load_state_dict(state)
model.to(DEVICE)
model.eval()

# 4. Tokenizer
tokenizer = AutoTokenizer.from_pretrained(str(CHECKPOINT_DIR))

# 5. Inference
def predict(text: str) -> tuple[str, str, float]:
    """(sector_label, ig_label, threshold) 반환."""
    encoded = tokenizer(
        [text],
        truncation=True,
        padding="max_length",
        max_length=config["max_length"],
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"].to(DEVICE)
    attention_mask = encoded["attention_mask"].to(DEVICE)

    sector_ids, ig_ids = model.predict_hierarchical(
        input_ids, attention_mask, threshold=best_threshold,
    )

    sector_label = label_mapping.sector_id2label[int(sector_ids[0].item())]
    ig_id = int(ig_ids[0].item())
    ig_label = (
        label_mapping.ig_id2label[ig_id] if ig_id != -1 else "__NONE__"
    )
    return sector_label, ig_label, best_threshold

# 사용 예
text = "Apple Inc. reported strong quarterly earnings driven by iPhone sales."
sector, ig, thresh = predict(text)
print(f"Sector: {sector} | IG: {ig} (threshold={thresh})")
```

### 중요: 추론 시 `load_from_ic2=False`

Fine-tuned checkpoint(`model.pt`)에는 이미 학습된 전체 가중치가 저장되어 있으므로, 모델 생성 시 반드시 `load_from_ic2=False`로 설정해야 한다. `True`(기본값)로 설정하면 HuggingFace에서 `BAAI/IndustryCorpus2_Classifier`를 다시 다운로드하여 backbone을 덮어쓰게 된다.

---

## 분류 모델: IndustryCorpus2 (IC2)

### 모델 개요

- **모델명**: `BAAI/IndustryCorpus2_Classifier` (HuggingFace)
- **백본**: `BAAI/bge-m3` (0.5B 파라미터, BERT 계열)
- **출력**: 31개 산업 카테고리 (중국어 레이블)
- **학습 방식**: BAAI가 대규모 뉴스 코퍼스로 사전 학습 완료
- **사용 방식**: **Zero-shot** — 추가 학습 없이 사전 학습 상태 그대로 사용

### 작동 방식

```
뉴스 기사 → BAAI/IndustryCorpus2_Classifier → 31개 카테고리 중 1개 선택
                                                      ↓
                                           BAAI_LABEL_EN (중→영 매핑)
                                                      ↓
                              ┌──────────────────────────┐
                              ↓                          ↓
                     BAAI_TO_BIG_SECTOR           BAAI_TO_INDUSTRY_GROUP
                     (31→11개 GICS 섹터)          (31→25개 GICS IG)
                              ↓                          ↓
                         최종 섹터 예측                최종 IG 예측
```

- 각 BAAI 카테고리는 1개 이상의 GICS 섹터/IG 후보군(candidate set)으로 매핑됨
- 예: BAAI "Computing & Telecommunications" → GICS 섹터 {"Information Technology", "Communication Services"}
- 후보군이 2개 이상인 경우 첫 번째를 top-1 예측으로 사용
- BAAI 카테고리 중 8개는 GICS와 관련 없음 (예: Math & Statistics, Literature & Emotions 등) → 매핑 불가

### Zero-shot 추론 파라미터

| 파라미터 | 값 |
|---|---|
| 모델 | BAAI/IndustryCorpus2_Classifier |
| max_length | 2048 |
| 배치 크기 | 16 (predict_batch) |
| 연산 정밀도 | fp16 (CUDA) |
| 신뢰도 | softmax 확률 (31개 카테고리 중 max) |

**학습 관련 구성**: IC2는 zero-shot으로 사용되므로, optimizer / learning rate / weight decay 등 fine-tuning 파라미터가 적용되지 않는다. 모든 가중치는 사전 학습 상태로 고정(frozen)된다.

---

## 이전 모델 (비교 대상)

프로젝트 초기에는 `classla/multilingual-IPTC-news-topic-classifier` 기반 HierarchicalBertModel을 재학습하여 사용했다. IPTC는 1,362개 학습 샘플로 3 epoch 학습, AdamW(lr=5e-5, weight_decay=0.0)로 최적화했다. 그러나 데이터 부족으로 underfitting이 발생하여 IC2 zero-shot이 모든 메트릭에서 우세했다.

| 메트릭 | IPTC (재학습) | IC2 (zero-shot) |
|---|---|---|
| Sector 정확도 | 16.76% | **52.35%** |
| IG 정확도 | 4.71% | **32.94%** |
| Sector Macro F1 | 0.026 | **0.440** |
| Top-3 Sector recall | — | **80.00%** |

---