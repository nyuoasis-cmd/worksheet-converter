#!/usr/bin/env python3
"""
Gemini Batch 번역 — 러시아어(ru) 추가
======================================
기존 ja/zh/vi 번역이 있는 Tier 1 용어를 대상으로 러시아어 번역 추가.
영어 힌트를 활용하여 정확도 향상.
"""

import json
import os
import re
import time
from pathlib import Path

import google.generativeai as genai

VOCAB_PATH = Path("/home/claude/worksheet-converter/data/vocab/vocab_final.json")
OUTPUT = Path("/home/claude/worksheet-converter/glossary-pipeline/gemini_results_ru.json")

BATCH_SIZE = 50
MODEL = "gemini-2.0-flash"


def load_targets() -> list[dict]:
    """러시아어 번역이 필요한 용어 추출 (Tier 1: 다른 언어 번역이 있는 것 우선)"""
    vocab = json.load(open(VOCAB_PATH, encoding="utf-8"))

    # Tier 1: 다른 언어 번역이 1개 이상 있는 용어 (핵심 교과 용어)
    tier1 = []
    tier2 = []
    for t in vocab:
        if t.get("ru"):  # 이미 러시아어 있으면 스킵
            continue
        has_other = any(t.get(lang) for lang in ["ja", "zh", "vi"])
        entry = {"term_ko": t["term_ko"], "en": t.get("en", "")}
        if has_other:
            tier1.append(entry)
        elif t.get("en"):
            tier2.append(entry)

    print(f"Tier 1 (다언어 보유): {len(tier1)}개")
    print(f"Tier 2 (영어만 보유): {len(tier2)}개")
    # Tier 1만 우선 처리
    return tier1


def translate_batch(model, terms: list[dict]) -> dict[str, str]:
    """Gemini에게 교육 용어 배치 → 러시아어 번역 요청"""
    lines = []
    for t in terms:
        en_hint = f" (en: {t['en']})" if t["en"] else ""
        lines.append(f"- {t['term_ko']}{en_hint}")

    prompt = f"""한국어 교육 용어를 러시아어로 번역해주세요. 교과서/학술 용어에 적합한 공식 번역을 사용하세요.

규칙:
1. 러시아어(ru): 교과서에서 사용하는 공식 학술 용어 사용
2. 영어 힌트가 있으면 참고하되, 러시아어 교과서 표현 우선
3. 번역이 확실하지 않으면 빈 문자열로
4. 고유명사는 키릴 문자로 음차

JSON 배열로 반환. 각 항목: {{"ko": "한국어 용어", "ru": "러시아어 번역"}}

용어 목록:
{chr(10).join(lines)}

JSON만 출력 (```json 마크다운 없이):"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        items = json.loads(text)
    except Exception as e:
        print(f"  Gemini error: {e}")
        return {}

    results = {}
    for item in items:
        ko = item.get("ko", "")
        ru = item.get("ru", "")
        if ko and ru:
            results[ko] = ru
    return results


def main():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY")
    if not api_key:
        # youthschool .env에서 로드
        env_path = Path("/home/claude/youthschool/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GOOGLE_AI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')
                    break
    if not api_key:
        print("ERROR: GEMINI_API_KEY 또는 GOOGLE_AI_API_KEY 필요")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL)

    targets = load_targets()
    if not targets:
        print("번역 대상 없음")
        return

    print(f"\nGemini 러시아어 번역 시작: {len(targets)}개")

    # 기존 결과 이어서 처리
    all_results = {}
    if OUTPUT.exists():
        all_results = json.load(open(OUTPUT, encoding="utf-8"))
        print(f"기존 결과 로드: {len(all_results)}개")
        # 이미 번역된 것 제외
        targets = [t for t in targets if t["term_ko"] not in all_results]
        print(f"남은 대상: {len(targets)}개")

    total_batches = (len(targets) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  배치 {batch_num}/{total_batches} ({len(batch)}개)...", end=" ", flush=True)

        results = translate_batch(model, batch)
        print(f"번역 {len(results)}/{len(batch)}")
        all_results.update(results)

        # 10 배치마다 중간 저장
        if batch_num % 10 == 0:
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"  [중간 저장: {len(all_results)}개]")

        # Rate limit (Gemini free tier: 15 RPM)
        if i + BATCH_SIZE < len(targets):
            time.sleep(4)

    # 최종 저장
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n=== 러시아어 번역 완료 ===")
    print(f"총 번역: {len(all_results)}개")
    print(f"저장: {OUTPUT}")


if __name__ == "__main__":
    main()
