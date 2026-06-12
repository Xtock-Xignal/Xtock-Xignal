# 변경 요약 - 2026-05-21

## 목적
- 백엔드 차트 API를 프론트 대시보드 차트와 연결.
- WebSocket 기반 실시간 가격 수신을 프론트에 반영.
- 번역 모듈 충돌을 해결해 뉴스 번역 API를 다시 사용 가능하게 정리.
- 실행/테스트/빌드가 컨테이너 기준으로 통과하는지 확인.

## 백엔드 변경
- `backend/main.py`
  - `chart.router`를 FastAPI 앱에 등록.
  - 테스트/기존 코드 호환을 위해 `load_data()` 훅 추가.

- `backend/chart/service.py`
  - 기존 `points` 응답 유지.
  - 프론트 차트/테이블에서 바로 쓸 수 있도록 `rows` 필드 추가.
  - `rows` 형식: `{ date, close, volume }`.

- `backend/app/api/news.py`
  - `googletrans` 제거 후 `deep_translator.GoogleTranslator` 기반 번역으로 변경.
  - 번역 요청의 `url`을 선택값으로 변경.
  - `url` 없이도 `/api/news/translate` 호출 가능.

- `backend/requirements.txt`
  - `googletrans==4.0.0-rc1` 제거.
  - `deep-translator` 추가.

- `backend/Dockerfile`
  - `googletrans` 충돌 회피용 별도 `httpx` 재설치 줄 제거.

## 프론트엔드 변경
- `frontend/components/DashboardSection.jsx`
  - 종목 상세 데이터 호출을 `/api/recent-status`에서 `/api/chart/history/{symbol}`로 변경.
  - 차트 데이터는 백엔드 `rows`를 사용.
  - 차트가 안 보이던 문제를 해결하기 위해 `ResponsiveContainer` 높이를 명시.
  - 종목 선택 시 `ws://localhost:8000/api/chart/ws/{symbol}` WebSocket 연결 추가.
  - WebSocket 상태 배지 추가: `연결 중`, `실시간 연결됨`, `실시간 오류`.
  - 실시간 가격 tick 수신 시 차트 마지막 값을 갱신.
  - 가격이 이전 tick과 같으면 업데이트하지 않도록 필터링.

- `frontend/app/page.jsx`
  - `useSearchParams()`를 사용하는 메인 화면을 `Suspense`로 감싸 Next.js 빌드 오류 해결.
  - 테스트 환경에서 `searchParams`가 없을 때도 안전하게 처리.

- `frontend/next.config.mjs`
  - Next.js 16 Turbopack 빌드 충돌 방지를 위해 `turbopack: {}` 추가.

- `frontend/jsconfig.json`
  - `@/*` 경로 별칭 추가.

- `frontend/app/analysis/[target]/page.js`
  - 누락된 옛 컴포넌트 import 때문에 빌드가 실패하던 페이지를 현재 구조에 맞게 단순화.

- `frontend/data/sp500_list.js`
  - 대시보드 S&P 500 리스트에서 참조하던 누락 파일 추가.

## 테스트 추가/수정
- `backend/tests/test_chart.py`
  - `/api/chart/history/{symbol}` 응답의 `points`, `rows` 검증.

- `backend/tests/test_news_translation.py`
  - `/api/news/translate`가 번역 모듈을 사용하는지 검증.

- `frontend/components/DashboardSection.test.jsx`
  - 종목 클릭 시 차트 API 호출 검증.
  - WebSocket URL 연결 검증.
  - 가격이 같은 tick은 다시 업데이트하지 않는지 검증.

## 실행 환경 변경
- `.env`
  - Docker Compose 실행에 필요한 최소 MongoDB 환경변수 추가.

## 검증 결과
- 백엔드 테스트: 통과.
- 프론트 테스트: 통과.
- 프론트 빌드: 통과.
- 백엔드 헬스체크: 정상.



2026-05-25
  - 주식 시뮬레이션 메뉴명/화면명 정리
  - 시뮬레이션 프론트와 백엔드 API 연결
  - 백엔드 simulation 라우터 활성화
  - 매수/매도/포트폴리오/거래내역 연동
  - 대시보드 기업 리스트 내부 차트를 주식 시뮬레이션 차트 형태로 변경
  - 관련 테스트 추가/수정 및 Docker 안에서 검증 완료