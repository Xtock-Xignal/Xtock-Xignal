# Changelog

## 2026-03-11

### Backend Components

- `main.py`
  - 백테스트 요청 스키마를 단일 `symbol`에서 `symbol` 또는 `positions`(티커+비중 배열) 조합으로 확장.
  - 포트폴리오 백테스팅에서 종목별 비중 정규화/분배 로직 `_normalize_backtest_positions`를 추가.
  - 포트폴리오 백테스트 결과 집계 경로에서 종목별 시뮬레이션 결과를 병합해 누적 자산곡선, 거래 내역, 조합 지표를 반환.
  - 종합 지표에서 종목별 할당액/수익률 조회를 위한 `composition`, `position_results`를 함께 반환하도록 확장.
  - 종목별 가중치 집계 응답에서 실제 요청 가중치로 반영되도록 버그 보정.
- 기존 API(`/api/register`, `/api/login`, `/api/portfolio/list`, `/api/portfolio/add`, `/api/portfolio/remove`, `/api/recent-status`)는 기존 동작을 유지.
- `POST /api/backtest/run` 엔드포인트
  - 단기/장기 이동평균교차(`ma_cross`) 전략 기반 백테스트 실행 지원.
  - 기간 설정, 초기 자금, MA 윈도우, 수수료율 반영, 수익률/최대낙폭(MDD)/승률 계산 기능을 응답으로 제공.
  - 초보자 안내를 위해 입력 유효성(자금/구간/윈도우) 검증 및 실패 메시지를 포함.
- `tests/*`
  - pytest 기반의 백엔드 유닛 테스트 뼈대(`tests/test_backtest.py`)를 추가해 백테스트 포트폴리오 정규화/가중치 검사, 백테스트 심볼 목록 API, 백테스트 실행 흐름을 fixture 기반으로 검증할 수 있도록 구성.
- `requirements.txt`
  - 테스트 실행에 필요한 `pytest`, `pytest-cov`를 추가.
- `pytest.ini`
  - 기본 테스트 경로/실행 옵션을 정리한 설정 파일을 추가.

### Notes

- 프론트엔드 쪽 모의 투자 강화 작업과 맞물려 백엔드 레이어는 동작 검증 기준(`동기화 성공/실패 시 응답 처리`) 점검 대상으로만 확인.

### 2026-03-11 (구조 리팩토링)

- `app/services/backtest_service.py`를 추가해 백테스트 모델/순수 계산 로직을 `main.py`에서 분리.
- `main.py`는 기존 공개 API 핸들러(`run_backtest`, `list_backtest_symbols`, `_load_backtest_prices`, `_normalize_backtest_positions`)는 유지하면서 백테스트 로직 호출 지점으로 역할을 축소.
- 백테스트 경계에서 공통 상수(`NAME_TO_TICKER`, `SP500_HANDLES`)를 주입해 테스트 대체가 쉬운 형태로 정리.

### Notes

- 다음 단계: 인증/포트폴리오/시장요약 로직도 동일한 방식으로 `app/services/*`로 이동하여 레이어 책임 분리 강화 예정.

### 2026-03-11 (구조 리팩토링 2차)

- `app/api/*.py` 라우터 모듈을 추가해 인증, 실시간 근황, 과거 영향 분석, 포트폴리오, 대시보드 엔드포인트 책임을 `main.py`에서 분리.
- `main.py`는 라이프사이클, DI 유틸, 백테스트 위임 함수, 공통 라우터 등록까지만 유지하도록 정리.
- `app/services/{auth,market,historical,portfolio,dashboard,backtest}_service.py` 계층을 정비해 도메인 규칙과 라우팅 계층 경계를 명확화.
