#!/usr/bin/env python3
"""
Wikidata + Gemini 결과를 vocab_final.json에 병합
================================================
규칙: 기존 값은 절대 덮어쓰지 않음. 빈 필드만 채움.
우선순위: 기존 > Wikidata > Gemini
"""

import json
import shutil
from pathlib import Path

BASE = Path("/home/claude/worksheet-converter")
VOCAB = BASE / "data/vocab/vocab_final.json"
BACKUP = BASE / "data/vocab/vocab_final.json.bak2"
WIKIDATA = BASE / "glossary-pipeline/wikidata_results.json"
GEMINI = BASE / "glossary-pipeline/gemini_results.json"


def main():
    # 백업
    shutil.copy2(VOCAB, BACKUP)
    print(f"백업: {BACKUP}")

    vocab = json.load(open(VOCAB, encoding="utf-8"))
    wikidata = json.load(open(WIKIDATA, encoding="utf-8")) if WIKIDATA.exists() else {}
    gemini = json.load(open(GEMINI, encoding="utf-8")) if GEMINI.exists() else {}

    print(f"vocab_final.json: {len(vocab)}개")
    print(f"Wikidata 결과: {len(wikidata)}개")
    print(f"Gemini 결과: {len(gemini)}개")

    # 병합 전 통계
    pre = {lang: sum(1 for t in vocab if t.get(lang, "").strip()) for lang in ["ja", "zh", "vi"]}

    filled = {"wikidata": {"ja": 0, "zh": 0, "vi": 0}, "gemini": {"ja": 0, "zh": 0, "vi": 0}}

    for item in vocab:
        ko = item.get("term_ko", "").strip()
        if not ko:
            continue

        wd = wikidata.get(ko, {})
        gm = gemini.get(ko, {})

        for lang in ["ja", "zh", "vi"]:
            if item.get(lang, "").strip():
                continue  # 이미 있음 — 건드리지 않음

            # Wikidata 우선
            wd_val = wd.get(lang, "").strip()
            if wd_val:
                item[lang] = wd_val
                filled["wikidata"][lang] += 1
                continue

            # Gemini fallback
            gm_val = gm.get(lang, "").strip()
            if gm_val:
                item[lang] = gm_val
                filled["gemini"][lang] += 1

    # 병합 후 통계
    post = {lang: sum(1 for t in vocab if t.get(lang, "").strip()) for lang in ["ja", "zh", "vi"]}

    print(f"\n=== 병합 결과 ===")
    print(f"{'언어':<6} {'병합 전':>8} {'Wikidata':>10} {'Gemini':>10} {'병합 후':>8} {'증가':>8} {'커버리지':>10}")
    for lang in ["ja", "zh", "vi"]:
        delta = post[lang] - pre[lang]
        pct = post[lang] / len(vocab) * 100
        print(
            f"  {lang:<4} {pre[lang]:>8,} {filled['wikidata'][lang]:>10,} "
            f"{filled['gemini'][lang]:>10,} {post[lang]:>8,} {delta:>+8,} {pct:>9.1f}%"
        )

    # 저장
    with open(VOCAB, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {VOCAB}")

    # 기존 638개 보존 검증
    bak_original = BASE / "data/vocab/vocab_final.json.bak"
    if bak_original.exists():
        original = json.load(open(bak_original, encoding="utf-8"))
        vocab_map = {t["term_ko"]: t for t in vocab}
        preserved = True
        for term in original:
            ko = term["term_ko"]
            if ko not in vocab_map:
                print(f"  MISSING: {ko}")
                preserved = False
                continue
            for lang in ["en", "ja", "zh", "vi", "tl"]:
                orig_val = term.get(lang, "").strip()
                if orig_val and vocab_map[ko].get(lang, "").strip() != orig_val:
                    print(f"  CHANGED: {ko}[{lang}] '{orig_val}' → '{vocab_map[ko].get(lang, '')}'")
                    preserved = False
        if preserved:
            print(f"\n✅ 기존 {len(original)}개 용어 100% 보존 확인")
        else:
            print(f"\n❌ 기존 용어 변경 발견!")


if __name__ == "__main__":
    main()
