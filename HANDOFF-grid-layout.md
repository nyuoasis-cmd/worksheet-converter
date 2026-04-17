# 이미지 그리드 레이아웃 보존 — 핸드오프

## 상태: 코드 수정 완료, E2E 테스트 필요

## 문제
`중등 국어.png`에서 교과서 표지 6개가 2×3 그리드인데, 변환 결과 세로 1열로 나열됨.
원인: Gemini 프롬프트에 이미지 격자 배치 규칙이 없었음.

## 완료된 수정 (3개 파일, 미커밋)

### 1. `backend/prompts/convert_prompt.py`
- 라인 40: 격자 배치 안내 추가 ("원본에서 이미지들이 격자 형태로 배치되어 있으면...")
- 라인 110~123: 패턴 3 신규 — `ws-grid-img-item` + `image-hint` 조합 HTML 예시
- 기존 빈칸 패턴 번호 3→4로 변경

### 2. `backend/routes/convert.py` (PDF CSS, 라인 270~272)
- `.ws-grid-img-item` CSS 3개 규칙 추가

### 3. `tests/render-html-to-png.mjs` (테스트 CSS, 라인 42~46)
- `.ws-grid-3` 누락 버그 수정 (기존에 없었음)
- `.ws-grid-img-item` CSS 동일 추가

## 통과한 검증
- `build_prompt()` 정상 빌드
- `run_convert_test.py`: test1, test2 OK (test3은 기존 의도적 400)
- `verify_output.py`: 4/4 PASS

## 남은 작업: E2E 테스트

```bash
cd /home/claude/worksheet-converter

# 1. Flask 서버 시작
python3 -m flask --app backend.app run --port 5001

# 2. 테스트 이미지로 변환
curl -X POST http://localhost:5001/api/convert \
  -F "image=@verify/중등 국어.png" \
  -F "difficulty=쉬움" \
  -o /tmp/grid-test.html

# 3. 결과 HTML에서 ws-grid-img-item 존재 확인
grep -c "ws-grid-img-item" /tmp/grid-test.html

# 4. PNG 렌더링으로 시각 확인
cp /tmp/grid-test.html tests/results/grid-test.html
node tests/render-html-to-png.mjs tests/results/grid-test.html
# → tests/results/grid-test.png 을 Read 도구로 열어 6개 이미지가 2×3 배치인지 확인
```

## 확인 포인트
- **`중등 국어.png`**: 교과서 표지 6개 → **2×3 그리드** (ws-grid-3 × 2행)
- **기존 이미지 케이스**: `중학교 과학.png` 등은 격자로 바뀌면 안 됨 (세로 유지)

## 성공 시 커밋
```bash
cd /home/claude/worksheet-converter
git add backend/prompts/convert_prompt.py backend/routes/convert.py tests/render-html-to-png.mjs
git commit -m "feat: 이미지 격자(grid) 레이아웃 보존 — ws-grid-img-item 패턴 추가"
```

## 실패 시 디버그
- Gemini가 `ws-grid-img-item`을 안 쓰면 → 프롬프트 강화 (예시 더 구체적으로)
- 이미지 크롭이 안 되면 → `image_service.py`의 bbox regex 확인 (중첩 div 처리 가능한지)
- CSS 깨지면 → convert.py와 render-html-to-png.mjs의 CSS 동기화 확인
