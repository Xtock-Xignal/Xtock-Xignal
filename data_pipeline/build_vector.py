import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import shutil
import os

def build_chroma_db():
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    input_file = os.path.join(BASE_DIR, 'sp500_sbert_input.jsonl')
    db_path = os.path.join(BASE_DIR, './chroma_db')
    model_name = 'BAAI/bge-m3'
    
    if os.path.exists(db_path):
        for filename in os.listdir(db_path):
            file_path = os.path.join(db_path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason {e}")
        
    df = pd.read_json(input_file, lines = True)
    
    print(df.columns.tolist())
    
    model = SentenceTransformer(model_name)
    
    client = chromadb.PersistentClient(path = db_path)
    
    try:
        client.delete_collection(name = 'sp500_companies')
        print("Deleted Existing Collection")
    except:
        pass
    
    collection = client.create_collection(name = 'sp500_companies')
    
    batch_size = 50
    total_batches = (len(df) // batch_size) + 1
    
    for i in tqdm(range(0, len(df), batch_size)):
        batch = df.iloc[i: i + batch_size]
        
        ids = batch['Ticker'].tolist()
        documents = batch['Enriched_Text'].tolist()
        
        metadatas = []
        for _, row in batch.iterrows():
            metadatas.append({
                "ticker": row['Ticker'],
                "name": row['Name'],
                "keywords": row['Generated_Keywords']
            })
            
        embeddings = model.encode(documents).tolist()
        
        collection.add(
            ids = ids,
            embeddings = embeddings,
            metadatas = metadatas,
            documents = documents
        )
        
    print("Indexing Complete")
    print(f"Total Items: {collection.count()}")
    
if __name__ == "__main__":
    build_chroma_db()