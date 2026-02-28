"""3장의 테스트 이미지를 /api/convert 엔드포인트로 변환 테스트한다.

테스트 시나리오:
  1. test1 — 모드1 (RAG 없음, 다국어 없음)
  2. test2 — 모드2 (RAG + 베트남어/중국어)
  3. test3 — 모드1 (RAG 없음, 베트남어만)
"""

import json
import os
import sys
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.app import create_app

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_worksheets")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

app = create_app()

test_cases = [
    {
        "name": "test1_mode1_no_lang",
        "image": "test1_science_3_1_materials.png",
        "data": {
            "difficulty": "쉬움",
        },
        "description": "모드1: RAG 힌트 없음, 다국어 없음",
    },
    {
        "name": "test2_mode2_vi_zh",
        "image": "test2_science_4_1_plants.png",
        "data": {
            "languages": "vi,zh",
            "difficulty": "쉬움",
            "subject": "과학",
            "grade_group": "3-4",
        },
        "description": "모드2: RAG 힌트(과학 3-4학년), 베트남어+중국어",
    },
    {
        "name": "test3_mode1_vi_only",
        "image": "test3_science_3_1_magnets.png",
        "data": {
            "languages": "vi",
            "difficulty": "매우 쉬움",
        },
        "description": "모드1: RAG 힌트 없음, 베트남어만, 매우 쉬움",
    },
]

results = []

with app.test_client() as client:
    for i, tc in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/3] {tc['name']}: {tc['description']}")
        print(f"{'='*60}")

        image_path = os.path.join(SAMPLE_DIR, tc["image"])
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        data = dict(tc["data"])
        data["image"] = (io.BytesIO(image_bytes), tc["image"])

        try:
            response = client.post(
                "/api/convert",
                data=data,
                content_type="multipart/form-data",
            )

            status = response.status_code
            body = response.get_json()

            print(f"Status: {status}")
            print(f"Mode: {body.get('mode', 'N/A')}")

            if status == 200:
                html = body.get("html", "")
                print(f"HTML length: {len(html)} chars")
                print(f"First 500 chars:\n{html[:500]}")

                # 결과 저장
                result_path = os.path.join(RESULTS_DIR, f"{tc['name']}.html")
                with open(result_path, "w", encoding="utf-8") as out:
                    out.write(html)
                print(f"Saved: {result_path}")

                results.append({
                    "name": tc["name"],
                    "description": tc["description"],
                    "status": status,
                    "mode": body.get("mode"),
                    "html_length": len(html),
                    "success": True,
                })
            else:
                error = body.get("error", "Unknown error")
                print(f"Error: {error}")
                results.append({
                    "name": tc["name"],
                    "description": tc["description"],
                    "status": status,
                    "error": error,
                    "success": False,
                })

        except Exception as e:
            print(f"Exception: {e}")
            results.append({
                "name": tc["name"],
                "description": tc["description"],
                "status": -1,
                "error": str(e),
                "success": False,
            })

# 요약
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for r in results:
    status_str = "OK" if r["success"] else "FAIL"
    print(f"  [{status_str}] {r['name']}: {r['description']}")

# JSON 결과 저장
summary_path = os.path.join(RESULTS_DIR, "summary.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSummary saved: {summary_path}")
