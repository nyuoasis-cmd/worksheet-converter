# 다문화 학습지 변환기 — 프로젝트 메모

## 프로젝트 개요
교사가 문제지 사진을 업로드하면, 쉬운 한국어 + 다국어 핵심 용어 병기된 변환본을 자동 생성하는 도구.
TeacherMate(teachermate.co.kr) 플랫폼의 새 모듈.

## 기술 스택
- 프론트엔드: React / TypeScript (기존 TeacherMate와 동일)
- 백엔드: Flask (Python)
- AI: Gemini Vision API (이미지 OCR + 텍스트 변환)
- 출력: PDF (weasyprint), HWPX (기존 모듈 재사용)

## 핵심 설계 원칙 (절대 위반 금지)

### 1. 파이프라인 1개, 분기 없음
- /api/convert 엔드포인트 1개로 모든 학년/과목/언어 처리
- 학년/과목별 엔드포인트 만들지 마라
- Gemini가 이미지에서 과목/학년을 자동 감지

### 2. 확장 = 데이터 추가 (코드 변경 제로)
- 언어 추가: config/languages.ts에 한 줄 + translations 객체에 키 추가
- 과목 추가: data/terms/에 JSON 파일 추가
- 학년 추가: data/terms/에 JSON 파일 추가
- 위 작업에 코드 변경이 필요하면 설계가 잘못된 것

### 3. 모드1/모드2는 분기가 아니라 데이터 유무
- 모드1(프롬프트 only): rag_context = "" (빈값)
- 모드2(프롬프트+RAG): rag_context = 매칭된 어휘/지식
- 동일한 프롬프트 템플릿, 동일한 코드. if/else 없음

## 변환 규칙 (프롬프트에 하드코딩)
1. 문제 번호, 문제 구조, 보기 순서 절대 변경 금지
2. 정답이 바뀌는 변환 절대 금지
3. 어려운 단어 뒤에 괄호로 쉬운 설명 삽입 — 예: 이산화탄소(= 우리가 내쉬는 공기)
4. 외국어 모드 시 핵심 용어에만 다국어 병기 — 예: 광합성(quang hợp / 光合作用)
5. 문장은 짧게. 한 문장 15자 이내 권장
6. 존댓말 사용 (~해요 체)

## 데이터 스키마 (모든 에이전트 공통)

### 어휘 DB (terms)
```json
{
  "term_ko": "광합성",
  "easy_ko": "식물이 빛으로 음식을 만드는 것",
  "translations": {
    "vi": "quang hợp",
    "zh": "光合作用",
    "en": "photosynthesis"
  },
  "subject": "과학",
  "grade_group": "3-4",
  "source": "krdict"
}
```

### 교과 지식 DB (concepts)
```json
{
  "subject": "과학",
  "grade_group": "3-4",
  "unit": "2단원. 식물의 생활",
  "concepts": [{
    "concept": "광합성",
    "easy_explanation": "식물은 잎에서 빛을 받아요. 빛과 물로 양분을 만들어요.",
    "related_terms": ["잎", "빛", "물", "양분"]
  }]
}
```

### 언어 설정 (데이터 드리븐)
```typescript
const SUPPORTED_LANGUAGES = [
  { code: "vi", label: "베트남어", flag: "🇻🇳", default: false },
  { code: "zh", label: "중국어", flag: "🇨🇳", default: false },
  { code: "en", label: "영어", flag: "🇺🇸", default: false },
  // 한 줄 추가 = UI + 프롬프트 + 출력에 자동 반영
] as const;
```

## 폴더 구조 & 담당 영역



⚠️ 자기 영역 외 폴더는 절대 건드리지 마라.

## 자동 검증 파이프라인

코드 수정 후 반드시 3단계를 순서대로 실행한다.

### Step 1: 테스트 실행
```bash
python3 tests/run_convert_test.py
```
3개 테스트 케이스 전부 OK 필수. FAIL 시 즉시 수정.

### Step 2: HTML 구조 검증
```bash
python3 tests/verify_output.py
```
검증 항목 5가지:
1. 필수 클래스 존재 (.worksheet, .worksheet-header, .question, .question-text)
2. 문제 번호 연속성 (data-number="1", "2", ... 빠짐 없이)
3. 다국어 모드: languages 있으면 term-multilingual 존재 필수
4. 이미지 레이블 언어 매칭 (zh→图, ja→図, vi→Hình, en→Picture, fil→Larawan)
5. 마크다운 잔재(**bold**) 미검출

### Step 3: 시각 검증
```bash
node tests/render-html-to-png.mjs
```
PNG를 Read 도구로 열어 직접 확인: 레이아웃, 폰트, ko-ref 스타일, 이미지 힌트 박스.

## 자동화 파이프라인 (생성 ↔ 검증 루프)

verify/ 폴더에 이미지를 넣으면 자동으로 변환 → 검증 → 재시도 루프를 실행한다.

### 사용법

```bash
# 1. 이미지를 verify/ 폴더에 넣기
cp "학습지.png" /home/claude/worksheet-converter/verify/

# 2. (선택) 메타데이터 지정 — 사이드카 JSON
# 없으면 기본값: languages="zh", difficulty="쉬움"
echo '{"languages": "ja", "subject": "과학", "grade_group": "중1"}' > verify/학습지.json

# 3. 파이프라인 실행
python3 scripts/auto_pipeline.py            # 전체 이미지
python3 scripts/auto_pipeline.py "학습지.png"  # 특정 파일

# 4. 결과 확인
ls verify/output/
# → 학습지.html, 학습지.png, 학습지_report.json
```

### 파이프라인 단계

```
이미지 → [Step 1] Gemini 변환 → HTML
       → [Step 2] 구조 검증 (5항목)
       → [Step 3] PNG 렌더링 (Puppeteer)
       → [Step 4] 시각 검증 (Gemini Vision, 5항목)
       → FAIL 시 에러 피드백 포함하여 Step 1로 (최대 3회)
```

### 시각 검증 항목 (verify_visual.py)
1. text_overflow — 텍스트 영역 밖 넘침
2. diagram_covered — 다이어그램 가려짐
3. blank_preserved — 빈칸(□) 보존
4. font_readability — 텍스트 가독성
5. layout_integrity — 레이아웃 보존

### 파이프라인 핵심 파일
| 파일 | 역할 |
|------|------|
| scripts/auto_pipeline.py | 오케스트레이션 메인 |
| tests/verify_visual.py | Gemini Vision 시각 검증 |
| tests/verify_output.py | HTML 구조 검증 5단계 |
| tests/render-html-to-png.mjs | HTML→PNG 렌더링 |

## 실수 목록 (발견되면 여기에 추가)
- (아직 없음 — 작업 중 실수 발견 시 이 CLAUDE.md에 기록할 것)