# backend/search_logic.py
import os
import json
import torch
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer
from constants import ALIASES

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH_STATIC = os.path.join(BASE_DIR, "chromaDB/static")
DB_PATH_DYNAMIC = os.path.join(BASE_DIR, "chromaDB/dynamic")
BEST_PARAMS_PATH = os.path.join(BASE_DIR, "best_params.json")

class SearchEngine:
    def __init__(self):
        # 1. 파라미터 로드
        if os.path.exists(BEST_PARAMS_PATH):
            with open(BEST_PARAMS_PATH, 'r') as f:
                params = json.load(f)
            self.alpha = params.get('alpha', 0.7)
            self.beta = params.get('beta', 0.3)
            self.lambda_mention = params.get('lambda_mention', 1.0)
            print(f"Loaded Best Params: α={self.alpha:.2f}, β={self.beta:.2f}")
        else:
            print("Best params not found. Using defaults.")
            self.alpha, self.beta, self.lambda_mention = 0.7, 0.3, 1.0

        # 2. 모델 로드
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading BGE-M3 Model on {device.upper()}...")
        self.model = SentenceTransformer('BAAI/bge-m3', device=device)

        # 3. DB 연결
        try:
            self.client_static = chromadb.PersistentClient(path=DB_PATH_STATIC)
            self.client_dynamic = chromadb.PersistentClient(path=DB_PATH_DYNAMIC)
            self.col_static = self.client_static.get_collection("sbert")
            self.col_dynamic = self.client_dynamic.get_collection("sbert")
            print("ChromaDB Connected Successfully.")
        except Exception as e:
            print(f"DB Connection Error: {e}")
            self.col_static = None
            self.col_dynamic = None

    def calculate_score(self, query_vec, vec_static, vec_dyn, mention_bonus):
        score_static = np.dot(query_vec, vec_static)
        score_dynamic = np.dot(query_vec, vec_dyn)
        return (self.alpha * score_static) + (self.beta * score_dynamic) + mention_bonus

    def detect_mention_score(self, text, ticker):
        text_lower = text.lower()
        if f"${ticker.lower()}" in text_lower: return 1.0
        if ticker in ALIASES:
            for alias in ALIASES[ticker]:
                if alias in text_lower: return 1.0
        return 0.0

    def search(self, query_text: str, top_k: int = 5):
        if not self.col_static:
            return []

        # 1. 쿼리 임베딩
        query_vec = self.model.encode(query_text, convert_to_numpy=True)
        
        # 2. 1차 검색 (Static DB)
        res = self.col_static.query(
            query_embeddings=[query_vec.tolist()], 
            n_results=top_k * 3, 
            include=['embeddings', 'metadatas']
        )
        
        if not res['ids'] or not res['ids'][0]:
            return []

        ids = res['ids'][0]
        embeddings = res['embeddings'][0]
        metadatas = res['metadatas'][0]
        
        candidates = []
        
        # 3. Dynamic DB 조회 및 점수 재계산
        for i, ticker in enumerate(ids):
            vec_static = np.array(embeddings[i])
            
            # 변수 초기화 (안전장치)
            vec_dyn = np.zeros_like(vec_static)
            dyn_meta = {}
            
            try:
                res_dyn = self.col_dynamic.get(ids=[ticker], include=['embeddings', 'metadatas'])
                
                # 메타데이터 확보
                if res_dyn['metadatas'] is not None and len(res_dyn['metadatas']) > 0:
                    dyn_meta = res_dyn['metadatas'][0]

                # 임베딩 확보
                if res_dyn['embeddings'] is not None and len(res_dyn['embeddings']) > 0:
                    vec_dyn = np.array(res_dyn['embeddings'][0])
                    
            except Exception as e:
                print(f"Dynamic Fetch Error ({ticker}): {e}")
                
            # 점수 계산
            mention_score = self.detect_mention_score(query_text, ticker) * self.lambda_mention
            final_score = self.calculate_score(query_vec, vec_static, vec_dyn, mention_score)
            
            real_symbol = metadatas[i].get('symbol', ticker)
                        
            candidates.append({
                "symbol": real_symbol,  # 프론트엔드 통일성을 위해 ticker -> symbol
                "name": metadatas[i].get('name', ''),
                "score": float(final_score),
                "keywords": metadatas[i].get('keywords', ''),
                "financial_summary": dyn_meta.get('Financial_Text', 'N/A')
            })
            
        # 4. 최종 정렬
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:top_k]

# 전역 인스턴스 (main.py에서 import해서 사용)
search_engine = SearchEngine()