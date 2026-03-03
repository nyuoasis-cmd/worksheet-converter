"""RAG 조회 서비스.

data/vocab/vocab_final.json (18,265개) 과 data/knowledge/knowledge_*.json (2,450개 개념)에서
관련 어휘 및 교과 지식을 검색하여 프롬프트의 rag_context 문자열로 조립한다.

스키마:
  vocab_final.json 항목: term_ko, easy_ko, en/ja/zh/vi/tl (flat 필드), subjects (["과학 3-4"] 형태)
  knowledge_*.json 항목: [{subject, grade, unit, concepts: [{concept, easy_explanation}]}]

data/ 폴더는 읽기 전용. 수정하지 않는다.
"""

import json
import os
from functools import lru_cache
from typing import Optional

from backend.config import VOCAB_FINAL_PATH, KNOWLEDGE_DIR

LANG_LABELS = {"vi": "베트남어", "zh": "중국어", "en": "영어", "ja": "일본어", "tl": "필리핀어", "ru": "러시아어"}


@lru_cache(maxsize=1)
def _load_vocab() -> list[dict]:
    """vocab_final.json을 한 번만 로드."""
    if not os.path.exists(VOCAB_FINAL_PATH):
        return []
    with open(VOCAB_FINAL_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_knowledge() -> list[dict]:
    """knowledge_*.json 전체를 한 번만 로드."""
    results = []
    if not os.path.isdir(KNOWLEDGE_DIR):
        return results
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not fname.startswith("knowledge_") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(KNOWLEDGE_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                results.extend(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _match_subject_grade(subjects_arr: list[str], subject: str, grade_group: Optional[str]) -> bool:
    """subjects 배열 ["과학 3-4", ...] 에서 subject/grade_group 매칭.

    학년 없는 항목 (예: "과학")은 해당 과목의 모든 학년에 매칭된다.
    """
    for s in subjects_arr:
        parts = s.split(" ", 1)
        s_subj = parts[0]
        s_grade = parts[1] if len(parts) > 1 else ""
        if s_subj == subject:
            # 학년 없는 용어 → 전학년 매칭
            if not s_grade or grade_group is None or grade_group == s_grade:
                return True
    return False


def search_vocab(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
    languages: Optional[list[str]] = None,
    max_terms: int = 500,
) -> list[dict]:
    """vocab_final.json에서 조건에 맞는 용어 반환.

    languages가 지정되면 해당 언어 번역이 있는 용어를 우선 정렬한다.
    max_terms 상한을 적용하여 프롬프트 길이를 제어한다.
    """
    all_vocab = _load_vocab()
    if not subject and not grade_group:
        return []

    filtered = []
    for term in all_vocab:
        subjects_arr = term.get("subjects", [])
        if isinstance(subjects_arr, str):
            subjects_arr = [subjects_arr]

        if subject and not _match_subject_grade(subjects_arr, subject, grade_group):
            continue
        filtered.append(term)

    # 선택 언어 번역이 있는 용어를 앞으로 정렬
    if languages:
        def _has_translation(t):
            return sum(1 for lang in languages if t.get(lang, "")) > 0
        filtered.sort(key=lambda t: (not _has_translation(t), t.get("term_ko", "")))

    return filtered[:max_terms]


def search_knowledge(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
) -> list[dict]:
    """knowledge DB에서 조건에 맞는 단원 반환."""
    all_knowledge = _load_knowledge()
    if not subject and not grade_group:
        return []

    filtered = []
    for entry in all_knowledge:
        if subject and entry.get("subject", "") != subject:
            continue
        if grade_group and entry.get("grade", "") != grade_group:
            continue
        filtered.append(entry)

    return filtered


def build_rag_context(
    subject: Optional[str] = None,
    grade_group: Optional[str] = None,
    languages: Optional[list[str]] = None,
) -> str:
    """RAG 결과를 프롬프트에 주입할 문자열로 조립한다.

    subject/grade_group 힌트가 없으면 빈 문자열 반환 (모드1).
    데이터가 없어도 빈 문자열 반환 (에러 아님).

    Args:
        subject: 과목명 (예: "과학"). None이면 필터 없음.
        grade_group: 학년군 (예: "3-4"). None이면 필터 없음.
        languages: 다국어 코드 리스트 (예: ["vi", "zh"]).

    Returns:
        RAG 컨텍스트 문자열. 데이터 없으면 "".
    """
    if not subject and not grade_group:
        return ""

    vocab_items = search_vocab(subject=subject, grade_group=grade_group, languages=languages)
    knowledge_items = search_knowledge(subject=subject, grade_group=grade_group)

    if not vocab_items and not knowledge_items:
        return ""

    parts = []

    if vocab_items:
        parts.append("### 핵심 용어 (다국어 번역 참고)")
        for t in vocab_items:
            term = t.get("term_ko", "")
            easy = t.get("easy_ko", "") or t.get("definition_ko", "")
            line = f"- {term}"
            if easy:
                line += f": {easy}"
            # 요청된 언어 번역 추가
            if languages:
                trans_parts = []
                for lang in languages:
                    val = t.get(lang, "")
                    if val:
                        label = LANG_LABELS.get(lang, lang)
                        trans_parts.append(f"{label}: {val}")
                if trans_parts:
                    line += f" ({', '.join(trans_parts)})"
            parts.append(line)

    if knowledge_items:
        parts.append("\n### 교과 지식 (단원별 핵심 개념)")
        # 최대 5단원만 주입 (프롬프트 길이 제한)
        for entry in knowledge_items[:5]:
            unit = entry.get("unit", "")
            concepts = entry.get("concepts", [])
            if unit and concepts:
                parts.append(f"\n[{unit}]")
                for c in concepts[:10]:
                    concept = c.get("concept", "")
                    explanation = c.get("easy_explanation", "")
                    if concept and explanation:
                        parts.append(f"  - {concept}: {explanation}")

    return "\n".join(parts)
