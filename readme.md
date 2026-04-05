입력받은 텍스트의 클래스를 분류하는 모델 구현
클래스: Energy, Materials, Industrials, Utilities, Healthcare, Financials, Consumer Discretionary, Consumer Staples, Information Technology, Communication Services, Real Estate

모델: fastText, randomforest, bert. TF-IDF와 성능 비교해서 우세한 방식 사용

yfinance 라이브러리를 통해 경제 뉴스 수집
해당 기사를 gemini api에 전달 후 GICS sector 11개 중 하나로 분류
분류 결과 및 기사를 DB에 저장
해당 기사에서 stopwords를 제거함.
stock market domain words 그리고 s&p500 기업 또는 기업을 연상시키는 단어에 대한 설명을 gemini api를 통해 추가함.

요구사항
1. stopwords 제거에 특화된 모델 또는 corpus가 존재하는지 조사해야 함.
2. stock market domain words 및 s&p500 기업 또는 기업을 연상시키는 단어를 구분할 수 있는 모델 또는 이를 정의하는 corpus가 존재하는지 조사해야 함.
3. 기사의 GICS sector 분류를 위해 fastText, randomforest, bert 그리고 TF-IDF를 사용한 분류 모델 4가지가 대용량 텍스트 분류에 적합한지 조사해야 함.
4. 텍스트 분류에서 11개 클래스가 적절한 클래스 수인지 조사해야 함. 만약 적절하지 않다면 적절한 클래스 수를 제안해야 함.

전처리 문서
- `docs/fasttext-preprocessing.md`
- `docs/tfidf-preprocessing.md`

뉴스 적재 스크립트
- `python3 pipelines/load_data/build_news_datasets.py --overwrite`
- Gemini API 키는 `GEMINI_API_KEY` 또는 `geminiAPI.txt`에서 읽음
- 출력 파일:
  - `datasets/raw_news.csv` (`text`, `label` 두 컬럼만 저장)
  - `datasets/news_fastText.csv` (`text`, `label`, `normalized_text`, `normalized_label`, `fasttext_line`)
  - `datasets/news_tfidf.csv` (`text`, `label`, `tfidf_text_max_df`, `tfidf_text_custom_stopwords`)
