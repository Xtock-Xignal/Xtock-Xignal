import os
import shutil

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_FILE = os.path.join(BASE_DIR, "sp500_sbert_input.jsonl")
DYNAMIC_FILE = os.path.join(BASE_DIR, "sp500_financials.jsonl")

DB_ROOT = os.path.join(BASE_DIR, "../backend/chromaDB")
STATIC_DB_PATH = os.path.join(DB_ROOT, "static")
DYNAMIC_DB_PATH = os.path.join(DB_ROOT, "dynamic")


def build_dual_db():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Model (BGE-M3) on {device.upper()}")
    model = SentenceTransformer("BAAI/bge-m3", device=device)

    if os.path.exists(DB_ROOT):
        print("Cleaning up existing DB")
        try:
            shutil.rmtree(DB_ROOT)
        except Exception as e:
            print(f"Warning: Could not delete DB folder ({e})")

    os.makedirs(STATIC_DB_PATH, exist_ok=True)
    os.makedirs(DYNAMIC_DB_PATH, exist_ok=True)

    print("\nBuilding Static DB")
    if not os.path.exists(STATIC_FILE):
        print(f"Error: {STATIC_FILE} missing")
        return

    df_static = pd.read_json(STATIC_FILE, lines=True)
    client_static = chromadb.PersistentClient(path=STATIC_DB_PATH)
    col_static_sbert = client_static.get_or_create_collection(name="sbert")
    col_static_finbert = client_static.get_or_create_collection(name="finbert")

    batch_size = 64
    for i in tqdm(range(0, len(df_static), batch_size), desc="Indexing Static"):
        batch = df_static.iloc[i : i + batch_size]

        ids = batch["Ticker"].tolist()
        docs = batch["Enriched_Text"].tolist()

        metadatas = []
        for _, row in batch.iterrows():
            metadatas.append(
                {
                    "ticker": row["Ticker"],
                    "name": row["Name"],
                    "keywords": row.get("Generated_Keywords", ""),
                }
            )

        embeddings = model.encode(docs, show_progress_bar=False).tolist()

        col_static_sbert.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)
        col_static_finbert.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)

    print("Buildind Dynamic DB")
    if not os.path.exists(DYNAMIC_FILE):
        print(f"Error: {DYNAMIC_FILE} missing. Using Wiki Data as placeholder for Dynamic DB")
        df_dynamic = df_static
        docs_col = "Enriched_Text"
    else:
        print(f"Loading Financials Data from {DYNAMIC_FILE}")
        df_dynamic = pd.read_json(DYNAMIC_FILE, lines=True)
        docs_col = "Financial_Text"

    client_dynamic = chromadb.PersistentClient(path=DYNAMIC_DB_PATH)
    col_dynamic_sbert = client_dynamic.get_or_create_collection(name="sbert")
    col_dynamic_finbert = client_dynamic.get_or_create_collection(name="finbert")

    for i in tqdm(range(0, len(df_dynamic), batch_size), desc="Indexing Dynamic"):
        batch = df_dynamic.iloc[i : i + batch_size]

        ids = batch["Ticker"].tolist()
        docs = batch[docs_col].tolist()

        metadatas = []
        for _, row in batch.iterrows():
            metadatas.append(
                {
                    "ticker": row["Ticker"],
                    "name": row["Name"],
                    "status": row.get("Latest_Status", "Unknown"),
                    "Financial_Text": row.get("Financial_Text", ""),
                }
            )

        embeddings = model.encode(docs, show_progress_bar=False).tolist()

        col_dynamic_sbert.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)
        col_dynamic_finbert.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=docs)

    print("\n Dual DB Construction Complete")
    print(f"    path: {DB_ROOT}")


if __name__ == "__main__":
    build_dual_db()

