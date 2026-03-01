자동 검증 파이프라인을 실행합니다.

verify/ 폴더의 학습지 이미지를 스캔하여 변환 → 구조검증 → PNG렌더링 → 시각검증 루프를 자동 실행합니다.

## 실행

```bash
cd /home/claude/worksheet-converter && python3 scripts/auto_pipeline.py $ARGUMENTS
```

- 인자 없이: verify/ 내 모든 이미지 처리
- 파일명 지정: 해당 이미지만 처리 (예: `"중학교 과학.png"`)

## 실행 후

1. `verify/output/` 에 생성된 결과물 확인:
   - `{이미지명}.html` — 변환된 HTML
   - `{이미지명}.png` — 렌더링 PNG
   - `{이미지명}_report.json` — 검증 리포트

2. report.json의 `final_status` 확인:
   - `"pass"` → 모든 검증 통과
   - `"best_effort"` → 3회 시도 후 최선 결과 (문제점 리포트 참조)

3. PNG 파일을 Read 도구로 열어 시각적으로 최종 확인
