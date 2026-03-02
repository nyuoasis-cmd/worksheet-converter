#!/usr/bin/env python3
"""zh 빈칸 574개 재시도 — Gemini로 tier1 zh 85% 달성"""

import json
import os
import re
import time

import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

vocab = json.load(open("data/vocab/vocab_final.json", encoding="utf-8"))
targets = json.load(open("glossary-pipeline/tier1_targets.json", encoding="utf-8"))
target_terms = {t["term_ko"] for t in targets}
vocab_map = {t["term_ko"]: t for t in vocab}

# zh가 아직 빈 tier1 용어 추출
need_zh = []
for ko in target_terms:
    item = vocab_map.get(ko, {})
    if not item.get("zh", "").strip():
        need_zh.append({"term_ko": ko, "en": item.get("en", "")})

print(f"zh 번역 필요: {len(need_zh)}개")

BATCH = 50
results = {}

for i in range(0, len(need_zh), BATCH):
    batch = need_zh[i : i + BATCH]
    batch_num = i // BATCH + 1
    total = (len(need_zh) + BATCH - 1) // BATCH

    lines = []
    for t in batch:
        en_hint = f' (en: {t["en"]})' if t["en"] else ""
        lines.append(f"- {t['term_ko']}{en_hint}")

    prompt = (
        "한국어 교육 용어를 중국어(간체자)로 번역해주세요.\n"
        "교과서/학술 용어에 적합한 공식 번역을 사용하세요.\n\n"
        'JSON 배열로 반환: [{"ko": "...", "zh": "..."}, ...]\n\n'
        "용어:\n" + "\n".join(lines) + "\n\nJSON만 출력:"
    )

    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            text = resp.text.strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            items = json.loads(text)
            count = 0
            for item in items:
                if item.get("ko") and item.get("zh"):
                    results[item["ko"]] = item["zh"]
                    count += 1
            print(f"  배치 {batch_num}/{total}: {count} 번역")
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                print(f"  배치 {batch_num}/{total}: 429 재시도 ({attempt + 1}/3)...")
                time.sleep(15)
            else:
                print(f"  배치 {batch_num}/{total}: 에러 {e}")
                break

    time.sleep(5)

# vocab에 적용
applied = 0
for item in vocab:
    ko = item.get("term_ko", "")
    if ko in results and not item.get("zh", "").strip():
        item["zh"] = results[ko]
        applied += 1

# 저장
with open("data/vocab/vocab_final.json", "w", encoding="utf-8") as f:
    json.dump(vocab, f, ensure_ascii=False, indent=2)

# 최종 tier1 zh 커버리지
vocab_reloaded = json.load(open("data/vocab/vocab_final.json", encoding="utf-8"))
vm = {t["term_ko"]: t for t in vocab_reloaded}
filled = sum(1 for ko in target_terms if vm.get(ko, {}).get("zh", "").strip())
pct = filled / len(target_terms) * 100
print(f"\n결과: {applied}개 추가 적용")
print(f"Tier 1 zh: {filled}/{len(target_terms)} ({pct:.1f}%)")
