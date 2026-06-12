# 2026-05-25 변경사항 재확인 결과

확인일: 2026-05-26

대상 문서: `docs/CHANGE_SUMMARY_2026-05-21.md`의 `2026-05-25` 섹션

## 요약

`2026-05-25`에 기록된 구현 항목은 현재 코드 기준으로 대부분 반영되어 있습니다.

Docker Desktop 실행 후 컨테이너 내부에서 관련 백엔드/프론트 테스트를 재실행했고 모두 통과했습니다.

## 항목별 확인

| 기록 항목 | 확인 결과 | 근거 |
| --- | --- | --- |
| 주식 시뮬레이션 메뉴명/화면명 정리 | 완료 확인 | `frontend/app/page.jsx`에서 사이드바 메뉴 라벨, 헤더, 안내 문구가 `주식 시뮬레이션`으로 연결됨. `frontend/components/StockSimulationSection.jsx`도 화면 제목을 `주식 시뮬레이션`으로 표시함. |
| 시뮬레이션 프론트와 백엔드 API 연결 | 완료 확인 | `frontend/components/StockSimulationSection.jsx`에서 `/api/simulation/account`, `/api/simulation/portfolio/{id}`, `/api/simulation/history/{id}`, `/api/simulation/buy`, `/api/simulation/sell` 호출을 사용함. |
| 백엔드 simulation 라우터 활성화 | 완료 확인 | `backend/main.py`에서 `simulation_router`를 import하고 `app.include_router(simulation_router)`로 등록함. |
| 매수/매도/포트폴리오/거래내역 연동 | 완료 확인 | `backend/simulation/router.py`에 `/buy`, `/sell`, `/portfolio/{user_id}`, `/history/{user_id}` 엔드포인트가 있고, `backend/simulation/service.py`에서 보유 종목, 현금, 거래내역 컬렉션을 갱신함. 프론트도 주문 후 포트폴리오와 히스토리를 다시 불러옴. |
| 대시보드 기업 리스트 내부 차트를 주식 시뮬레이션 차트 형태로 변경 | 완료 확인 | `frontend/components/DashboardSection.jsx`에서 `/api/chart/history/{symbol}`과 WebSocket tick을 사용하고, 차트 설명에 종가, 이동평균, 거래량을 표시함. 관련 테스트도 `frontend/components/DashboardSection.test.jsx`에 존재함. |
| 관련 테스트 추가/수정 및 Docker 안에서 검증 완료 | 완료 확인 | `backend/tests/test_simulation.py`, `frontend/components/StockSimulationSection.test.jsx`, `frontend/components/DashboardSection.test.jsx`, `frontend/app/page.test.jsx`를 컨테이너 내부에서 실행했고 모두 통과함. |

## 확인한 주요 파일

- `backend/main.py`
- `backend/simulation/router.py`
- `backend/simulation/service.py`
- `backend/tests/test_simulation.py`
- `frontend/app/page.jsx`
- `frontend/components/StockSimulationSection.jsx`
- `frontend/components/StockSimulationSection.test.jsx`
- `frontend/components/DashboardSection.jsx`
- `frontend/components/DashboardSection.test.jsx`
- `frontend/app/page.test.jsx`

## 테스트 재실행 상태

실행 시도:

```bash
docker compose exec backend pytest tests/test_simulation.py
docker compose exec frontend npm run test:run -- StockSimulationSection.test.jsx DashboardSection.test.jsx app/page.test.jsx
```

결과:

```text
backend: 2 passed
frontend: 3 test files passed, 9 tests passed
```

참고:

- 프론트 테스트 실행 중 Recharts가 jsdom 환경에서 chart width/height가 0이라는 경고를 출력했지만, 테스트 실패는 발생하지 않았습니다.

## 실행 상태

현재 Docker Compose 서비스는 실행 중입니다.

```text
backend: http://localhost:8000
backend docs: http://localhost:8000/docs
frontend: http://localhost:3000
data-pipeline: http://localhost:8001
mongo-db: localhost:27017
```

## 결론

기능 구현은 현재 파일 기준으로 반영되어 있고, 관련 백엔드/프론트 테스트도 Docker 컨테이너 내부에서 통과했습니다. 최종 상태는 “구현 확인 및 컨테이너 테스트 통과”입니다.
