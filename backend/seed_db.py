import json
import os
from pymongo import MongoClient
from dotenv import load_dotenv

def seed_database():
    print("[Info] Starting database seeding process...")

    # 1. 환경 변수 로드 및 DB 연결
    load_dotenv()
    # 로컬 테스트용이므로 기본 몽고DB 주소 사용, 도커 환경에 맞게 변경 가능
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017") 
    
    try:
        client = MongoClient(mongo_uri)
        db = client["xtock_xignal"] # 우리가 사용할 메인 DB 이름
        collection = db["financial_terms"]
        print("[Info] Successfully connected to MongoDB.")
    except Exception as e:
        print("[Error] Failed to connect to MongoDB. Reason: " + str(e))
        return

    # 2. JSON 파일 읽기 (backend/json/seed.json)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "json", "seed.json")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            terms_data = json.load(f)
            print("[Info] Loaded " + str(len(terms_data)) + " terms from JSON file.")
    except FileNotFoundError:
        print("[Error] JSON file not found at: " + file_path)
        return

    # 3. 데이터 밀어넣기 (중복 방지)
    inserted_count = 0
    for term in terms_data:
        # en_term 기준으로 이미 DB에 있는지 확인
        exists = collection.find_one({"en_term": term["en_term"]})
        if not exists:
            collection.insert_one(term)
            inserted_count += 1
        else:
            print("[Skip] Term already exists in DB: " + term["en_term"])

    print("[Success] Seeding completed. Inserted " + str(inserted_count) + " new terms.")

if __name__ == "__main__":
    seed_database()