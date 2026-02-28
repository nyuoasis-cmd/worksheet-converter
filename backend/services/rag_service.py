"""RAG 조회 서비스.

data/terms/*.json과 data/concepts/*.json에서 관련 용어 및 지식을 검색하여
프롬프트의 rag_context에 주입할 문자열로 조립한다.

data/ 폴더는 읽기 전용. 수정하지 않는다.
"""

import json
import os
from typing import Optional

from backend.config import TERMS_DIR, CONCEPTS_DIR


def _load_json_files(directory: str) -> list[dict]:
    """디렉토리 내 모든 JSON 파일을 읽어 리스트로 반환한다."""
    results = []
    if not os.path.isdir(directory):
        return results
    for filename in os.listdir(directory):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(directory, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def search_terms(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
    languages: Optional[list[str]] = None,
) -> list[dict]:
    """조건에 맞는 용어를 검색한다."""
    all_terms = _load_json_files(TERMS_DIR)
    filtered = []
    for term in all_terms:
        if subject and term.get("subject", "").lower() != subject.lower():
            continue
        if grade_group and term.get("grade_group") != grade_group:
            continue
        filtered.append(term)
    return filtered


def search_concepts(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
) -> list[dict]:
    """조건에 맞는 교과 지식을 검색한다."""
    all_concepts = _load_json_files(CONCEPTS_DIR)
    filtered = []
    for concept in all_concepts:
        if subject and concept.get("subject", "").lower() != subject.lower():
            continue
        if grade_group and concept.get("grade_group") != grade_group:
            continue
        filtered.append(concept)
    return filtered


def build_rag_context(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
    languages: Optional[list[str]] = None,
) -> str:
    """RAG 결과를 프롬프트에 주입할 문자열로 조립한다.

    데이터가 없으면 빈 문자열을 반환한다 (에러 아님).

    Args:
        subject: 과목명 (예: "과학").
        grade_group: 학년군 (예: "3-4").
        languages: 다국어 코드 리스트 (예: ["vi", "zh"]).

    Returns:
        RAG 컨텍스트 문자열. 데이터 없으면 "".
    """
    # 필터 조건이 하나도 없으면 전체 DB를 덤프하지 않음 (모드1)
    if not subject and not grade_group:
        return ""

    terms = search_terms(subject=subject, grade_group=grade_group, languages=languages)
    concepts = search_concepts(subject=subject, grade_group=grade_group)

    if not terms and not concepts:
        return ""

    parts = []

    if terms:
        parts.append("### 핵심 용어")
        for t in terms:
            line = f"- {t.get('term_ko', '?')}: {t.get('easy_ko', '')}"
            translations = t.get("translations", {})
            if languages and translations:
                lang_parts = []
                for lang in languages:
                    if lang in translations:
                        lang_parts.append(f"{lang}: {translations[lang]}")
                if lang_parts:
                    line += f" ({', '.join(lang_parts)})"
            parts.append(line)

    if concepts:
        parts.append("\n### 교과 지식")
        for c in concepts:
            unit = c.get("unit", "")
            if unit:
                parts.append(f"\n#### {unit}")
            for item in c.get("concepts", []):
                parts.append(f"- {item.get('concept', '?')}: {item.get('easy_explanation', '')}")

    return "\n".join(parts)
