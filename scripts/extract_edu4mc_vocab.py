#!/usr/bin/env python3
"""
edu4mc 이북 raw 데이터에서 어휘 정리 섹션 추출 → vocab_edu4mc.json
"""

import json
import re
from collections import Counter
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
VOCAB_DIR = Path(__file__).resolve().parent.parent / "data" / "vocab"

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

VOCAB_SECTIONS = {"어휘 정리", "어휘 정리 (1학년)", "어휘 정리 (2학년)"}
PUZZLE_PATTERN = re.compile(r"^(가로|세로)\s*\d")


def extract():
    seen_terms: dict[str, dict] = {}

    for f in sorted(KNOWLEDGE_DIR.glob("raw_*.json")):
        book_name = f.stem.replace("raw_", "")
        subject, grade = BOOK_MAP.get(book_name, ("?", "?"))
        data = json.loads(f.read_text(encoding="utf-8"))

        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get("section") not in VOCAB_SECTIONS:
                continue

            raw_term = (item.get("term") or "").strip()
            if not raw_term:
                continue

            # 낱말퍼즐 항목 제외
            if PUZZLE_PATTERN.match(raw_term):
                continue

            defn = (item.get("definition") or "").strip()
            text = (item.get("text") or "").strip()
            easy = defn if defn else (text[:100] if text else "")
            if not easy:
                continue

            # 쉼표로 분리된 복수 term 처리
            terms = [t.strip() for t in raw_term.split(",") if t.strip()]

            for term in terms:
                if term not in seen_terms:
                    seen_terms[term] = {
                        "term_ko": term,
                        "definition_ko": defn,
                        "easy_ko": easy,
                        "en": "",
                        "ja": "",
                        "zh": "",
                        "vi": "",
                        "tl": "",
                        "subject": subject,
                        "grade": grade,
                        "source": "edu4mc",
                        "krdict_target_code": "",
                    }

    result = list(seen_terms.values())
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    out = VOCAB_DIR / "vocab_edu4mc.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"vocab_edu4mc.json: {len(result)}개 저장")
    dist = Counter(v["subject"] + " " + v["grade"] for v in result)
    for k, cnt in sorted(dist.items()):
        print(f"  {k}: {cnt}개")


if __name__ == "__main__":
    extract()
