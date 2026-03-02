#!/usr/bin/env python3
"""
Gemini Batch 번역 — Wikidata 미매칭 용어 보강
=============================================
Wikidata에서 번역을 못 찾은 용어를 Gemini에게 교육 용어 사전 번역 요청.
50개씩 배치로 처리, JSON 출력.
"""

import json
import os
import time
import re
from pathlib import Path

import google.generativeai as genai

BASE = Path("/home/claude/worksheet-converter/glossary-pipeline")
TARGETS = BASE / "tier1_targets.json"
WIKIDATA = BASE / "wikidata_results.json"
OUTPUT = BASE / "gemini_results.json"

BATCH_SIZE = 50
MODEL = "gemini-2.0-flash"


def load_remaining() -> list[dict]:
    """Wikidata 결과 적용 후에도 빈칸이 있는 용어만 추출"""
    targets = json.load(open(TARGETS, encoding="utf-8"))
    wikidata = json.load(open(WIKIDATA, encoding="utf-8")) if WIKIDATA.exists() else {}

    remaining = []
    for t in targets:
        ko = t["term_ko"]
        en = t.get("en", "")
        needs = {}
        wd = wikidata.get(ko, {})

        for lang in ["ja", "zh", "vi"]:
            if t["needs"][lang] and not wd.get(lang, ""):
                needs[lang] = True

        if needs:
            remaining.append({"term_ko": ko, "en": en, "needs": needs})

    return remaining


def translate_batch(model, terms: list[dict]) -> dict[str, dict]:
    """Gemini에게 교육 용어 배치 번역 요청"""
    # 번역 필요 언어 확인
    lines = []
    for t in terms:
        langs = [l for l in ["ja", "zh", "vi"] if t["needs"].get(l)]
        en_hint = f" (en: {t['en']})" if t["en"] else ""
        lines.append(f"- {t['term_ko']}{en_hint} → {','.join(langs)}")

    prompt = f"""한국어 교육 용어를 번역해주세요. 교과서/학술 용어에 적합한 공식 번역을 사용하세요.

규칙:
1. 일본어(ja): 한자어는 한자 표기 (예: 光合成), 일반어는 히라가나/카타카나
2. 중국어(zh): 간체자 사용 (예: 光合作用)
3. 베트남어(vi): 한자어는 한월음 사용 (예: quang hợp)
4. 각 용어의 지정된 언어만 번역
5. 번역이 확실하지 않으면 빈 문자열로

JSON 배열로 반환. 각 항목: {{"ko": "용어", "ja": "...", "zh": "...", "vi": "..."}}
지정되지 않은 언어 필드는 생략.

용어 목록:
{chr(10).join(lines)}

JSON만 출력 (```json 마크다운 없이):"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # markdown fence 제거
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        items = json.loads(text)
    except Exception as e:
        print(f"  Gemini error: {e}")
        return {}

    results = {}
    for item in items:
        ko = item.get("ko", "")
        if ko:
            results[ko] = {
                "ja": item.get("ja", ""),
                "zh": item.get("zh", ""),
                "vi": item.get("vi", ""),
            }
    return results


def main():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL)

    remaining = load_remaining()
    print(f"Gemini 번역 대상: {len(remaining)}개")
    print(f"  ja 필요: {sum(1 for t in remaining if t['needs'].get('ja'))}")
    print(f"  zh 필요: {sum(1 for t in remaining if t['needs'].get('zh'))}")
    print(f"  vi 필요: {sum(1 for t in remaining if t['needs'].get('vi'))}")

    all_results = {}
    total_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  배치 {batch_num}/{total_batches} ({len(batch)}개)...", end=" ", flush=True)

        results = translate_batch(model, batch)
        print(f"번역 {len(results)}/{len(batch)}")
        all_results.update(results)

        # Gemini rate limit: 15 RPM for free tier
        if i + BATCH_SIZE < len(remaining):
            time.sleep(4)

    # 통계
    has_ja = sum(1 for v in all_results.values() if v.get("ja"))
    has_zh = sum(1 for v in all_results.values() if v.get("zh"))
    has_vi = sum(1 for v in all_results.values() if v.get("vi"))
    print(f"\n=== Gemini 결과 ===")
    print(f"총 번역: {len(all_results)}")
    print(f"  ja: {has_ja}")
    print(f"  zh: {has_zh}")
    print(f"  vi: {has_vi}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"저장: {OUTPUT}")


if __name__ == "__main__":
    main()
