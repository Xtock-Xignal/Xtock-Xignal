# TF-IDF preprocessing

이 프로젝트의 TF-IDF + RandomForest 전처리는 `pipelines/tfidf_randomforest/preprocessing.py`에 구현되어 있습니다.

## 목적
- 영어 텍스트를 TF-IDF 벡터화에 적합한 형태로 정리
- 표면형 분산을 줄이고 해석 가능한 feature 유지
- stopwords 전략을 `max_df`와 custom TF-IDF 방식으로 비교 가능하게 구성

## 적용 단계
1. **lowercase**
   - 모든 문자를 소문자로 변환
2. **tokenization**
   - 정규식 `[a-z0-9가-힣]+` 기준 토큰 추출
   - 구두점은 제거됨
3. **POS-aware lemmatization**
   - `nltk.pos_tag`로 품사 태깅
   - Penn Treebank 품사를 WordNet 품사로 변환
   - `WordNetLemmatizer`로 표제어 추출
4. **stopword filtering**
   - 기본 불용어 제거
   - 추가로 두 전략 비교 가능
     - `max_df`
     - custom TF-IDF stopwords
5. **join**
   - 정제된 토큰을 공백 문자열로 재조합

## stopwords 전략

### 1) `max_df`
- `TfidfVectorizer(max_df=...)`에 맡겨 문서빈도가 과도하게 높은 단어를 제거
- 장점
  - 구현 단순
  - scikit-learn 기본 기능 활용
- 용도
  - baseline

### 2) `custom_tfidf`
- 학습 텍스트에서
  - 문서빈도가 높고
  - 평균 TF-IDF가 낮은 단어를
  - custom stopwords로 추가 선택
- 장점
  - 데이터셋 특화 불용어 선별 가능
- 용도
  - domain-specific stopwords 비교

## lemmatization을 택한 이유
- 영어 텍스트에서 `run`, `running`, `ran` 등을 더 자연스럽게 통합
- stemming보다 단어 훼손이 적음
- TF-IDF feature를 사람이 해석하기 쉬움
- RandomForest 입력 feature 분산을 줄이는 데 유리할 수 있음

## NLTK 리소스 준비
lemmatization에 필요한 리소스:
- `averaged_perceptron_tagger_eng`
- `wordnet`
- `omw-1.4`

다운로드 스크립트:
```bash
python3 scripts/download_nltk_resources.py
```

커스텀 다운로드 경로 지정:
```bash
python3 scripts/download_nltk_resources.py --download-dir /path/to/nltk_data
```

lemmatization 적용 확인:
```bash
python3 scripts/check_tfidf_lemmatization.py
```

## 구현 함수
- `tokenize(text)`
- `lemmatize_tokens(text)`
- `normalize_tokens(text)`
- `preprocess_text(text, stopwords=None)`
- `derive_custom_stopwords_by_tfidf(...)`
- `build_stopword_strategy(...)`

## 참고
- scikit-learn `TfidfVectorizer` 문서:
  - https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
