import os
import google.generativeai as genai
from dotenv import load_dotenv

def test_gemini_term_explanation(term):
    print("[Info] Starting Gemini API test for term: " + term)
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("[Error] GOOGLE_API_KEY not found in .env file.")
        return
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 날카롭게 깎아낸 영문 시스템 프롬프트 (출력은 한국어 강제)
        prompt = f"""Act as a highly intuitive financial mentor for stock market beginners.
                     Your task is to explain the financial term '{term}'.

                     Strict Constraints:
                     1. Maximum length is exactly 3 sentences.
                     2. Absolutely NO complex financial jargon. Explain it as if you are talking to a middle school student.
                     3. You MUST include a simple, relatable everyday analogy.
                     4. The final output MUST be written entirely in natural, friendly Korean.
                     5. DO NOT include any conversational greetings, intros, or filler phrases (e.g., "안녕하세요", "제가 설명해 드릴게요"). Start the explanation immediately.
                     """
        
        print("[Info] Sending structured English prompt to Gemini API...")
        response = model.generate_content(prompt)
        
        print("[Success] Received response from Gemini:")
        print("-" * 50)
        print(response.text.strip())
        print("-" * 50)
        
    except Exception as e:
        print("[Error] Gemini API call failed. Reason: " + str(e))

if __name__ == "__main__":
    # 까다로운 주식 은어로 테스트
    target_term = "Diamond Hands (다이아몬드 핸즈)"
    test_gemini_term_explanation(target_term)