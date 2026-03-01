#!/usr/bin/env python3
"""edu4mc 전자책 이미지에서 Gemini Vision으로 어휘/개념 추출.

사용법:
  python3 extract_ebook_text.py [book_folder] [--pages START-END]

예시:
  python3 extract_ebook_text.py 초등_3-4학년_과학
  python3 extract_ebook_text.py 초등_3-4학년_과학 --pages 5-22
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import urllib.request

API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")
if not API_KEY:
    # Try loading from .env files
    for env_path in [
        Path(__file__).resolve().parent.parent / ".env",
        Path("/home/claude/youthschool/.env"),
    ]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GOOGLE_AI_API_KEY="):
                    API_KEY = line.split("=", 1)[1].strip()
                    break
        if API_KEY:
            break

EBOOKS_DIR = Path(__file__).resolve().parent.parent / "data" / "ebooks"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

EXTRACT_PROMPT = """이 이미지는 다문화 학생용 교과 어휘 교재 페이지입니다.
이 페이지에서 다음 정보를 JSON 배열로 추출해주세요:

1. 어휘 번호와 용어 (bold 텍스트)
2. 이해 섹션의 설명문 (어휘 정의/설명)
3. 연습 문제 내용

출력 형식 (JSON 배열, 마크다운 코드블록 없이):
[
  {
    "lesson_num": "01",
    "term": "물체",
    "section": "이해",
    "text": "야구방망이, 글러브, 모자, 야구공처럼 모양이 있고 공간을 차지하고 있는 것을 물체라고 합니다.",
    "definition": "모양이 있고 공간을 차지하는 것"
  },
  {
    "lesson_num": "01",
    "term": "물체",
    "section": "연습",
    "text": "1. 빈칸에 알맞은 말을 쓰세요. 1) 모양이 있고 공간을 차지하고 있는 것을 [물체]라고 합니다."
  }
]

규칙:
- 단원 표지 페이지(목차만 있는 페이지)는 빈 배열 [] 반환
- 어휘 정리 페이지(십자말 퍼즐)도 내용 추출 (가로/세로 힌트가 곧 어휘 정의)
- 이미지 설명은 [그림: 야구하는 장면] 형태로 간략히
- 모든 텍스트는 원문 그대로 추출 (빈칸은 [___]로 표시)
- JSON만 출력, 설명 텍스트 없이"""

BATCH_SIZE = 4  # 한 번에 처리할 페이지 수


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def call_gemini(images: list[tuple[str, str]], prompt: str) -> str:
    """Gemini Vision API 호출. images = [(filename, base64_data), ...]"""
    parts = []

    # Add images
    for filename, b64 in images:
        parts.append({"text": f"--- 페이지: {filename} ---"})
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64,
            }
        })

    # Add prompt
    parts.append({"text": prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 16384,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return text
    except Exception as e:
        print(f"  API Error: {e}")
        return "[]"


def parse_response(text: str) -> list[dict]:
    """Gemini 응답에서 JSON 배열 추출."""
    text = text.strip()
    # Remove markdown code block if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in text
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        print(f"  Parse error, raw: {text[:200]}")
        return []


def get_content_pages(book_dir: Path, page_range: tuple | None = None) -> list[Path]:
    """TOC를 기반으로 내용 페이지 목록 반환."""
    meta_path = book_dir / "meta.json"
    if not meta_path.exists():
        # Fallback: all jpg files
        pages = sorted(book_dir.glob("*.jpg"))
        if page_range:
            pages = [
                p for p in pages
                if page_range[0] <= int(p.stem) <= page_range[1]
            ]
        return pages

    meta = json.loads(meta_path.read_text())
    toc = meta.get("toc", [])

    # 스킵할 섹션의 시작 페이지
    skip_sections = {"정답", "색인", "실험 기구"}
    skip_start_pages = set()
    for entry in toc:
        if entry["title"] in skip_sections:
            skip_start_pages.add(int(entry["page_idx"]))

    # Get all pages
    all_pages = sorted(book_dir.glob("*.jpg"), key=lambda p: int(p.stem))

    # Filter
    pages = []
    total = int(meta.get("total_pages", len(all_pages)))
    skip_from = min(skip_start_pages) if skip_start_pages else total + 1

    for p in all_pages:
        num = int(p.stem)
        if num < 2:  # Skip page 1 (cover)
            continue
        if num >= skip_from:
            continue
        if page_range and not (page_range[0] <= num <= page_range[1]):
            continue
        pages.append(p)

    return pages


def process_book(book_folder: str, page_range: tuple | None = None):
    book_dir = EBOOKS_DIR / book_folder

    if not book_dir.exists():
        print(f"Error: {book_dir} does not exist")
        sys.exit(1)

    pages = get_content_pages(book_dir, page_range)
    print(f"Book: {book_folder}")
    print(f"Content pages: {len(pages)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"raw_{book_folder}.json"

    # Load existing results
    all_results = []
    if output_file.exists():
        try:
            all_results = json.loads(output_file.read_text())
            if not isinstance(all_results, list):
                all_results = []
        except json.JSONDecodeError:
            all_results = []

    processed_pages = {
        r["_page"] for r in all_results
        if isinstance(r, dict) and "_page" in r
    }

    # Filter out already processed
    todo = [p for p in pages if p.stem not in processed_pages]
    print(f"Already processed: {len(processed_pages)}")
    print(f"To process: {len(todo)}")

    if not todo:
        print("Nothing to do!")
        return

    # Process in batches
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i : i + BATCH_SIZE]
        batch_names = [p.stem for p in batch]
        print(f"\nBatch {i // BATCH_SIZE + 1}: pages {', '.join(batch_names)}")

        images = [(p.name, encode_image(p)) for p in batch]
        response = call_gemini(images, EXTRACT_PROMPT)
        items = parse_response(response)

        print(f"  Extracted {len(items)} items")

        # Flatten nested arrays
        flat_items = []
        for item in items:
            if isinstance(item, list):
                flat_items.extend(item)
            elif isinstance(item, dict):
                flat_items.append(item)
        items = flat_items

        # Tag with page number
        for item in items:
            if isinstance(item, dict):
                if "_page" not in item:
                    item["_page"] = batch_names[0]
                item["_book"] = book_folder

        all_results.extend(items)

        # Save after each batch
        output_file.write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Rate limiting
        if i + BATCH_SIZE < len(todo):
            time.sleep(2)

    print(f"\nDone! Total items: {len(all_results)}")
    print(f"Output: {output_file}")


def main():
    if not API_KEY:
        print("Error: GOOGLE_AI_API_KEY not found in .env")
        sys.exit(1)

    book_folder = sys.argv[1] if len(sys.argv) > 1 else "초등_3-4학년_과학"
    page_range = None

    if "--pages" in sys.argv:
        idx = sys.argv.index("--pages")
        if idx + 1 < len(sys.argv):
            start, end = sys.argv[idx + 1].split("-")
            page_range = (int(start), int(end))

    process_book(book_folder, page_range)


if __name__ == "__main__":
    main()
