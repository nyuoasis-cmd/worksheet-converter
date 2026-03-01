#!/usr/bin/env python3
"""
어휘 DB 병합 스크립트
data/vocab/vocab_*.json 파일을 전부 읽어 vocab_all.json으로 병합합니다.
같은 term_ko가 여러 교과에 있으면 subject를 배열로 합칩니다.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "vocab"


def merge_vocab():
    """모든 vocab_*.json을 병합한다."""
    vocab_files = sorted(DATA_DIR.glob("vocab_*.json"))
    vocab_files = [f for f in vocab_files if f.name != "vocab_all.json"]

    if not vocab_files:
        print("병합할 파일이 없습니다.")
        return

    print(f"병합 대상: {len(vocab_files)}개 파일")
    for f in vocab_files:
        print(f"  - {f.name}")

    # term_ko 기준 병합
    merged: dict[str, dict] = {}

    for vocab_file in vocab_files:
        with open(vocab_file, encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            term = entry["term_ko"]
            subject_info = f"{entry['subject']} {entry['grade']}"

            if term in merged:
                # 기존 항목에 subject 추가
                existing = merged[term]
                if subject_info not in existing["subjects"]:
                    existing["subjects"].append(subject_info)
                # 빈 필드가 있으면 채움
                for lang in ["en", "ja", "zh", "vi", "tl"]:
                    if not existing.get(lang) and entry.get(lang):
                        existing[lang] = entry[lang]
                if not existing.get("definition_ko") and entry.get("definition_ko"):
                    existing["definition_ko"] = entry["definition_ko"]
                if not existing.get("krdict_target_code") and entry.get("krdict_target_code"):
                    existing["krdict_target_code"] = entry["krdict_target_code"]
            else:
                merged[term] = {
                    "term_ko": term,
                    "definition_ko": entry.get("definition_ko", ""),
                    "easy_ko": entry.get("easy_ko", ""),
                    "en": entry.get("en", ""),
                    "ja": entry.get("ja", ""),
                    "zh": entry.get("zh", ""),
                    "vi": entry.get("vi", ""),
                    "tl": entry.get("tl", ""),
                    "subjects": [subject_info],
                    "source": entry.get("source", "krdict"),
                    "krdict_target_code": entry.get("krdict_target_code", ""),
                }

    # 리스트로 변환
    result = list(merged.values())

    # 저장
    output_file = DATA_DIR / "vocab_all.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"===== 어휘 DB 구축 완료 =====")
    print(f"{'='*50}")
    print(f"총 어휘 수: {len(result)}개")

    # 교과별 통계
    subject_counts: dict[str, int] = {}
    for vocab_file in vocab_files:
        with open(vocab_file, encoding="utf-8") as f:
            entries = json.load(f)
        # 파일명에서 교과 추출
        fname = vocab_file.stem  # e.g. vocab_science_e34
        subject_counts[fname] = len(entries)

    # 교과명 매핑
    name_map = {
        "vocab_science_e34": "과학3-4",
        "vocab_social_e34": "사회3-4",
        "vocab_math_e34": "수학3-4",
        "vocab_science_e56": "과학5-6",
        "vocab_social_e56": "사회5-6",
    }

    parts = []
    for key, count in subject_counts.items():
        label = name_map.get(key, key)
        parts.append(f"{label} ({count}개)")
    print(f"교과별: {', '.join(parts)}")

    # 번역 완료율
    langs = ["en", "ja", "zh", "vi", "tl"]
    total = len(result)
    print(f"번역 완료율:")
    missing_terms: dict[str, list[str]] = {}
    for lang in langs:
        filled = sum(1 for r in result if r.get(lang))
        pct = filled / total * 100 if total > 0 else 0
        print(f"  {lang}: {pct:.0f}% ({filled}/{total})")
        missing = [r["term_ko"] for r in result if not r.get(lang)]
        if missing:
            missing_terms[lang] = missing

    # 번역 누락 용어
    print(f"번역 누락 용어:")
    for lang in langs:
        terms = missing_terms.get(lang, [])
        if terms:
            preview = terms[:15]
            suffix = f" 외 {len(terms)-15}개" if len(terms) > 15 else ""
            print(f"  {lang} ({len(terms)}개): {', '.join(preview)}{suffix}")
        else:
            print(f"  {lang}: 없음 (100% 완료)")


if __name__ == "__main__":
    merge_vocab()
