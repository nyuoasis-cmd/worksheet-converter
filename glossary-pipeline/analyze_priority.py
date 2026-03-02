#!/usr/bin/env python3
"""
빈출 용어 분석 스크립트
======================
목표: 18,265개 vocab_final.json 중 실제 워크시트에 자주 등장하는 용어를 추려내고,
      ja/zh/vi 번역이 빈 항목 수를 파악하여 "보강 대상 용어 리스트"를 산출한다.

기준:
  1) knowledge_*.json에 등장하는 교과 핵심 개념과 매칭
  2) subjects에 "과학", "수학", "사회" 포함 (빈출 교과)
  3) source에 "edu4mc" 또는 "krdict" 포함 (기초 용어)
"""

import json
import os
from collections import Counter

# ── 경로 설정 ──
BASE = "/home/claude/worksheet-converter"
KNOWLEDGE_DIR = os.path.join(BASE, "data/knowledge")
VOCAB_PATH = os.path.join(BASE, "data/vocab/vocab_final.json")

# ── 1. Knowledge 용어 수집 ──
def load_knowledge_terms():
    """knowledge_*.json 파일에서 모든 concept 용어를 수집한다."""
    terms = set()
    related = set()
    file_stats = {}

    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not fname.startswith("knowledge_") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(KNOWLEDGE_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for unit in data:
            for concept in unit.get("concepts", []):
                term = concept.get("concept", "").strip()
                if term:
                    terms.add(term)
                    count += 1
                # related_terms도 수집
                for rt in concept.get("related_terms", []):
                    rt = rt.strip()
                    if rt:
                        related.add(rt)
        file_stats[fname] = count

    return terms, related, file_stats


# ── 2. Vocab 로드 ──
def load_vocab():
    with open(VOCAB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 3. 분석 ──
def analyze():
    print("=" * 70)
    print("  빈출 용어 분석 보고서")
    print("=" * 70)

    # 1) Knowledge 용어 수집
    knowledge_terms, related_terms, file_stats = load_knowledge_terms()
    all_knowledge = knowledge_terms | related_terms

    print(f"\n[1] Knowledge 용어 현황")
    print(f"    knowledge_*.json 파일 수: {len(file_stats)}")
    print(f"    concept 고유 용어 수:     {len(knowledge_terms)}")
    print(f"    related_terms 고유 수:    {len(related_terms)}")
    print(f"    전체 고유 용어 (합집합):  {len(all_knowledge)}")
    print()
    print(f"    {'파일':<45} {'concept 수':>10}")
    print(f"    {'─'*45} {'─'*10}")
    for fname, count in sorted(file_stats.items()):
        print(f"    {fname:<45} {count:>10}")

    # 2) Vocab 로드
    vocab = load_vocab()
    print(f"\n[2] vocab_final.json 전체 현황")
    print(f"    전체 항목 수: {len(vocab)}")

    # 전체 번역 빈칸 현황
    total_empty = {"ja": 0, "zh": 0, "vi": 0, "en": 0, "tl": 0}
    for item in vocab:
        for lang in total_empty:
            if not item.get(lang, "").strip():
                total_empty[lang] += 1
    print(f"    전체 번역 빈칸 현황:")
    for lang, cnt in total_empty.items():
        print(f"      {lang}: {cnt:,} / {len(vocab):,} ({cnt/len(vocab)*100:.1f}%)")

    # 3) Knowledge 매칭
    knowledge_matched = []
    knowledge_matched_terms = set()
    for item in vocab:
        term = item.get("term_ko", "").strip()
        if term in all_knowledge:
            knowledge_matched.append(item)
            knowledge_matched_terms.add(term)

    unmatched_knowledge = all_knowledge - knowledge_matched_terms

    print(f"\n[3] Knowledge-Vocab 매칭")
    print(f"    knowledge 용어 중 vocab에 있는 수: {len(knowledge_matched_terms)} / {len(all_knowledge)}")
    print(f"    매칭된 vocab 항목 수:              {len(knowledge_matched)}")
    print(f"    (vocab에 동일 term_ko가 여러 번 있을 수 있음)")
    print(f"    vocab에 없는 knowledge 용어 수:    {len(unmatched_knowledge)}")

    km_empty = {"ja": 0, "zh": 0, "vi": 0}
    for item in knowledge_matched:
        for lang in km_empty:
            if not item.get(lang, "").strip():
                km_empty[lang] += 1
    print(f"    매칭 항목 중 번역 빈칸:")
    for lang, cnt in km_empty.items():
        print(f"      {lang}: {cnt} / {len(knowledge_matched)}")

    # 4) 빈출 교과 필터 (과학, 수학, 사회)
    freq_subjects = {"과학", "수학", "사회"}
    freq_subject_items = []
    for item in vocab:
        subjects = item.get("subjects", [])
        if any(any(fs in s for s in subjects) for fs in freq_subjects):
            freq_subject_items.append(item)

    print(f"\n[4] 빈출 교과 필터 (과학/수학/사회)")
    print(f"    해당 항목 수: {len(freq_subject_items)} / {len(vocab)}")

    fs_empty = {"ja": 0, "zh": 0, "vi": 0}
    for item in freq_subject_items:
        for lang in fs_empty:
            if not item.get(lang, "").strip():
                fs_empty[lang] += 1
    print(f"    번역 빈칸:")
    for lang, cnt in fs_empty.items():
        print(f"      {lang}: {cnt} / {len(freq_subject_items)}")

    # 5) Source 필터 (edu4mc 또는 krdict 포함)
    basic_source_items = []
    for item in vocab:
        src = item.get("source", "")
        if "edu4mc" in src or "krdict" in src:
            basic_source_items.append(item)

    source_counter = Counter()
    for item in vocab:
        source_counter[item.get("source", "")] += 1

    print(f"\n[5] Source 필터 (edu4mc/krdict 포함)")
    print(f"    해당 항목 수: {len(basic_source_items)} / {len(vocab)}")
    print(f"    source 분포:")
    for src, cnt in source_counter.most_common():
        marker = " <--" if ("edu4mc" in src or "krdict" in src) else ""
        print(f"      {src:<25} {cnt:>6}{marker}")

    bs_empty = {"ja": 0, "zh": 0, "vi": 0}
    for item in basic_source_items:
        for lang in bs_empty:
            if not item.get(lang, "").strip():
                bs_empty[lang] += 1
    print(f"    번역 빈칸:")
    for lang, cnt in bs_empty.items():
        print(f"      {lang}: {cnt} / {len(basic_source_items)}")

    # 6) 최종 보강 대상: 위 3개 기준 중 하나라도 해당 + ja/zh/vi 중 하나라도 빈 항목
    knowledge_term_set = {item["term_ko"] for item in knowledge_matched}
    freq_subject_term_set = {item["term_ko"] for item in freq_subject_items}
    basic_source_term_set = {item["term_ko"] for item in basic_source_items}

    priority_items = []
    priority_reasons = Counter()
    for item in vocab:
        term = item.get("term_ko", "").strip()
        reasons = []
        if term in knowledge_term_set:
            reasons.append("knowledge")
        if term in freq_subject_term_set:
            reasons.append("freq_subject")
        if term in basic_source_term_set:
            reasons.append("basic_source")

        if not reasons:
            continue

        has_empty = False
        for lang in ["ja", "zh", "vi"]:
            if not item.get(lang, "").strip():
                has_empty = True
                break

        if has_empty:
            priority_items.append((item, reasons))
            for r in reasons:
                priority_reasons[r] += 1

    print(f"\n{'=' * 70}")
    print(f"  [최종] 보강 대상 용어 리스트")
    print(f"{'=' * 70}")
    print(f"  조건: (knowledge 매칭 OR 빈출 교과 OR 기초 source) AND (ja/zh/vi 중 빈칸)")
    print(f"\n  전체 보강 대상 수: {len(priority_items)}")

    final_empty = {"ja": 0, "zh": 0, "vi": 0}
    all_three_empty = 0
    for item, _ in priority_items:
        empties = []
        for lang in ["ja", "zh", "vi"]:
            if not item.get(lang, "").strip():
                final_empty[lang] += 1
                empties.append(lang)
        if len(empties) == 3:
            all_three_empty += 1

    print(f"\n  언어별 빈칸 수:")
    print(f"    ja 빈 용어 수: {final_empty['ja']}")
    print(f"    zh 빈 용어 수: {final_empty['zh']}")
    print(f"    vi 빈 용어 수: {final_empty['vi']}")
    print(f"    3개 모두 빈 수: {all_three_empty}")

    print(f"\n  매칭 기준별 중복 포함 수:")
    for reason, cnt in priority_reasons.most_common():
        print(f"    {reason}: {cnt}")

    # 7) 기준별 교집합/합집합 분석
    print(f"\n  기준별 조합 분석:")
    combo_counter = Counter()
    for item, reasons in priority_items:
        combo_counter[tuple(sorted(reasons))] += 1
    for combo, cnt in combo_counter.most_common():
        print(f"    {' + '.join(combo)}: {cnt}")

    # 8) 보강 대상 중 상위 50개 샘플 (3개 모두 빈 항목 우선)
    print(f"\n  보강 대상 샘플 (ja+zh+vi 모두 빈 항목 우선, 상위 30개):")
    print(f"  {'term_ko':<20} {'subjects':<30} {'source':<20} {'reasons'}")
    print(f"  {'─'*20} {'─'*30} {'─'*20} {'─'*20}")

    # 3개 모두 빈 것 우선 정렬
    sorted_items = sorted(priority_items, key=lambda x: (
        -sum(1 for lang in ["ja","zh","vi"] if not x[0].get(lang,"").strip()),
        -len(x[1])
    ))

    for item, reasons in sorted_items[:30]:
        term = item["term_ko"]
        subjects = ", ".join(item.get("subjects", [])[:2])
        if len(item.get("subjects", [])) > 2:
            subjects += "..."
        source = item.get("source", "")
        empty_langs = [l for l in ["ja","zh","vi"] if not item.get(l,"").strip()]
        print(f"  {term:<20} {subjects:<30} {source:<20} {','.join(reasons)} (빈:{','.join(empty_langs)})")

    # 9) 고유 term 기준 집계 (중복 제거)
    print(f"\n{'=' * 70}")
    print(f"  [참고] 고유 term_ko 기준 집계 (중복 항목 제거)")
    print(f"{'=' * 70}")
    seen = set()
    unique_priority = []
    for item, reasons in priority_items:
        term = item["term_ko"]
        if term not in seen:
            seen.add(term)
            unique_priority.append((item, reasons))

    unique_empty = {"ja": 0, "zh": 0, "vi": 0}
    for item, _ in unique_priority:
        for lang in ["ja", "zh", "vi"]:
            if not item.get(lang, "").strip():
                unique_empty[lang] += 1

    print(f"  고유 용어 수: {len(unique_priority)}")
    print(f"    ja 빈 용어 수: {unique_empty['ja']}")
    print(f"    zh 빈 용어 수: {unique_empty['zh']}")
    print(f"    vi 빈 용어 수: {unique_empty['vi']}")

    print(f"\n{'=' * 70}")
    print(f"  분석 완료")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    analyze()
