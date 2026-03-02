"""Gemini 출력 HTML에서 glossary 기반 강제 치환."""
import re
from typing import Optional


def apply_glossary_postprocess(
    html: str,
    vocab: list[dict],
    languages: list[str],
) -> str:
    """
    ko-ref 역참조 기반 강제 치환.

    HTML 구조 예시:
    岩石圈 <span class="ko-ref">[지권]</span>

    동작:
    1. <span class="ko-ref">[한국어]</span> 패턴에서 한국어 용어 추출
    2. vocab에서 해당 용어 찾기
    3. ko-ref 바로 앞의 번역이 glossary와 다르면 교체
    """
    if not vocab or not languages:
        return html

    # vocab을 term_ko 기준 딕셔너리로 변환
    vocab_map = {t["term_ko"]: t for t in vocab if t.get("term_ko")}

    # ko-ref 패턴: (번역어)(공백/태그)(ko-ref span)
    # 번역어 부분을 glossary 값으로 교체
    def replace_with_glossary(match):
        before_text = match.group(1)  # ko-ref 앞의 번역어
        ko_term = match.group(2)      # 한국어 원문
        full_span = match.group(0)    # 전체 매치

        if ko_term not in vocab_map:
            return full_span

        term_data = vocab_map[ko_term]

        # 각 언어별로 올바른 번역 확인
        for lang in languages:
            correct = term_data.get(lang, "")
            if not correct:
                continue
            # before_text에 올바른 번역이 이미 있으면 skip
            if correct in before_text:
                continue
            # 올바른 번역으로 교체
            # before_text 전체를 교체 (오역이 포함되어 있으므로)
            return correct + match.group(0)[len(before_text):]

        return full_span

    # 패턴: (비HTML텍스트)(공백*)<span class="ko-ref">[용어]</span>
    pattern = r'([^<>]{1,50})\s*<span\s+class="ko-ref">\[([^\]]+)\]</span>'
    html = re.sub(pattern, replace_with_glossary, html)

    return html
