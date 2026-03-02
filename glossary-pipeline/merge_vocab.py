"""Phase 1-C: 3개 소스 통합 → vocab_final.json 확장.

소스 우선순위:
  1. existing (vocab_final.json) — 최우선 (수동 검수 완료)
  2. krdict — definition_ko, ja, vi 풍부
  3. pyeonsu — en 정확 (편수자료 공식)

Subjects 정규화:
  - "과학-물리" → "과학" (서브카테고리 제거)
  - "과학 3-4" → 그대로 유지 (학년 정보 보존)
  - "과학" → 그대로 유지 (전학년 매칭)
"""

import json
import os
import shutil
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXISTING_PATH = os.path.join(BASE, "data", "vocab", "vocab_final.json")
KRDICT_PATH = os.path.join(BASE, "glossary-pipeline", "krdict", "krdict_education_terms.json")
PYEONSU_PATH = os.path.join(BASE, "glossary-pipeline", "pyeonsu", "pyeonsu_terms.json")
OUTPUT_PATH = EXISTING_PATH  # overwrite
BACKUP_PATH = EXISTING_PATH + ".bak"


def normalize_subjects(subjects: list[str], source: str) -> list[str]:
    """subjects 정규화: 과학-물리 → 과학."""
    result = set()
    for s in subjects:
        if "-" in s and source == "pyeonsu":
            # "과학-물리" → "과학"
            parent = s.split("-", 1)[0]
            result.add(parent)
        else:
            result.add(s)
    return sorted(result)


def merge_field(existing_val, krdict_val, pyeonsu_val):
    """빈 문자열이 아닌 첫 번째 값 반환."""
    for v in [existing_val, krdict_val, pyeonsu_val]:
        if v:
            return v
    return ""


def merge_field_en(existing_val, pyeonsu_val, krdict_val):
    """en 필드: 편수자료 우선 (공식 영어 용어)."""
    for v in [existing_val, pyeonsu_val, krdict_val]:
        if v:
            return v
    return ""


def merge():
    # Load sources
    with open(EXISTING_PATH, encoding="utf-8") as f:
        existing = json.load(f)
    with open(KRDICT_PATH, encoding="utf-8") as f:
        krdict = json.load(f)
    with open(PYEONSU_PATH, encoding="utf-8") as f:
        pyeonsu = json.load(f)

    print(f"Sources: existing={len(existing)}, krdict={len(krdict)}, pyeonsu={len(pyeonsu)}")

    # Index by term_ko
    existing_map = {}
    for t in existing:
        k = t["term_ko"]
        existing_map[k] = t

    krdict_map = {}
    for t in krdict:
        k = t["term_ko"]
        krdict_map[k] = t

    pyeonsu_map = {}
    for t in pyeonsu:
        k = t["term_ko"]
        # pyeonsu에 중복 가능 (여러 과목에 같은 용어)
        if k in pyeonsu_map:
            # subjects 합치기
            pyeonsu_map[k]["subjects"] = list(
                set(pyeonsu_map[k]["subjects"]) | set(t.get("subjects", []))
            )
        else:
            pyeonsu_map[k] = t

    # All unique terms
    all_terms = set(existing_map) | set(krdict_map) | set(pyeonsu_map)
    print(f"Unique terms: {len(all_terms)}")

    merged = []
    stats = {"existing_only": 0, "krdict_new": 0, "pyeonsu_new": 0, "enriched": 0}

    for term_ko in sorted(all_terms):
        ex = existing_map.get(term_ko, {})
        kr = krdict_map.get(term_ko, {})
        py = pyeonsu_map.get(term_ko, {})

        # Subjects: union
        subjects = set()
        for s in ex.get("subjects", []):
            subjects.add(s)
        for s in normalize_subjects(kr.get("subjects", []), "krdict"):
            subjects.add(s)
        for s in normalize_subjects(py.get("subjects", []), "pyeonsu"):
            subjects.add(s)

        # Source tracking
        sources = []
        if ex:
            sources.append("edu4mc")
        if kr:
            sources.append("krdict")
        if py:
            sources.append("pyeonsu")

        entry = {
            "term_ko": term_ko,
            "definition_ko": merge_field(ex.get("definition_ko", ""), kr.get("definition_ko", ""), ""),
            "easy_ko": merge_field(ex.get("easy_ko", ""), kr.get("easy_ko", ""), ""),
            "en": merge_field_en(ex.get("en", ""), py.get("en", ""), kr.get("en", "")),
            "ja": merge_field(ex.get("ja", ""), kr.get("ja", ""), ""),
            "zh": merge_field(ex.get("zh", ""), kr.get("zh", ""), ""),
            "vi": merge_field(ex.get("vi", ""), kr.get("vi", ""), ""),
            "tl": merge_field(ex.get("tl", ""), kr.get("tl", ""), ""),
            "subjects": sorted(subjects),
            "source": "+".join(sources),
            "krdict_target_code": merge_field(
                ex.get("krdict_target_code", ""),
                kr.get("krdict_target_code", ""),
                "",
            ),
        }

        merged.append(entry)

        # Stats
        if ex and not kr and not py:
            stats["existing_only"] += 1
        elif not ex and kr and not py:
            stats["krdict_new"] += 1
        elif not ex and not kr and py:
            stats["pyeonsu_new"] += 1
        elif not ex and kr and py:
            stats["enriched"] += 1

    # Backup
    shutil.copy2(EXISTING_PATH, BACKUP_PATH)
    print(f"Backup: {BACKUP_PATH}")

    # Write
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {len(merged)} terms → {OUTPUT_PATH}")
    print(f"Stats: {stats}")

    # Coverage report
    en_cnt = sum(1 for t in merged if t["en"])
    ja_cnt = sum(1 for t in merged if t["ja"])
    zh_cnt = sum(1 for t in merged if t["zh"])
    vi_cnt = sum(1 for t in merged if t["vi"])
    tl_cnt = sum(1 for t in merged if t["tl"])
    defn_cnt = sum(1 for t in merged if t["definition_ko"])
    easy_cnt = sum(1 for t in merged if t["easy_ko"])

    print(f"\nCoverage:")
    print(f"  definition_ko: {defn_cnt}/{len(merged)} ({defn_cnt*100//len(merged)}%)")
    print(f"  easy_ko: {easy_cnt}/{len(merged)} ({easy_cnt*100//len(merged)}%)")
    print(f"  en: {en_cnt}/{len(merged)} ({en_cnt*100//len(merged)}%)")
    print(f"  ja: {ja_cnt}/{len(merged)} ({ja_cnt*100//len(merged)}%)")
    print(f"  zh: {zh_cnt}/{len(merged)} ({zh_cnt*100//len(merged)}%)")
    print(f"  vi: {vi_cnt}/{len(merged)} ({vi_cnt*100//len(merged)}%)")
    print(f"  tl: {tl_cnt}/{len(merged)} ({tl_cnt*100//len(merged)}%)")

    # Check key terms
    print("\nKey terms check:")
    key_terms = ["지권", "수권", "생물권", "외권", "광합성", "지층", "이산화탄소", "기권"]
    for kt in key_terms:
        found = [t for t in merged if t["term_ko"] == kt]
        if found:
            t = found[0]
            print(f"  {kt}: en={t['en'][:30] if t['en'] else '❌'}, "
                  f"ja={t['ja'][:20] if t['ja'] else '❌'}, "
                  f"zh={t['zh'][:10] if t['zh'] else '❌'}, "
                  f"vi={t['vi'][:20] if t['vi'] else '❌'}")
        else:
            print(f"  {kt}: ❌ NOT FOUND")


if __name__ == "__main__":
    merge()
