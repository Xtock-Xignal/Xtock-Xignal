모델: fastText, bert. TF-IDF+RandomForest와 성능 비교해서 우세한 방식 사용

yfinance 라이브러리를 통해 경제 뉴스 수집
뉴스 기사를 산업으로 분류
분류 결과 및 기사를 DB에 저장
해당 기사에서 stopwords를 제거함.
stock market domain words 그리고 s&p500 기업 또는 기업을 연상시키는 단어에 대한 설명을 gemini api를 통해 추가함.

클래스 분류
  - GICS 11개 섹터를 세부 산업 29개로 세분화 함. S&P 500 기업을 각 산업에 맞게 분류하고 산업이 중복되는 경우 모두 추가함.
  - news_raw.csv: BERT 학습에 사용. 전처리가 문맥 파악을 방해할 수 있어 전처리를 하지 않음. (Title, Full Text, Industry 컬럼)
  - news_tfidf.csv: TF-IDF + RandomForest 학습에 사용. stopword 제거, lemmatization 적용.
  - news_fasttext.csv: fastText 학습에 사용. 전용 튜토리얼 스타일의 구두점 spacing 및 소문자화 정규화 적용.

전처리 문서
- `docs/fasttext-preprocessing.md`
- `docs/tfidf-preprocessing.md`

뉴스 적재 스크립트
- `python3 pipelines/load_data/build_news_data.py` (limit_per_ticker 파라미터 조절 가능)
- Gemini API 키는 `GEMINI_API_KEY` 환경변수 또는 `geminiAPI.txt`에서 읽음
- 출력 파일:
  - `datasets/news_raw.csv` (`Title`, `Full Text`, `Industry`)
  - `datasets/news_fasttext.csv` (`text`, `label`, `normalized_text`, `normalized_label`, `fasttext_line`)
  - `datasets/news_tfidf.csv` (`text`, `label`, `tfidf_text_max_df`, `tfidf_text_custom_stopwords`)
