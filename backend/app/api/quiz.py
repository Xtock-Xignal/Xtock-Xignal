from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Query
from google import genai
from pymongo import MongoClient

load_dotenv()

router = APIRouter()

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://xtock-mongodb:27017"
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock_xignal")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGODB_NAME]
quiz_collection = db["quiz_bank"]

# 학습센터 LearningCenter.jsx의 LEARN_SECTIONS와 동일한 단어 목록
QUIZ_WORDS = [
    {"term": "주식", "def": "회사가 자본을 모으기 위해 발행하는 지분 증서로, 주식을 보유하면 해당 회사의 소유권 일부를 가진다."},
    {"term": "지수 (Index)", "def": "코스피, 코스닥, S&P500처럼 여러 종목의 가격을 종합해 시장의 전반적인 움직임을 나타내는 수치."},
    {"term": "시가 / 종가", "def": "시가는 하루 중 처음 체결된 가격, 종가는 장 종료 직전에 체결된 마지막 가격."},
    {"term": "고가 / 저가", "def": "고가는 해당 기간 동안 가장 높게 거래된 가격, 저가는 가장 낮게 거래된 가격."},
    {"term": "거래량", "def": "특정 기간 동안 거래된 주식의 수량으로, 시장의 관심도와 유동성을 나타내는 지표."},
    {"term": "시가총액", "def": "주가 × 발행 주식 수로 계산되며, 회사의 시장에서 평가받는 전체 가치."},
    {"term": "캔들 차트", "def": "시가, 고가, 저가, 종가를 하나의 막대로 표현하는 차트 형태. 빨간색/초록색 봉으로 상승/하락 표현."},
    {"term": "이동평균선 (MA)", "def": "특정 기간 동안의 평균 가격을 선으로 이은 지표로, 추세의 방향과 강도를 파악할 때 사용."},
    {"term": "RSI (Relative Strength Index)", "def": "과매수/과매도 구간을 판단하는 모멘텀 지표로, 일반적으로 70 이상이면 과매수, 30 이하면 과매도로 본다."},
    {"term": "MACD", "def": "단기와 장기 이동평균선의 차이를 이용해 추세 전환 시점을 찾는 보조지표."},
    {"term": "지지선 / 저항선", "def": "지지선은 주가가 잘 내려가지 않는 바닥 구간, 저항선은 주가가 잘 뚫지 못하는 천장 구간."},
    {"term": "거래량 급증", "def": "평소보다 거래량이 크게 늘어난 상태로, 추세 전환이나 강한 움직임의 신호."},
    {"term": "재무제표", "def": "손익계산서, 재무상태표, 현금흐름표 등 회사의 재무 상태와 경영 성과를 보여주는 보고서."},
    {"term": "PER (주가수익비율)", "def": "주가를 주당순이익(EPS)으로 나눈 값으로, 현재 주가가 이익에 비해 비싼지 싼지 판단."},
    {"term": "PBR (주가순자산비율)", "def": "주가를 주당순자산으로 나눈 값으로, 회사의 장부가치 대비 주가 수준."},
    {"term": "ROE (자기자본이익률)", "def": "자기자본 대비 얼마만큼의 이익을 냈는지를 보여주는 지표로, 높을수록 효율적인 경영을 의미."},
    {"term": "EPS (주당순이익)", "def": "당기순이익을 발행 주식 수로 나눈 값으로, 한 주당 벌어들이는 이익."},
    {"term": "배당수익률", "def": "배당금을 주가로 나눈 비율로, 주식을 보유했을 때 받는 현금 배당의 수익률."},
    {"term": "감성 분석 (Sentiment Analysis)", "def": "트위터, 뉴스 등 텍스트 데이터를 분석해 긍정/부정 같은 정서 상태를 파악하는 기법."},
    {"term": "백테스트 (Backtesting)", "def": "과거 데이터에 특정 투자 전략을 적용해, 전략이 과거에는 어떻게 성과를 냈는지 검증하는 과정."},
    {"term": "팩터 (Factor)", "def": "주가 수익률에 영향을 미치는 요인(가치, 모멘텀, 규모 등)을 의미하며, 퀀트 전략의 기반이 된다."},
    {"term": "알파 (Alpha)", "def": "시장 수익률 대비 초과 수익을 의미하며, 전략이나 운용 능력이 만들어 낸 추가 성과."},
    {"term": "과적합 (Overfitting)", "def": "모델이 학습 데이터에만 지나치게 맞춰져 실제 투자 환경에서는 성과가 떨어지는 현상."},
    {"term": "변동성 (Volatility)", "def": "주가가 위아래로 움직이는 정도를 나타내며, 변동성이 클수록 위험도와 수익 가능성이 모두 커진다."},
    {"term": "손절 (Stop Loss)", "def": "손실이 일정 수준을 넘기기 전에 미리 정해 둔 가격에서 매도해 손실을 제한하는 행위."},
    {"term": "분산 투자", "def": "여러 종목·섹터·자산에 나누어 투자해, 한 곳의 손실이 전체 자산에 미치는 영향을 줄이는 전략."},
    {"term": "레버리지", "def": "대출이나 파생상품을 이용해 실제 자본보다 더 큰 금액을 운용하는 것으로, 수익과 손실이 모두 확대된다."},
    {"term": "드로다운 (Drawdown)", "def": "자산 가치가 최고점 대비 얼마나 감소했는지를 나타내는 지표로, 계좌가 맞은 최대 타격을 의미한다."},
    {"term": "가치 투자", "def": "내재 가치에 비해 저평가된 기업을 찾아 장기 보유하는 전략으로, 워렌 버핏의 투자 스타일로 유명하다."},
    {"term": "성장 투자", "def": "현재 이익보다는 향후 고성장 가능성이 높은 기업에 집중하는 전략으로, 기술주·혁신기업에 많이 적용된다."},
    {"term": "모멘텀 투자", "def": "최근에 잘 오른(또는 내린) 종목이 한동안 그 방향으로 계속 움직이는 경향을 이용하는 전략."},
    {"term": "배당 투자", "def": "안정적인 배당금을 꾸준히 지급하는 기업에 투자해 현금 흐름과 장기 수익을 동시에 추구하는 전략."},
    {"term": "퀀트 투자", "def": "수학·통계·알고리즘을 이용해 정량적인 규칙에 따라 기계적으로 매매하는 투자 방식."},
]

MIN_QUIZ_THRESHOLD = 20  # DB에 이 수 미만이면 자동 추가 생성


def _get_existing_questions() -> set[str]:
    return {doc["question"] for doc in quiz_collection.find({}, {"question": 1, "_id": 0})}


def _generate_via_gemini(words: list[dict], existing_questions: set[str]) -> list[dict]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return []

    all_terms = [w["term"] for w in words]
    word_list_str = "\n".join(f'- term: "{w["term"]}", def: "{w["def"]}"' for w in words)

    prompt = f"""당신은 금융 교육 퀴즈 출제자입니다. 아래 금융 용어 목록을 바탕으로 다양한 유형의 4지선다 퀴즈를 한국어로 생성하세요.

퀴즈 유형을 다양하게 섞어주세요:
- 설명을 보고 용어 맞추기: "다음 설명에 해당하는 용어는?"
- 용어를 보고 설명 맞추기: "'{term}'에 대한 올바른 설명은?"
- 특징/조건으로 맞추기: "~할 때 사용하는 지표는?"

규칙:
1. 각 퀴즈의 오답 3개는 반드시 아래 용어 목록 중에서 선택하세요.
2. 동일하거나 유사한 질문은 생성하지 마세요.
3. options 배열에는 정답과 오답이 무작위 순서로 섞여 있어야 합니다.

용어 목록:
{word_list_str}

반드시 아래 형식의 JSON 배열만 반환하세요 (설명 없이):
[
  {{
    "question": "질문 내용",
    "answer": "정답 용어",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "source_term": "출처 용어"
  }}
]

{len(words)}개의 퀴즈를 생성하세요.
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        quizzes = json.loads(response.text.strip())

        now = datetime.now(timezone.utc)
        new_quizzes = []
        for q in quizzes:
            question = q.get("question", "").strip()
            answer = q.get("answer", "").strip()
            options = q.get("options", [])
            source_term = q.get("source_term", "").strip()

            if not question or not answer or len(options) != 4:
                continue
            if answer not in options:
                continue
            if question in existing_questions:
                continue
            if not any(t in all_terms for t in options):
                continue

            new_quizzes.append({
                "question": question,
                "answer": answer,
                "options": options,
                "source_term": source_term,
                "created_at": now,
            })
            existing_questions.add(question)

        return new_quizzes
    except Exception as exc:
        print(f"[quiz] Gemini 퀴즈 생성 실패: {exc}")
        return []


@router.post("/generate")
def generate_quizzes():
    existing_questions = _get_existing_questions()
    current_count = len(existing_questions)

    if current_count >= MIN_QUIZ_THRESHOLD:
        return {"success": True, "generated": 0, "total": current_count, "msg": "퀴즈 DB가 충분합니다."}

    new_quizzes = _generate_via_gemini(QUIZ_WORDS, existing_questions)

    if new_quizzes:
        quiz_collection.insert_many(new_quizzes)

    total = quiz_collection.count_documents({})
    return {"success": True, "generated": len(new_quizzes), "total": total}


@router.get("/fetch")
def fetch_quizzes(count: int = Query(default=8, ge=1, le=50)):
    total = quiz_collection.count_documents({})

    if total == 0:
        return {"success": False, "quizzes": [], "total": 0, "msg": "퀴즈 DB가 비어있습니다."}

    sample_size = min(count, total)
    quizzes = list(quiz_collection.aggregate([
        {"$sample": {"size": sample_size}},
        {"$project": {"_id": 0, "question": 1, "answer": 1, "options": 1, "source_term": 1}},
    ]))

    return {"success": True, "quizzes": quizzes, "total": total}
