import json
import optuna
import numpy as np
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import os
import sys
import torch
import random

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from constants import ALIASES

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH_STATIC = os.path.join(BASE_DIR, "chromaDB/static")
DB_PATH_DYNAMIC = os.path.join(BASE_DIR, "chromaDB/dynamic")

TRAIN_FILES = [
    os.path.join(BASE_DIR, "json/train_news.json"),
    os.path.join(BASE_DIR, "json/train_tweet_stock.json"),
    os.path.join(BASE_DIR, "json/training2.json")
]
SP500_CSV = os.path.join(BASE_DIR, "csv/sp500_list.csv")

NUM_SAMPLES = 300
N_TRIALS = 30

def load_train_data():
    all_data = []
    
    if os.path.exists(SP500_CSV):
        sp500_df = pd.read_csv(SP500_CSV)
        sp500_tickers = set(sp500_df['ticker'].values)
    else:
        print("sp500_list.csv missing")
        sp500_tickers = set()
        
    print("Loading Training Data")
    for fpath in TRAIN_FILES:
        if not os.path.exists(fpath):
            print(f"Missing file: {fpath}")
            continue
        
        try:
            with open(fpath, 'r', encoding = 'utf-8') as f:
                data = json.load(f)
            for item in data:
                query = item.get('description') or item.get('text')
                raw_labels = item.get('sp500_labels') or item.get('tickers') or item.get('ticker')
                
                if not query or not raw_labels:
                    continue
                
                if isinstance(raw_labels, str):
                    labels = [raw_labels]
                else:
                    labels = raw_labels
                    
                valid_labels = [t for t in labels if t in sp500_tickers]
                
                if valid_labels:
                    all_data.append({
                        "query": query,
                        "labels": valid_labels
                    })
        except Exception as e:
            print(f"Error loading {fpath}: {e}")
        
    print(f"Loaded {len(all_data)} valid samples")
    
    if len(all_data) > NUM_SAMPLES:
        print(f"Randomly sampling {NUM_SAMPLES} items for training")
        return random.sample(all_data, NUM_SAMPLES)
    else:
        return all_data

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading Model (BGE-M3) on {device.upper()}")
model = SentenceTransformer('BAAI/bge-m3', device = device)

try:
    client_static = chromadb.PersistentClient(path = DB_PATH_STATIC)
    client_dynamic = chromadb.PersistentClient(path = DB_PATH_DYNAMIC)
    col_static = client_static.get_collection("sbert")
    col_dynamic = client_dynamic.get_collection("sbert")
except Exception as e:
    print(f"DB Error: {e}")
    sys.exit(1)
    
def calculate_score(query_vec, doc_vec_static, doc_vec_dynamic, alpha, beta, mention_bonus):
    score_static = np.dot(query_vec, doc_vec_static)
    score_dynamic = np.dot(query_vec, doc_vec_dynamic)
    return (alpha * score_static) + (beta * score_dynamic) + mention_bonus

def detect_mention_score(text, ticker):
    text_lower = text.lower()
    if f"${ticker.lower()}" in text_lower: return 1.0
    if ticker in ALIASES:
        for alias in ALIASES[ticker]:
            if alias in text_lower: return 1.0
    return 0.0

def objective(trial, dataset):
    alpha = trial.suggest_float("alpha", 0.3, 1.2)
    beta = trial.suggest_float("beta", 0.0, 1.0)
    lambda_mention = trial.suggest_float("lambda_mention", 0.5, 3.0)
    
    mrr_sum = 0
    total = 0
    
    for item in dataset:
        query_text = item['query']
        true_labels = item['labels']
        
        query_vec = model.encode(query_text, convert_to_numpy = True)
        
        res = col_static.query(
            query_embeddings = [query_vec.tolist()], 
            n_results = 30,
            include = ['embeddings', 'metadatas', 'documents']
            )
        
        candidates = []
        if res['ids'] and res['ids'][0] and res['embeddings'] is not None:
            ids = res['ids'][0]
            embeddings = res['embeddings'][0]
            
            for i, ticker in enumerate(ids):
                vec_static = np.array(embeddings[i])
                try:
                    res_dyn = col_dynamic.get(ids = [ticker], include = ['embeddings'])
                    if res_dyn['embeddings'] is not None and len(res_dyn['embeddings']) > 0:
                        vec_dyn = np.array(res_dyn['embeddings'][0])
                    else:
                        vec_dyn = np.zeros_like(vec_static)
                except Exception as e:
                    print(f"Error: {e}")
                    vec_dyn = np.zeros_like(vec_static)
                    
                # score_static = np.dot(query_vec, vec_static)
                # score_dynamic = np.dot(query_vec, vec_dyn)
                
                # if i == 0:
                #     print(f"Debug [{ticker}] Static: {score_static:.4f}, Dynamic: {score_dynamic:.4f}")
                
                mention_score = detect_mention_score(query_text, ticker) * lambda_mention
                score = calculate_score(query_vec, vec_static, vec_dyn, alpha, beta, mention_score)
                candidates.append((ticker, score))
                
            # if total > 2:
            #     sys.exit(0)
                
        candidates.sort(key = lambda x: x[1], reverse = True)
        score_added = 0.0
        for rank, (ticker, _) in enumerate(candidates[:5]):
            if ticker in true_labels:
                score_added = 1.0 / (rank + 1)
                break
        mrr_sum += score_added
        total += 1
    return mrr_sum / total if total > 0 else 0

if __name__== "__main__":
    train_data = load_train_data()
    
    if not train_data:
        print("No data to train")
        exit()
        
    print(f"Starting Optuna Optimization (Samples: {len(train_data)}, Trials: {N_TRIALS})")  
        
    study = optuna.create_study(direction = "maximize")
    
    with tqdm(total = N_TRIALS) as pbar:
        def callback(study, trial):
            pbar.update(1)
            pbar.set_description(f"Best Acc: {study.best_value:.4f}")
            
        study.optimize(lambda trial: objective(trial, train_data), n_trials = N_TRIALS, callbacks = [callback])
       
    print("\nBest Parameters:")
    print(json.dumps(study.best_params, indent = 4))
    print(f"Best Accuracy: {study.best_value:.4f}")
    
    best_params_path = os.path.join(BASE_DIR, "best_params.json")
    with open(best_params_path, 'w') as f:
        json.dump(study.best_params, f, indent = 4)
    print(f"Saved to {best_params_path}") 