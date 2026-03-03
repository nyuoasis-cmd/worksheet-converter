#!/usr/bin/env python3
"""
Gemini Batch 번역 — fr/es/ar/th/id/mn 추가
============================================
vocab_final.json에서 번역이 없는 언어를 Gemini로 채운다.
--lang 으로 언어 하나씩 지정해서 실행.
"""

import json
import os
import re
import sys
import time
import argparse
from pathlib import Path

import google.generativeai as genai

VOCAB_PATH = Path("/home/claude/worksheet-converter/data/vocab/vocab_final.json")
OUTPUT_DIR = Path("/home/claude/worksheet-converter/glossary-pipeline")

BATCH_SIZE = 50
MODEL = "gemini-2.0-flash"

LANG_META = {
    "fr": {"name": "프랑스어", "rule": "교과서에서 사용하는 공식 프랑스어 학술 용어"},
    "es": {"name": "스페인어", "rule": "교과서에서 사용하는 공식 스페인어 학술 용어"},
    "ar": {"name": "아랍어",   "rule": "교과서에서 사용하는 공식 아랍어 학술 용어 (아랍 문자)"},
    "th": {"name": "태국어",   "rule": "교과서에서 사용하는 공식 태국어 학술 용어 (태국 문자)"},
    "id": {"name": "인도네시아어", "rule": "교과서에서 사용하는 공식 인도네시아어 학술 용어"},
    "mn": {"name": "몽골어",   "rule": "교과서에서 사용하는 공식 몽골어 학술 용어 (키릴 문자)"},
}


def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_AI_API_KEY")
    if not key:
        env_path = Path("/home/claude/youthschool/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GOOGLE_AI_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
                    break
    if not key:
        print("ERROR: GEMINI_API_KEY 또는 GOOGLE_AI_API_KEY 필요")
        sys.exit(1)
    return key


def load_targets(lang: str) -> list[dict]:
    """해당 언어 번역이 없는 Tier 1 용어 추출 (다른 언어 번역이 있는 것 우선)"""
    vocab = json.load(open(VOCAB_PATH, encoding="utf-8"))

    tier1, tier2 = [], []
    for t in vocab:
        if t.get(lang):
            continue
        entry = {"term_ko": t["term_ko"], "en": t.get("en", "")}
        if any(t.get(l) for l in ["ja", "zh", "vi", "ru"]):
            tier1.append(entry)
        elif t.get("en"):
            tier2.append(entry)

    print(f"Tier 1 (다언어 보유): {len(tier1)}개")
    print(f"Tier 2 (영어만 보유): {len(tier2)}개")
    return tier1


def translate_batch(model, terms: list[dict], lang: str) -> dict[str, str]:
    meta = LANG_META[lang]
    lines = []
    for t in terms:
        en_hint = f" (en: {t['en']})" if t["en"] else ""
        lines.append(f"- {t['term_ko']}{en_hint}")

    prompt = f"""한국어 교육 용어를 {meta['name']}로 번역해주세요.

규칙:
1. {meta['rule']}
2. 영어 힌트가 있으면 참고하되, {meta['name']} 교과서 표현 우선
3. 번역이 확실하지 않으면 빈 문자열로
4. 고유명사는 현지 문자로 음차

JSON 배열로 반환. 각 항목: {{"ko": "한국어 용어", "{lang}": "{meta['name']} 번역"}}

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
        print(f"  Gemini 에러: {e}")
        return {}

    results = {}
    for item in items:
        ko = item.get("ko", "")
        val = item.get(lang, "")
        if ko and val:
            results[ko] = val
    return results


def apply_to_vocab(lang: str, results: dict):
    """번역 결과를 vocab_final.json에 직접 적용"""
    vocab = json.load(open(VOCAB_PATH, encoding="utf-8"))
    applied = 0
    for item in vocab:
        ko = item.get("term_ko", "")
        if ko in results and results[ko]:
            item[lang] = results[ko]
            applied += 1
    with open(VOCAB_PATH, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    has = sum(1 for v in vocab if v.get(lang))
    print(f"  → vocab_final.json 적용: {applied}개 / 누적 {has}/{len(vocab)} ({has*100/len(vocab):.1f}%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", required=True, choices=list(LANG_META.keys()),
                        help="번역할 언어 코드 (fr/es/ar/th/id/mn)")
    parser.add_argument("--apply", action="store_true",
                        help="번역 완료 후 vocab_final.json에 즉시 적용")
    args = parser.parse_args()

    lang = args.lang
    meta = LANG_META[lang]
    output = OUTPUT_DIR / f"gemini_results_{lang}.json"

    genai.configure(api_key=get_api_key())
    model = genai.GenerativeModel(MODEL)

    print(f"\n=== {meta['name']}({lang}) 번역 시작 ===")
    targets = load_targets(lang)
    if not targets:
        print("번역 대상 없음")
        return

    # 기존 결과 이어하기
    all_results = {}
    if output.exists():
        all_results = json.load(open(output, encoding="utf-8"))
        print(f"기존 결과 로드: {len(all_results)}개")
        targets = [t for t in targets if t["term_ko"] not in all_results]
        print(f"남은 대상: {len(targets)}개")

    total_batches = (len(targets) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"배치 수: {total_batches} (배치당 {BATCH_SIZE}개)\n")

    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  [{batch_num}/{total_batches}] {len(batch)}개 번역 중...", end=" ", flush=True)

        results = translate_batch(model, batch, lang)
        print(f"✅ {len(results)}/{len(batch)}")
        all_results.update(results)

        if batch_num % 10 == 0:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"  [중간 저장: {len(all_results)}개]")

        if i + BATCH_SIZE < len(targets):
            time.sleep(4)  # Gemini free tier: 15 RPM

    # 최종 저장
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n=== {meta['name']} 번역 완료 ===")
    print(f"총 번역: {len(all_results)}개")
    print(f"저장: {output}")

    if args.apply:
        print(f"\nvocab_final.json 적용 중...")
        apply_to_vocab(lang, all_results)


if __name__ == "__main__":
    main()
