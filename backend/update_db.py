import os
import json
import time
from pymongo import MongoClient
from google import genai

# 환경 변수 및 DB 연결 설정
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://xtock-mongodb:27017")
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock_xignal")

# Gemini API 키가 환경 변수에 등록되어 있어야 합니다.
API_KEY = os.getenv("GEMINI_API_KEY", "여기에_직접_API_키를_입력해도_됩니다")
client = genai.Client(api_key=API_KEY)

try:
    client = MongoClient(MONGO_URI)
    db = client[MONGODB_NAME]
    terms_col = db["terms_dict"]
except Exception as e:
    print(f"MongoDB 연결 실패: {e}")
    exit(1)

def batch_update_aliases():
    # aliases 필드가 없거나, 배열의 길이가 0인 문서들만 검색
    query = {"$or": [{"aliases": {"$exists": False}}, {"aliases": {"$size": 0}}]}
    terms_to_update = list(terms_col.find(query))

    if not terms_to_update:
        print("업데이트가 필요한 단어가 없습니다.")
        return

    print(f"총 {len(terms_to_update)}개의 단어에 대해 AI 동의어 추출을 시작합니다.")

    for term_doc in terms_to_update:
        en_term = term_doc.get("en_term", "")
        if not en_term:
            continue
            
        print(f"처리 중: {en_term}")

        prompt = f"""
        당신은 금융 전문가입니다. 
        금융 용어 '{en_term}'에 대해 자주 쓰이는 약어, 약자, 또는 명백한 유의어가 있다면 영어로만 1~3개 추출해주세요.
        예를 들어 'The Federal Reserve'의 경우 'Fed', 'FRB' 등을 추출합니다.
        해당 사항이 없다면 빈 배열을 반환하십시오.
        반드시 아래 JSON 형식으로만 응답해야 합니다. 마크다운 기호는 생략하십시오.
        {{
            "aliases": ["동의어1", "동의어2"]
        }}
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(res_text)
            
            aliases = data.get("aliases", [])
            
            # MongoDB 문서 업데이트
            terms_col.update_one(
                {"_id": term_doc["_id"]},
                {"$set": {"aliases": aliases}}
            )
            print(f"업데이트 완료: {en_term} -> {aliases}")
            
        except Exception as e:
            print(f"에러 발생 ({en_term}): {str(e)}")

        # 무료 API 호출 속도 제한(Rate Limit)을 피하기 위한 지연 시간
        time.sleep(2)

    print("모든 단어의 마이그레이션이 완료되었습니다.")

if __name__ == "__main__":
    batch_update_aliases()