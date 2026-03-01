#!/usr/bin/env python3
"""edu4mc.or.kr 전자책 페이지 이미지 다운로드 스크립트.

API 구조:
- 전체 목록: /restapi/booklistOrderByTitle
- 책 정보: /index.php/epub/info/{seq}/pd/
- 페이지 이미지: /files/contents/{base_url}/ebook/OEBPS/pp_print/{NNN}.jpg
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://ebook.edu4mc.or.kr"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "ebooks"

# 우선순위 순서 (과학 > 사회 > 수학, 3-4 > 5-6 > 중등)
PRIORITY_BOOKS = [
    # 초등
    {"seq": "67", "title": "3~4학년 과학", "category": "초등"},
    {"seq": "72", "title": "3~4학년 사회", "category": "초등"},
    {"seq": "75", "title": "3~4학년 수학", "category": "초등"},
    {"seq": "68", "title": "5~6학년 과학", "category": "초등"},
    {"seq": "73", "title": "5~6학년 사회", "category": "초등"},
    {"seq": "76", "title": "5~6학년 수학", "category": "초등"},
    {"seq": "69", "title": "1~2학년 국어", "category": "초등"},
    {"seq": "70", "title": "3~4학년 국어", "category": "초등"},
    {"seq": "71", "title": "5~6학년 국어", "category": "초등"},
    {"seq": "74", "title": "1~2학년 수학", "category": "초등"},
    {"seq": "77", "title": "1~2학년 통합", "category": "초등"},
    # 중등
    {"seq": "56", "title": "1~3학년 과학", "category": "중등"},
    {"seq": "62", "title": "1~3학년 사회", "category": "중등"},
    {"seq": "54", "title": "1~3학년 수학", "category": "중등"},
    {"seq": "59", "title": "1학년 국어", "category": "중등"},
    {"seq": "60", "title": "2학년 국어", "category": "중등"},
    {"seq": "61", "title": "3학년 국어", "category": "중등"},
]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True  # 이미 다운로드됨
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as e:
        print(f"  FAIL: {dest.name} — {e}")
        return False


def download_book(book: dict) -> dict:
    seq = book["seq"]
    title = book["title"]
    category = book["category"]
    folder_name = f"{category}_{title}".replace(" ", "_").replace("~", "-")
    book_dir = OUT_DIR / folder_name

    print(f"\n{'='*60}")
    print(f"[{category}] {title} (seq={seq})")
    print(f"{'='*60}")

    # 1. Get epub info
    info_url = f"{BASE}/index.php/epub/info/{seq}/pd/"
    try:
        data = fetch_json(info_url)
    except Exception as e:
        print(f"  ERROR fetching info: {e}")
        return {"title": title, "status": "error", "error": str(e)}

    epub_info = data.get("info", {})
    pages = data.get("pages", [])
    toc = data.get("toc", [])
    base_url = epub_info.get("base_url", "")
    total = epub_info.get("totalpage", len(pages))

    print(f"  base_url: {base_url}")
    print(f"  pages: {total}")
    print(f"  toc entries: {len(toc)}")

    # 2. Create directory
    book_dir.mkdir(parents=True, exist_ok=True)

    # Save metadata
    meta = {
        "seq": seq,
        "title": f"{category} {title}",
        "category": category,
        "base_url": base_url,
        "total_pages": total,
        "toc": toc,
    }
    (book_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3. Download page images
    downloaded = 0
    skipped = 0
    failed = 0

    for page in pages:
        url_path = page.get("url", "")
        idx = page.get("idx", 0)

        # Skip blank pages
        if "blank" in str(url_path) or idx == 0:
            continue

        # Image URL: pp_print/{NNN}.jpg
        page_num = str(idx).zfill(3)
        img_url = f"{BASE}/files/contents/{base_url}/ebook/OEBPS/pp_print/{page_num}.jpg"
        dest = book_dir / f"{page_num}.jpg"

        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            continue

        ok = download_file(img_url, dest)
        if ok:
            downloaded += 1
        else:
            failed += 1

        # Rate limiting
        if downloaded % 10 == 0 and downloaded > 0:
            time.sleep(0.5)

    print(f"  Done: {downloaded} downloaded, {skipped} skipped, {failed} failed")

    return {
        "title": f"{category} {title}",
        "folder": folder_name,
        "total_pages": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "toc_count": len(toc),
    }


def main():
    # Parse args
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass

    books_to_process = PRIORITY_BOOKS[:limit] if limit else PRIORITY_BOOKS

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output: {OUT_DIR}")
    print(f"Books to download: {len(books_to_process)}")

    results = []
    for book in books_to_process:
        result = download_book(book)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "OK" if r.get("failed", 0) == 0 else "PARTIAL"
        print(f"  [{status}] {r['title']}: {r.get('downloaded',0)}+{r.get('skipped',0)} pages")

    # Save summary
    (OUT_DIR / "download_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
