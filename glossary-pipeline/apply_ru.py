#!/usr/bin/env python3
"""
러시아어 번역 결과를 vocab_final.json에 적용
"""

import json
from pathlib import Path

VOCAB_PATH = Path("/home/claude/worksheet-converter/data/vocab/vocab_final.json")
RU_RESULTS = Path("/home/claude/worksheet-converter/glossary-pipeline/gemini_results_ru.json")


def main():
    vocab = json.load(open(VOCAB_PATH, encoding="utf-8"))
    ru_data = json.load(open(RU_RESULTS, encoding="utf-8"))

    print(f"어휘DB: {len(vocab)}개")
    print(f"러시아어 번역: {len(ru_data)}개")

    applied = 0
    for item in vocab:
        ko = item.get("term_ko", "")
        if ko in ru_data and ru_data[ko]:
            item["ru"] = ru_data[ko]
            applied += 1

    print(f"적용: {applied}개")

    # 저장
    with open(VOCAB_PATH, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {VOCAB_PATH}")

    # 검증
    vocab2 = json.load(open(VOCAB_PATH, encoding="utf-8"))
    has_ru = sum(1 for v in vocab2 if v.get("ru"))
    print(f"검증: ru 보유 {has_ru}/{len(vocab2)} ({has_ru*100/len(vocab2):.1f}%)")


if __name__ == "__main__":
    main()
