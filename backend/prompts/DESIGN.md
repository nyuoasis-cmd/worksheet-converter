# 프롬프트 설계 문서

## 1. 설계 원칙

- **프롬프트 1개**: 모든 학년/과목/언어를 단일 프롬프트로 처리
- **분기 없음**: 모드1(프롬프트 only)과 모드2(프롬프트+RAG)의 차이는 `{rag_context}` 변수의 값 유무뿐
- **확장 = 데이터 추가**: 새 언어/과목/학년 추가 시 코드 변경 제로

## 2. 변수 슬롯

| 슬롯 | 타입 | 설명 | 빈값 시 동작 |
|------|------|------|-------------|
| `{rag_context}` | str | 매칭된 어휘+교과지식 (RAG 결과) | 빈 문자열 → Gemini가 자체 판단으로 변환 |
| `{selected_languages}` | str | 사용자가 선택한 외국어 목록 (쉼표 구분) | 빈 문자열 → 다국어 병기 생략 |
| `{difficulty_level}` | str | 변환 난이도 ("쉬움"/"보통"/"매우 쉬움") | 기본값 "쉬움" |

### 모드1 vs 모드2 비교

```
모드1 (RAG 없음):
  rag_context = ""
  → Gemini가 이미지만으로 변환. 용어 번역은 Gemini 자체 능력에 의존.

모드2 (RAG 있음):
  rag_context = "### 핵심 용어\n광합성: 식물이 빛으로 음식을 만드는 것 (vi: quang hợp, zh: 光合作用)\n..."
  → Gemini가 제공된 용어 DB를 우선 사용. 더 정확한 번역 보장.
```

동일 프롬프트, 동일 코드. `rag_context`가 비어 있으면 해당 섹션이 자연스럽게 무시됨.

## 3. 변환 규칙 (프롬프트에 하드코딩)

1. 문제 번호, 문제 구조, 보기 순서 **절대 변경 금지**
2. 정답이 바뀌는 변환 **절대 금지**
3. 어려운 단어 뒤에 괄호로 쉬운 설명 삽입
   - 예: `이산화탄소(= 우리가 내쉬는 공기)`
4. 외국어 모드 시 핵심 용어에만 다국어 병기
   - 예: `광합성(quang hợp / 光合作用)`
5. 문장은 짧게 (한 문장 15자 이내 권장)
6. 존댓말 사용 (~해요 체)

## 4. 출력 포맷 (HTML)

Gemini 응답은 구조화된 HTML로 반환됨. 프론트엔드가 이를 렌더링하고, 필요 시 PDF/HWPX 변환.

```html
<div class="worksheet">
  <div class="worksheet-header">
    <h1>{과목명} - {단원명}</h1>
    <p class="grade">{학년} {학기}</p>
  </div>

  <div class="question" data-number="1">
    <p class="question-text">
      1. 식물이 빛(= 해에서 오는 것)을 받아서 양분(= 음식)을 만드는 것을
      무엇이라고 해요?
      <span class="term-multilingual">광합성(quang hợp / 光合作用)</span>
    </p>
    <div class="choices">
      <p class="choice">① 광합성(quang hợp / 光合作用)</p>
      <p class="choice">② 호흡(hô hấp / 呼吸)</p>
      <p class="choice">③ 증산 작용(thoát hơi nước / 蒸散作用)</p>
      <p class="choice">④ 소화(tiêu hóa / 消化)</p>
    </div>
  </div>

  <!-- 추가 문제들... -->
</div>
```

### HTML 클래스 규칙
- `.worksheet`: 최상위 컨테이너
- `.worksheet-header`: 과목, 단원, 학년 정보
- `.question[data-number]`: 각 문제 (번호 보존)
- `.question-text`: 문제 본문
- `.choices`: 선택지 영역
- `.choice`: 개별 선택지
- `.term-multilingual`: 다국어 병기 용어 (하이라이트용)
- `.explanation`: 괄호 안 쉬운 설명

## 5. Gemini API 호출 전략

1. **단일 호출**: 이미지 + 시스템 프롬프트를 한 번에 전송
2. **OCR + 변환 통합**: 별도 OCR 단계 없이 Gemini Vision이 이미지를 읽고 바로 변환
3. **모델**: `gemini-2.5-flash` (비용 효율 + 한국어 성능)
4. **temperature**: 0.1 (변환 일관성 유지, 창의성 억제)

## 6. 에러 처리

- 이미지가 문제지가 아닌 경우: Gemini가 판단하여 안내 메시지 반환
- data/에 해당 과목 용어가 없는 경우: rag_context="" → 모드1로 자동 전환 (에러 아님)
- API 키 없음/만료: HTTP 500 + 명확한 에러 메시지
