"""Gemini Vision 시각 검증 — 변환 결과 PNG를 Gemini에 보내 품질 판단.

검증 항목 5가지 (PRD 기반):
  1. text_overflow — 텍스트가 영역 밖으로 넘침
  2. diagram_covered — 다이어그램/삽화가 텍스트에 가려짐
  3. blank_preserved — 빈칸(□, ___, ( )) 보존 여부
  4. font_readability — 텍스트 가독성 (폰트 크기, 대비)
  5. layout_integrity — 전체 레이아웃 보존 (원본 대비)

사용법:
  # 원본 이미지와 변환 결과 PNG 비교 검증
  python3 tests/verify_visual.py original.png output.png

  # auto_pipeline.py에서 함수로 직접 호출
  from tests.verify_visual import verify_visual
  result = verify_visual(original_path, output_path)
"""

import base64
import json
import os
import sys

from google import genai
from google.genai import types

# 프로젝트 루트를 sys.path에 추가 (직접 실행 시)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.config import GEMINI_API_KEY

VERIFY_MODEL = "gemini-2.5-flash"

VERIFY_PROMPT = """당신은 학습지 변환 품질 검증 전문가입니다.

아래 두 이미지를 비교 분석하세요:
- 첫 번째 이미지: 원본 학습지 (교사가 업로드한 원본)
- 두 번째 이미지: 변환 결과물 (HTML→PNG 렌더링)

다음 5가지 품질 기준으로 검증하세요. 각 항목에 "pass" 또는 "fail" 판정과 상세 설명을 제공하세요.

## 검증 항목

1. **text_overflow**: 텍스트가 레이아웃 영역 밖으로 넘치거나 잘렸는가?
   - pass: 모든 텍스트가 영역 내에 정상 표시
   - fail: 텍스트가 잘리거나 영역을 벗어남

2. **diagram_covered**: 다이어그램/삽화/그림 영역이 텍스트에 가려졌는가?
   - pass: 이미지 힌트 영역이 명확히 구분됨 (원본에 그림이 없으면 자동 pass)
   - fail: 그림 영역이 텍스트로 가려지거나 표시 누락

3. **blank_preserved**: 원본의 빈칸(□, ___, ( ), ㅁ)이 변환 결과에 보존되었는가?
   - pass: 빈칸이 적절히 보존됨 (원본에 빈칸이 없으면 자동 pass)
   - fail: 빈칸이 사라지거나 채워짐

4. **font_readability**: 텍스트가 읽기 쉬운가? (폰트 크기, 색상 대비, 줄간격)
   - pass: 텍스트가 선명하고 읽기 쉬움
   - fail: 텍스트가 너무 작거나 흐리거나 읽기 어려움

5. **layout_integrity**: 전체 레이아웃이 원본과 유사하게 보존되었는가?
   - pass: 문제 순서, 선택지 배치, 전체 구조가 원본과 유사
   - fail: 레이아웃이 크게 변형되었거나 문제 순서가 뒤바뀜

## 출력 형식

반드시 아래 JSON 형식으로만 출력하세요. 다른 텍스트는 포함하지 마세요.

```json
{
  "checks": [
    {"name": "text_overflow", "pass": true, "detail": "설명"},
    {"name": "diagram_covered", "pass": true, "detail": "설명"},
    {"name": "blank_preserved", "pass": true, "detail": "설명"},
    {"name": "font_readability", "pass": true, "detail": "설명"},
    {"name": "layout_integrity", "pass": true, "detail": "설명"}
  ],
  "overall": "pass",
  "summary": "전체 요약 (1-2문장)"
}
```

overall은 모든 checks가 pass면 "pass", 하나라도 fail이면 "fail".
"""


def _load_image(path: str) -> tuple[bytes, str]:
    """이미지 파일을 바이트로 로드하고 MIME 타입을 반환."""
    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(ext, "image/png")
    with open(path, "rb") as f:
        return f.read(), mime_type


def verify_visual(original_path: str, output_path: str) -> dict:
    """원본 이미지와 변환 결과 PNG를 Gemini Vision으로 비교 검증.

    Args:
        original_path: 원본 학습지 이미지 경로
        output_path: 변환 결과 PNG 경로

    Returns:
        검증 결과 dict: {checks: [...], overall: "pass"|"fail", summary: "..."}
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    orig_bytes, orig_mime = _load_image(original_path)
    out_bytes, out_mime = _load_image(output_path)

    orig_part = types.Part.from_bytes(data=orig_bytes, mime_type=orig_mime)
    out_part = types.Part.from_bytes(data=out_bytes, mime_type=out_mime)

    response = client.models.generate_content(
        model=VERIFY_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    orig_part,
                    out_part,
                    types.Part.from_text(text="위 두 이미지를 비교 검증하세요. 첫 번째가 원본, 두 번째가 변환 결과입니다."),
                ],
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=VERIFY_PROMPT,
            temperature=0.1,
        ),
    )

    raw = response.text.strip()

    # JSON 블록 추출 (```json...``` 감싸기 제거)
    import re
    json_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "checks": [],
            "overall": "error",
            "summary": f"Gemini 응답 파싱 실패: {raw[:200]}",
        }

    return result


def print_result(result: dict) -> bool:
    """검증 결과를 테이블로 출력. overall pass 여부 반환."""
    overall = result.get("overall", "error")
    checks = result.get("checks", [])
    summary = result.get("summary", "")

    print(f"\n{'─' * 70}")
    print(f"  시각 검증 결과  [{overall.upper()}]")
    print(f"{'─' * 70}")
    print(f"  {'검증 항목':<20} {'결과':<6} {'상세'}")
    print(f"  {'─' * 64}")

    for check in checks:
        name = check.get("name", "?")
        passed = check.get("pass", False)
        detail = check.get("detail", "")
        mark = "PASS" if passed else "FAIL"
        print(f"  {name:<20} {mark:<6} {detail}")

    if summary:
        print(f"\n  요약: {summary}")

    return overall == "pass"


def main():
    if len(sys.argv) < 3:
        print("사용법: python3 tests/verify_visual.py <원본이미지> <변환PNG>")
        print("예: python3 tests/verify_visual.py verify/중학교\\ 과학.png verify/output/중학교\\ 과학.png")
        sys.exit(1)

    original_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(original_path):
        print(f"원본 파일 없음: {original_path}")
        sys.exit(1)
    if not os.path.exists(output_path):
        print(f"변환 결과 파일 없음: {output_path}")
        sys.exit(1)

    result = verify_visual(original_path, output_path)
    passed = print_result(result)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
