#!/usr/bin/env python3
"""미추출 이북 전체를 순차 추출."""
import subprocess
import sys
from pathlib import Path

EBOOKS_DIR = Path(__file__).resolve().parent.parent / "data" / "ebooks"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
EXTRACT_SCRIPT = Path(__file__).resolve().parent / "extract_ebook_text.py"

# 이미 추출된 책 확인
extracted = set()
for f in KNOWLEDGE_DIR.glob("raw_*.json"):
    name = f.stem.replace("raw_", "")
    extracted.add(name)

# 미추출 책 목록
remaining = []
for d in sorted(EBOOKS_DIR.iterdir()):
    if d.is_dir() and d.name not in extracted and not d.name.startswith("."):
        page_count = len(list(d.glob("*.jpg")))
        remaining.append((d.name, page_count))

print(f"이미 추출: {len(extracted)}권")
print(f"미추출: {len(remaining)}권")
print(f"총 페이지: {sum(c for _, c in remaining)}장")
print("=" * 60)

for i, (book, pages) in enumerate(remaining, 1):
    print(f"\n[{i}/{len(remaining)}] {book} ({pages}장)")
    result = subprocess.run(
        [sys.executable, str(EXTRACT_SCRIPT), book],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  ERROR: exit code {result.returncode}")

print("\n" + "=" * 60)
print("전체 추출 완료!")

# 최종 결과 요약
for f in sorted(KNOWLEDGE_DIR.glob("raw_*.json")):
    import json
    data = json.loads(f.read_text())
    print(f"  {f.name}: {len(data)}개 항목")
