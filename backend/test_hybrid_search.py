import google.generativeai as genai
import chromadb
import os
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


load_dotenv(os.path.join(BASE_DIR, "../.env"))
 
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    GOOGLE_API_KEY = GOOGLE_API_KEY.strip()
if not GOOGLE_API_KEY:
    raise ValueError("Don't Exist GOOGLE API KEY. Check .env file")
genai.configure(api_key = GOOGLE_API_KEY)

llm_model = genai.GenerativeModel('gemini-flash-lite-latest')


db_path = os.path.join(BASE_DIR, './chroma_db')

client = chromadb.PersistentClient(path = db_path)
collection = client.get_collection(name = 'sp500_companies')
sbert_model = SentenceTransformer('BAAI/bge-m3')
finbert_model = pipeline("sentiment-analysis", model = "prosusAI/finbert")

def ask_gemini_for_context(tweet_text):
    prompt = f"""
    Analyze the following tweet and identify the specific public company related to it.
    If the product mentioned belongs to a specific company (e.g., 'Gemini' -> Google, 'Optimus' -> Tesla), identify that company.
    
    Tweet: "{tweet_text}"
    
    Return ONLY the Company Name and Ticker Symbol in this format:
    "Company: [Name], Ticker: [Ticker]"
    If you are not sure, return "Unknown".
    """
    
    try:
        response = llm_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f" Gemini API Error: {e}")
        return ""
    
def analyze_sentiment(text):
    try:
        res = finbert_model(text[:512])[0]
        return {"label": res['label'], "score": round(res['score'], 4)}
    except:
        return {"label": "neutral", "score": 0.0}
    
def hybrid_search(tweet_text):
    ai_context = ask_gemini_for_context(tweet_text)
    print(f" Gemini Context: {ai_context}")
    
    if "Unknown" not in ai_context and ai_context != "":
        expanded_query = f"{ai_context} {tweet_text}"
    else:
        expanded_query = tweet_text
        
    sentiment_result = analyze_sentiment(tweet_text)
        
    query_vector = sbert_model.encode(expanded_query).tolist()
    
    results = collection.query(
        query_embeddings = [query_vector],
        n_results = 3
    )
    
    top_companies = []
    if results['ids'] and results['ids'][0]:
        for i in range(len(results['ids'][0])):
            keywords = results['metadatas'][0][i].get('keywords', '')
            top_companies.append({
                "rank": i + 1,
                "ticker": results['ids'][0][i],
                "name": results['metadatas'][0][i]['name'],
                "score": results['distances'][0][i],
                "keywords": keywords
            })
            
    return {
            "input_text": tweet_text,
            "sentiment": sentiment_result,
            "matches": top_companies
        }

        
if __name__ == "__main__":
    test_tweets = [
        "Introducing Gemini 3. It’s the best model in the world for multimodal understanding, and our most powerful agentic + vibe coding model yet. Gemini 3 can bring any idea to life, quickly grasping context and intent so you can get what you need with less prompting. Find Gemini"
    ]

    for tweet in test_tweets:
        print("=" * 60)
        
        # 1. 검색 함수 호출 (트윗 1개씩)
        matches = hybrid_search(tweet)

        
        if not matches:
            print("No matches found.")
        else:
            sent = matches['sentiment']
            print(f"Sentiment: [{sent['label'].upper()}] (Score: {sent['score']})")
            
            print(f"Matched Companies: ")
            for m in matches['matches']:
                print(f" -{m['ticker']} ({m['name']})")
        print("\n")