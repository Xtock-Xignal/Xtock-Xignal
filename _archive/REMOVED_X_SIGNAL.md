# [ARCHIVED] X(Twitter) 감성 분석 관련 코드

아카이브 일시: 2026-06-12

## 제거 이유
X(Twitter) API 기반 감성 분석 기능을 프로젝트에서 완전히 제거. 해당 기능은 X API Bearer Token에 의존하며, 현재 프로젝트 방향과 맞지 않아 제거됨.

## 아카이브된 파일 목록

### Backend
| 파일 | 원래 위치 | 설명 |
|------|-----------|------|
| `backend/api/x_signal_router.py` | `backend/app/api/x_signal_router.py` | X API 트윗 검색, 감성 분석, 주가 영향 분석 라우터 |
| `backend/services/x_signal_service.py` | `backend/app/services/x_signal_service.py` | 주가 히스토리 정규화, 익일 수익률 계산, 감성 추정 서비스 |
| `backend/tests/test_x_signal.py` | `backend/tests/test_x_signal.py` | X 신호 관련 단위 테스트 |
| `backend/train_model.py` | `backend/train_model.py` | 트윗 데이터(train_tweet_stock.json) 기반 ML 모델 학습 |

### Frontend
| 파일 | 원래 위치 | 설명 |
|------|-----------|------|
| `frontend/components/TweetCard.jsx` | `frontend/components/TweetCard.jsx` | 트윗 카드 UI 컴포넌트 |
| `frontend/components/RecentStatusSection.jsx` | `frontend/components/RecentStatusSection.jsx` | 실시간 X API 기반 기업 근황 섹션 |
| `frontend/components/HistoricalImpactSection.jsx` | `frontend/components/HistoricalImpactSection.jsx` | 과거 트윗 영향력 분석 섹션 |
| `frontend/analysis_target/page.js` | `frontend/app/analysis/[target]/page.js` | 트윗 & 감성 분석 동적 라우트 페이지 |

## 제거된 백엔드 API 엔드포인트
- `GET /api/tweets` — X 트윗 검색
- `GET /api/price` — (x_signal_router 내) 주가 히스토리
- `GET /api/next-return` — 익일 수익률
- `POST /api/tweet-impact` — 트윗 영향도 계산/저장
- `POST /api/match-company` — 검색어→회사 매칭 (트윗 기반)
- `POST /api/sentiment` — 감성 분석
- `POST /api/recent-status` — X API 기반 실시간 기업 근황
- `POST /api/historical-impact` — CSV 트윗 기반 과거 영향 분석
- `POST /api/historical-chart` — 트윗 시점 기준 주가 차트

## 제거된 환경 변수
- `BEARER_TOKEN`
- `TWEETER_BEARER_TOKEN`
- `X_BEARER_TOKEN`
- `TWITTER_BEARER_TOKEN`
