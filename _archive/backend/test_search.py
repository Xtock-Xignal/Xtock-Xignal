import chromadb
from sentence_transformers import SentenceTransformer


db_path = '/p_project/chroma_db'
client = chromadb.PersistentClient(path = db_path)
collection = client.get_collection(name = 'sp500_companies')
model = SentenceTransformer('all-MiniLM-L6-v2')

def test_search(test_tweets: str):

    all_results = []
    
    for tweet in test_tweets:
        
        query_vector = model.encode(tweet).tolist()
        
        results = collection.query(            
            query_embeddings = [query_vector],
            n_results = 3
        )
        
        if not results['ids'] or not results['ids'][0]:
            all_results.append({
                "tweet": tweet,
                "matches": []
            })
            continue
        
        current_tweet_matches = []
        
        count = len(results['ids'][0])
        
        for i in range(count):
            ticker = results['ids'][0][i]
            score = results['distances'][0][i]
            metadatas = results['metadatas'][0][i]
            
            current_tweet_matches.append({
                "rank": i + 1,
                "ticker": ticker,
                "name": metadatas['name'],
                "similarity_score": score,
                "keywords": metadatas.get('keywords', '')
            })
        
        all_results.append({
            "tweet": tweet,
            "matches": current_tweet_matches
        })
        
    return all_results
        
if __name__ == "__main__":
    test_tweets = [
        "CUDA is a parallel computing platform and application programming interface (API) model. It allows software developers to use a CUDA-enabled graphics processing unit (GPU) for general purpose processing, an approach known as GPGPU (General-Purpose computing on Graphics Processing Units).",
    ]

    results = test_search(test_tweets)
    
    for result in results:
        print(f"Tweet: {result['tweet']}")
        print("=" * 60)
        for item in result['matches']:
            print(f"Rank {item['rank']}: {item['ticker']} ({item['name']})")
            print(f"Similarity Score: {item['similarity_score']:.4f}")
            print(f"Key Words: {item['keywords']}")
            print("-" * 60)