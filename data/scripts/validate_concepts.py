#!/usr/bin/env python3
"""
초등 3-4학년 과학 교과 지식 DB 검증 스크립트
검증 항목:
1. JSON 파싱 검증
2. easy_explanation 문장 15자 이내 확인
3. related_terms 비어있지 않은지 확인
4. 단원 수, 총 concept 수 출력
5. 스키마 필수 필드 확인
"""

import json
import re
import sys
import os

JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'concepts', 'science_3-4.json')

def split_sentences(text):
    """문장을 ~해요/~이에요/~예요 등의 종결어미 기준으로 분리"""
    # 마침표 기준으로 분리하되, 빈 문장 제거
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    # 마침표가 없으면 원문 그대로
    if not sentences:
        sentences = [text.strip()]
    return sentences

def count_display_chars(text):
    """표시되는 글자 수 (공백 포함, 마침표 제외)"""
    # 마침표 제거 후 길이 측정
    return len(text.rstrip('.'))

def main():
    errors = []
    warnings = []

    # === 1. JSON 파싱 검증 ===
    print("=" * 60)
    print("1. JSON 파싱 검증")
    print("=" * 60)
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"   [PASS] JSON 파싱 성공 ({len(data)}개 단원)")
    except json.JSONDecodeError as e:
        print(f"   [FAIL] JSON 파싱 실패: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"   [FAIL] 파일 없음: {JSON_PATH}")
        sys.exit(1)

    # === 2. 스키마 검증 ===
    print("\n" + "=" * 60)
    print("2. 스키마 검증")
    print("=" * 60)
    required_unit_fields = {"subject", "grade_group", "unit", "concepts"}
    required_concept_fields = {"concept", "easy_explanation", "related_terms"}

    for i, unit in enumerate(data):
        missing = required_unit_fields - set(unit.keys())
        if missing:
            errors.append(f"단원[{i}]: 필수 필드 누락 {missing}")

        if unit.get("subject") != "과학":
            errors.append(f"단원[{i}]: subject가 '과학'이 아님 → '{unit.get('subject')}'")
        if unit.get("grade_group") != "3-4":
            errors.append(f"단원[{i}]: grade_group이 '3-4'가 아님 → '{unit.get('grade_group')}'")

        for j, concept in enumerate(unit.get("concepts", [])):
            missing_c = required_concept_fields - set(concept.keys())
            if missing_c:
                errors.append(f"단원[{i}].concepts[{j}]: 필수 필드 누락 {missing_c}")

    if not errors:
        print("   [PASS] 모든 단원/개념의 필수 필드 존재")
    else:
        for e in errors:
            print(f"   [FAIL] {e}")

    # === 3. easy_explanation 문장 15자 이내 확인 ===
    print("\n" + "=" * 60)
    print("3. easy_explanation 문장 길이 검증 (15자 이내)")
    print("=" * 60)
    long_sentences = []
    total_sentences = 0

    for unit in data:
        for concept in unit.get("concepts", []):
            sentences = split_sentences(concept["easy_explanation"])
            for sent in sentences:
                total_sentences += 1
                char_count = count_display_chars(sent)
                if char_count > 15:
                    long_sentences.append({
                        "unit": unit["unit"],
                        "concept": concept["concept"],
                        "sentence": sent,
                        "length": char_count
                    })

    if long_sentences:
        print(f"   [WARN] 15자 초과 문장 {len(long_sentences)}개 / 전체 {total_sentences}개")
        for item in long_sentences:
            print(f"     - [{item['length']}자] {item['unit']} > {item['concept']}")
            print(f"       \"{item['sentence']}\"")
    else:
        print(f"   [PASS] 모든 문장 15자 이내 (전체 {total_sentences}개)")

    # === 4. related_terms 비어있지 않은지 확인 ===
    print("\n" + "=" * 60)
    print("4. related_terms 비어있지 않은지 확인")
    print("=" * 60)
    empty_terms = []
    for unit in data:
        for concept in unit.get("concepts", []):
            if not concept.get("related_terms") or len(concept["related_terms"]) == 0:
                empty_terms.append(f"{unit['unit']} > {concept['concept']}")

    if empty_terms:
        for e in empty_terms:
            print(f"   [FAIL] related_terms 비어있음: {e}")
            errors.append(f"related_terms 비어있음: {e}")
    else:
        total_concepts = sum(len(u.get("concepts", [])) for u in data)
        print(f"   [PASS] 모든 {total_concepts}개 concept에 related_terms 존재")

    # === 5. 통계 출력 ===
    print("\n" + "=" * 60)
    print("5. 통계")
    print("=" * 60)
    total_units = len(data)
    total_concepts = sum(len(u.get("concepts", [])) for u in data)
    total_terms = sum(
        len(c.get("related_terms", []))
        for u in data
        for c in u.get("concepts", [])
    )

    print(f"   단원 수: {total_units}")
    print(f"   총 concept 수: {total_concepts}")
    print(f"   총 related_terms 수: {total_terms}")
    print(f"   concept당 평균 related_terms: {total_terms/total_concepts:.1f}")

    # 학기별 통계
    semesters = {}
    for unit in data:
        key = unit["unit"][:3]  # "3-1", "3-2", "4-1", "4-2"
        if key not in semesters:
            semesters[key] = {"units": 0, "concepts": 0}
        semesters[key]["units"] += 1
        semesters[key]["concepts"] += len(unit.get("concepts", []))

    print("\n   학기별 분포:")
    for sem, stats in sorted(semesters.items()):
        print(f"     {sem}: {stats['units']}개 단원, {stats['concepts']}개 concept")

    # === 6. ~해요 체 확인 ===
    print("\n" + "=" * 60)
    print("6. ~해요 체 사용 확인")
    print("=" * 60)
    non_haeyo = []
    for unit in data:
        for concept in unit.get("concepts", []):
            sentences = split_sentences(concept["easy_explanation"])
            for sent in sentences:
                clean = sent.rstrip('.')
                if not re.search(r'(요|에요|예요|어요|아요|져요|려요|워요|돼요)$', clean):
                    non_haeyo.append({
                        "unit": unit["unit"],
                        "concept": concept["concept"],
                        "sentence": sent
                    })

    if non_haeyo:
        print(f"   [WARN] ~해요 체가 아닌 문장 {len(non_haeyo)}개")
        for item in non_haeyo:
            print(f"     - {item['unit']} > {item['concept']}: \"{item['sentence']}\"")
    else:
        print(f"   [PASS] 모든 문장이 ~해요 체 사용")

    # === 최종 결과 ===
    print("\n" + "=" * 60)
    print("최종 결과")
    print("=" * 60)
    if errors:
        print(f"   [FAIL] {len(errors)}개 오류 발견")
        sys.exit(1)
    elif long_sentences or non_haeyo:
        print(f"   [WARN] 경고 {len(long_sentences) + len(non_haeyo)}개 (수정 권장)")
        sys.exit(0)
    else:
        print("   [PASS] 모든 검증 통과!")
        sys.exit(0)

if __name__ == "__main__":
    main()
