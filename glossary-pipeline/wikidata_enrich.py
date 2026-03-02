#!/usr/bin/env python3
"""
Wikidata SPARQL 기반 다국어 번역 수집
=====================================
tier1_targets.json의 용어를 Wikidata에서 ja/zh/vi 번역 조회.
SPARQL VALUES 절로 100개씩 배치 쿼리.
"""

import json
import time
import requests
from pathlib import Path

BASE = Path("/home/claude/worksheet-converter/glossary-pipeline")
TARGETS = BASE / "tier1_targets.json"
OUTPUT = BASE / "wikidata_results.json"

SPARQL_URL = "https://query.wikidata.org/sparql"
BATCH_SIZE = 80  # VALUES clause limit safe range
HEADERS = {
    "User-Agent": "TeacherMate-GlossaryBot/1.0 (educational; contact: teachermate)",
    "Accept": "application/json",
}


def sparql_batch(terms_ko: list[str]) -> dict[str, dict]:
    """SPARQL로 한국어 용어 → ja/zh/vi 라벨 조회"""
    values = " ".join(f'"{t}"@ko' for t in terms_ko)
    query = f"""
    SELECT ?item ?koLabel ?jaLabel ?zhLabel ?viLabel WHERE {{
      ?item rdfs:label ?koLabel .
      FILTER(LANG(?koLabel) = "ko")
      VALUES ?koLabel {{ {values} }}
      OPTIONAL {{ ?item rdfs:label ?jaLabel . FILTER(LANG(?jaLabel) = "ja") }}
      OPTIONAL {{ ?item rdfs:label ?zhLabel . FILTER(LANG(?zhLabel) = "zh") }}
      OPTIONAL {{ ?item rdfs:label ?viLabel . FILTER(LANG(?viLabel) = "vi") }}
    }}
    """
    try:
        resp = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  SPARQL error: {e}")
        return {}

    results = {}
    for binding in data.get("results", {}).get("bindings", []):
        ko = binding.get("koLabel", {}).get("value", "")
        if not ko:
            continue
        if ko not in results:
            results[ko] = {"ja": "", "zh": "", "vi": ""}
        for lang, key in [("ja", "jaLabel"), ("zh", "zhLabel"), ("vi", "viLabel")]:
            val = binding.get(key, {}).get("value", "")
            if val and not results[ko][lang]:
                results[ko][lang] = val
    return results


def main():
    targets = json.load(open(TARGETS, encoding="utf-8"))
    # zh가 필요한 용어만 (3,270개 전부)
    terms = [t["term_ko"] for t in targets]
    print(f"총 대상: {len(terms)}개")

    all_results = {}
    total_batches = (len(terms) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(terms), BATCH_SIZE):
        batch = terms[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  배치 {batch_num}/{total_batches} ({len(batch)}개)...", end=" ", flush=True)

        results = sparql_batch(batch)
        matched = sum(1 for v in results.values() if any(v.values()))
        print(f"매칭 {matched}/{len(batch)}")
        all_results.update(results)

        if i + BATCH_SIZE < len(terms):
            time.sleep(2)  # rate limit

    # 통계
    has_ja = sum(1 for v in all_results.values() if v.get("ja"))
    has_zh = sum(1 for v in all_results.values() if v.get("zh"))
    has_vi = sum(1 for v in all_results.values() if v.get("vi"))
    print(f"\n=== Wikidata 결과 ===")
    print(f"총 매칭: {len(all_results)} / {len(terms)}")
    print(f"  ja: {has_ja}")
    print(f"  zh: {has_zh}")
    print(f"  vi: {has_vi}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"저장: {OUTPUT}")


if __name__ == "__main__":
    main()
