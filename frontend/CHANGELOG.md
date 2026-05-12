# Changelog

## 2026-03-11

### Frontend Components

- `components/BacktestSection.jsx`
  - 초보자용 백테스팅 UX를 확장해 템플릿 포트폴리오(올웨더/성장형/보수형) 선택 기능 추가.
  - 템플릿 선택 시 단일 티커 대신 `positions`로 요청을 구성하도록 백엔드 payload를 조정.
  - 초기 자금 빠른 입력 버튼(5만, 10만, 30만, 100만) 추가.
  - 템플릿 선택 즉시 현재 초기 자금 기준으로 종목별 예상 배분(장바구니) 미리보기를 표시.
  - 빠른 티커 샘플을 6개에서 확장하고, 샘플은 예시일 뿐 직접 입력도 가능하다는 안내를 추가.
  - 실행 중 진행 단계(데이터 조회→MA 계산→신호 실행→결과 집계) 텍스트와 진행바를 표시해 체감 지연을 완화.
  - 결과 화면에 종목별 구성 비율/배분금액 카드와 체결 내역 종목 라벨 표시를 추가.


- `components/PortfolioSection.jsx`
  - `모의 투자 시뮬레이션 인터페이스`를 확장해 초보자용 주문 흐름을 추가.
  - 로컬 모의 계좌 상태(현금/초기 현금/체결 이력)를 `localStorage`로 사용자별(`STORAGE_PREFIX + user email`) 저장/복원.
  - 매수·매도 주문 로직에 수량/가격 유효성 검사, 수수료 반영, 잔액 예측, 보유 수량 초과 방지, 실패 사유 메시지 표시를 추가.
  - 주문 모달에서 즉시 계산되는 `예상 거래금액/수수료/주문 후 잔액` 패널을 추가해 초보자 가독성 강화.
  - 포트폴리오 목록에 자산 구성(파이차트) 및 체결 이력 패널을 추가, 보유종목별 수익률 계산 표시를 고도화.
  - 초보자용 3단계 가이드 텍스트 블록을 상단에 추가.
  - 초보자를 위한 샘플 종목 셀렉터(`AAPL/MSFT/TSLA/NVDA/AMZN/GOOGL`)를 추가해, 티커를 모르는 사용자도 즉시 주문 화면으로 이동해 체험 가능하게 개선.
  - 주문 모달에 빠른 시작 칩(예시 종목 4개)도 추가해 스크롤 없이 바로 접근 가능하게 보강.
- `app/page.js`
  - 로그인 상태를 `localStorage`에 보존하도록 복구 로직 추가.
  - 로그인 정보에 `expiresAt`을 추가해 30일간 유지되도록 영속성 정책 적용.
  - 로그인 성공 시 사용자 정보를 저장하고, 초기 렌더 시 복원되면 자동 로그인 처리.
  - 로그아웃 시 저장값을 삭제해 세션이 명확히 종료되도록 정리.
  - 네비게이션에서 `모의 투자(포트폴리오)` 진입 경로를 텍스트로 노출하고, 대시보드에서 모의 투자 화면으로 바로 이동할 수 있는 버튼을 추가해 초보자 가이드를 개선.
  - 학습 플로우에 `백테스팅` 메뉴를 추가하고 `BacktestSection`을 연결.
- `components/BacktestSection.jsx` (신규)
  - 백테스트 실행 화면을 신설해 MA 교차 전략 입력/실행/결과 조회를 제공.
  - 결과 지표(총 수익률, MDD, 승률, 거래 횟수), 자산 곡선, 체결 내역, 초보자용 종목 바로가기 버튼을 추가.
- `components/BacktestSection.test.jsx`
  - 백테스트 컴포넌트 유닛 테스트 뼈대를 추가해 심볼 툴팁 렌더, 티커 버튼 클릭 반영, `/api/backtest/run` 요청 payload를 검증.
- `components/LoginPage.test.jsx`
  - 로그인/회원가입 경로의 API mock 기반 유닛 테스트를 추가해 인증 플로우 핵심 케이스(성공 응답, 화면 상태 전환)를 검증.
- `app/page.test.jsx`
  - 인증 진입 제어 테스트를 추가해 로그인 미보유 시 로그인 화면 노출, 유효 토큰 보유 시 메인 화면 노출을 검증.
- `package.json`
  - 프론트 단위 테스트를 위한 `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `@vitejs/plugin-react` 의존성 및 테스트 스크립트를 추가.
- `vitest.config.js`, `vitest.setup.js`
  - jsdom 환경과 공통 테스트 설정(테스트 유틸, `ResizeObserver` mock) 추가.

### Notes

- 이 릴리스에서는 백엔드 API 스펙은 변경 없이 기존 `/api/recent-status`, `/api/portfolio/*` 엔드포인트를 재사용.

### 2026-03-11 (구조 리팩토링 2차)

- `frontend/features/` 아래 feature 디렉토리를 dashboard/recent/historical/learn/settings으로 확장하고, `frontend/app/page.js`가 엔트리 컴포넌트를 `components/*` 대신 각 feature 브릿지 파일로 임포트하도록 변경.
- `app/page.js`의 화면 진입점 의존성을 더 명확한 `features/*` 경로로 정리해 UI 책임 경계 가시성 개선.

### 2026-03-11 (구조 리팩토링)

- `frontend/features/backtest/BacktestSection.jsx`, `frontend/features/auth/LoginPage.jsx`, `frontend/features/portfolio/PortfolioSection.jsx`를 추가해 기능별 폴더 골격을 분리.
- `frontend/app/page.js`가 백테스트/로그인/포트폴리오 영역을 `features/*` 경로에서 가져오도록 변경해 화면 엔트리의 책임을 분리.
- 라우트 테스트(`frontend/app/page.test.jsx`)는 신규 feature import 경로를 기준으로 mock 경로를 갱신해 구조 변경에도 테스트 의존성을 안정화.

### Notes

- 동일한 컴포넌트 로직은 `components/*.jsx` 하위에서 공통 유지되며, `features/*` 계층은 화면 진입점용 책임으로 확장 중.
