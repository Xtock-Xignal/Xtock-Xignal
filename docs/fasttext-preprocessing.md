# fastText preprocessing

이 프로젝트의 fastText 전처리는 `pipelines/fasttext/preprocessing.py`에 구현되어 있습니다.

## 목적
- fastText supervised 학습 포맷에 맞는 입력 생성
- 공식 튜토리얼의 기본 정규화 흐름 유지

## 적용 단계
1. **trim**
   - 앞뒤 공백 제거
2. **lowercase**
   - 모든 문자를 소문자로 변환
3. **punctuation spacing**
   - `.` `!` `?` `,` `'` `/` `(` `)` 주변에 공백 추가
   - 예: `Hello, WORLD!` → `hello , world !`
4. **whitespace normalize**
   - 연속 공백을 하나로 축소
5. **label formatting**
   - 라벨을 `__label__{label}` 형식으로 변환
   - 공백은 `_`로 치환

## 출력 예시
- 입력 텍스트: `Cloud demand rises!`
- 입력 라벨: `Information Technology`
- 출력:
  - `__label__Information_Technology cloud demand rises !`

## 구현 함수
- `normalize_text(text)`
  - fastText용 텍스트 정규화
- `normalize_label(label)`
  - fastText 라벨 접두사 형식 변환
- `to_fasttext_line(text, label)`
  - 학습용 한 줄 생성
- `decode_label(label)`
  - 예측 라벨 복원

## 참고
- fastText supervised tutorial의 예시는 구두점 spacing 후 lowercase를 수행합니다.
- 공식 문서: https://fasttext.cc/docs/en/supervised-tutorial.html
