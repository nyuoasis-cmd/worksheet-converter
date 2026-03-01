#!/usr/bin/env python3
"""raw 추출 데이터를 Agent B 포맷의 knowledge DB로 변환.

입력: data/knowledge/raw_{book}.json (Gemini Vision 추출 결과)
출력: data/knowledge/{subject}_{grade}.json (Agent B 포맷)

Agent B 포맷:
{
  "subject": "과학",
  "grade": "3-4",
  "unit": "1. 물질의 성질",
  "concepts": [{
    "concept": "물체",
    "easy_explanation": "모양이 있고 공간을 차지하는 것",
    "related_terms": ["물질", "재료"]
  }]
}
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
VOCAB_DIR = Path(__file__).resolve().parent.parent / "data" / "vocab"

# 책 이름 → (subject, grade) 매핑
BOOK_MAP = {
    "초등_3-4학년_과학": ("과학", "3-4"),
    "초등_3-4학년_사회": ("사회", "3-4"),
    "초등_3-4학년_수학": ("수학", "3-4"),
    "초등_5-6학년_과학": ("과학", "5-6"),
    "초등_5-6학년_사회": ("사회", "5-6"),
    "초등_5-6학년_수학": ("수학", "5-6"),
    "초등_1-2학년_국어": ("국어", "1-2"),
    "초등_1-2학년_수학": ("수학", "1-2"),
    "초등_1-2학년_통합": ("통합", "1-2"),
    "초등_3-4학년_국어": ("국어", "3-4"),
    "초등_5-6학년_국어": ("국어", "5-6"),
    "중등_1-3학년_과학": ("과학", "중1-3"),
    "중등_1-3학년_사회": ("사회", "중1-3"),
    "중등_1-3학년_수학": ("수학", "중1-3"),
    "중등_1학년_국어": ("국어", "중1"),
    "중등_2학년_국어": ("국어", "중2"),
    "중등_3학년_국어": ("국어", "중3"),
}


def load_toc(book_name: str) -> list[dict]:
    """meta.json에서 TOC 로드."""
    ebooks_dir = Path(__file__).resolve().parent.parent / "data" / "ebooks"
    meta_path = ebooks_dir / book_name / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        return meta.get("toc", [])
    return []


def infer_unit(toc: list[dict], page: str) -> str:
    """페이지 번호로 소속 단원 추론."""
    page_num = int(page) if page.isdigit() else 0
    current_unit = ""
    for entry in toc:
        raw_page = entry.get("page_idx", "0")
        # '047.html' 형태 처리
        raw_page = raw_page.split(".")[0] if isinstance(raw_page, str) else str(raw_page)
        entry_page = int(raw_page) if raw_page.isdigit() else 0
        if entry_page <= page_num:
            depth = entry.get("depth", "1")
            title = entry.get("title", "")
            if depth == "1" and not title.startswith("어휘") and title not in ("일러두기", "차례", "정답", "색인", "실험 기구"):
                current_unit = title
            elif depth == "2" and not title.startswith("어휘"):
                current_unit = title
    return current_unit


def build_knowledge(book_name: str) -> dict:
    """raw 데이터를 knowledge DB 포맷으로 변환."""
    raw_path = KNOWLEDGE_DIR / f"raw_{book_name}.json"
    if not raw_path.exists():
        print(f"  No raw data for {book_name}")
        return None

    subject, grade = BOOK_MAP.get(book_name, ("?", "?"))
    raw = json.loads(raw_path.read_text())
    toc = load_toc(book_name)

    # 단원별 개념 그룹화
    unit_concepts = defaultdict(list)
    seen_terms = set()

    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("section") != "이해":
            continue

        term = (item.get("term") or "").strip()
        definition = (item.get("definition") or "").strip()
        text = (item.get("text") or "").strip()
        page = (item.get("_page") or "")

        if not term or not (definition or text):
            continue

        # 중복 제거
        if term in seen_terms:
            continue
        seen_terms.add(term)

        # 단원 추론
        unit = infer_unit(toc, page)
        if not unit:
            unit = f"lesson_{item.get('lesson_num', '?')}"

        # easy_explanation: definition 우선, 없으면 text 첫 문장
        easy = definition
        if not easy and text:
            # 첫 문장 추출
            sentences = re.split(r'[.。]', text)
            easy = sentences[0].strip() + "." if sentences else text[:50]

        # related_terms: text에서 다른 알려진 용어 찾기
        related = []

        unit_concepts[unit].append({
            "concept": term,
            "easy_explanation": easy,
            "related_terms": related,
        })

    # 최종 구조화
    result = []
    for unit, concepts in unit_concepts.items():
        result.append({
            "subject": subject,
            "grade": grade,
            "unit": unit,
            "concepts": concepts,
        })

    return result


def cross_link_terms(knowledge_list: list[dict]):
    """교차 참조: related_terms 채우기."""
    all_terms = set()
    for entry in knowledge_list:
        for concept in entry.get("concepts", []):
            all_terms.add(concept["concept"])

    for entry in knowledge_list:
        for concept in entry.get("concepts", []):
            text = concept.get("easy_explanation", "")
            related = []
            for term in all_terms:
                if term != concept["concept"] and term in text:
                    related.append(term)
            concept["related_terms"] = related[:5]


def main():
    books = sys.argv[1:] if len(sys.argv) > 1 else list(BOOK_MAP.keys())

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    all_stats = []

    for book_name in books:
        if book_name not in BOOK_MAP:
            continue

        raw_path = KNOWLEDGE_DIR / f"raw_{book_name}.json"
        if not raw_path.exists():
            continue

        subject, grade = BOOK_MAP[book_name]
        print(f"\n{'='*50}")
        print(f"Processing: {book_name} → {subject} {grade}")
        print(f"{'='*50}")

        knowledge = build_knowledge(book_name)
        if not knowledge:
            continue

        cross_link_terms(knowledge)

        # Save
        output_path = KNOWLEDGE_DIR / f"knowledge_{subject}_{grade}.json"
        output_path.write_text(
            json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Stats
        total_concepts = sum(len(e["concepts"]) for e in knowledge)
        total_units = len(knowledge)
        print(f"  Units: {total_units}")
        print(f"  Concepts: {total_concepts}")
        print(f"  Output: {output_path}")

        all_stats.append({
            "book": book_name,
            "subject": subject,
            "grade": grade,
            "units": total_units,
            "concepts": total_concepts,
        })

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for s in all_stats:
        print(f"  {s['subject']} {s['grade']}: {s['concepts']} concepts in {s['units']} units")

    total = sum(s["concepts"] for s in all_stats)
    print(f"\n  TOTAL: {total} concepts")


if __name__ == "__main__":
    main()
