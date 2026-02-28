#!/usr/bin/env python3
"""
국립국어원 한국어기초사전(krdict) API 크롤러
초등 3-4학년 과학 용어의 다국어 번역을 수집합니다.

사용법:
    export KRDICT_API_KEY="your-api-key"
    python krdict_crawler.py

API 키 발급: https://krdict.korean.go.kr/openApi/openApiRegister
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API_BASE = "https://krdict.korean.go.kr/api/search"
DETAIL_BASE = "https://krdict.korean.go.kr/api/view"

# 다국어 코드 매핑 (krdict API trans_lang 파라미터)
LANG_CODES = {
    "en": 1,   # 영어
    "zh": 5,   # 중국어
    "vi": 9,   # 베트남어
}

# 초등 3-4학년 과학 핵심 용어 목록
SCIENCE_TERMS = [
    "관찰", "측정", "예상", "분류", "실험", "탐구", "가설", "결론",
    "물질", "고체", "액체", "기체", "무게", "부피", "성질", "탄성",
    "자석", "나침반",
    "알", "애벌레", "번데기", "곤충", "변태",
    "동물", "식물", "서식지", "적응",
    "포유류", "조류", "파충류", "양서류", "어류",
    "척추동물", "무척추동물",
    "잎", "줄기", "뿌리", "꽃", "열매", "씨앗",
    "토양", "암석", "풍화", "침식", "퇴적",
    "지구", "육지", "바다", "공기",
    "지층", "화석", "퇴적암",
    "광합성", "양분",
    "증발", "응결", "수증기", "온도",
    "물의 순환",
    "빛", "그림자", "반사", "거울",
    "화산", "용암", "마그마", "지진",
    "혼합물",
    "힘", "소리", "진동",
    "환경", "생태계", "먹이사슬",
    "산소", "이산화탄소",
    "기후변화", "미생물", "현미경",
    "별", "별자리", "태양", "달",
]


def get_api_key():
    key = os.environ.get("KRDICT_API_KEY", "")
    if not key:
        print("ERROR: KRDICT_API_KEY 환경변수를 설정하세요.")
        print("  export KRDICT_API_KEY='your-api-key'")
        print("  API 키 발급: https://krdict.korean.go.kr/openApi/openApiRegister")
        sys.exit(1)
    return key


def search_term(api_key: str, term: str, lang_code: int) -> list[dict]:
    """한국어기초사전에서 용어를 검색하고 다국어 번역을 가져옵니다."""
    params = {
        "key": api_key,
        "q": term,
        "translated": "y",
        "trans_lang": lang_code,
        "sort": "popular",
        "num": 5,
        "part": "word",
        "type1": "word",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")
        return parse_search_result(xml_data, lang_code)
    except Exception as e:
        print(f"  [WARN] '{term}' 검색 실패 (lang={lang_code}): {e}")
        return []


def parse_search_result(xml_data: str, lang_code: int) -> list[dict]:
    """API XML 응답에서 용어와 번역을 추출합니다."""
    results = []
    try:
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item"):
            word_el = item.find("word")
            if word_el is None:
                continue
            word = word_el.text.strip() if word_el.text else ""

            # 정의(뜻) 추출
            definition = ""
            sense = item.find(".//sense")
            if sense is not None:
                def_el = sense.find("definition")
                if def_el is not None and def_el.text:
                    definition = def_el.text.strip()

            # 다국어 번역 추출
            translation = ""
            trans_el = item.find(".//translation")
            if trans_el is not None:
                trans_word = trans_el.find("trans_word")
                if trans_word is not None and trans_word.text:
                    translation = trans_word.text.strip()

            results.append({
                "word": word,
                "definition": definition,
                "translation": translation,
            })
    except ET.ParseError as e:
        print(f"  [WARN] XML 파싱 실패: {e}")
    return results


def collect_term(api_key: str, term: str) -> dict | None:
    """하나의 용어에 대해 3개 언어 번역을 수집합니다."""
    translations = {}

    for lang, code in LANG_CODES.items():
        results = search_term(api_key, term, code)
        if results:
            # 정확히 일치하는 결과 우선
            exact = [r for r in results if r["word"] == term]
            chosen = exact[0] if exact else results[0]
            if chosen["translation"]:
                translations[lang] = chosen["translation"]
        time.sleep(0.1)  # API 부하 방지

    if not translations:
        print(f"  [SKIP] '{term}': 번역 없음")
        return None

    return {
        "term_ko": term,
        "easy_ko": "",  # 수동 보완 필요
        "translations": translations,
        "subject": "과학",
        "grade_group": "3-4",
        "source": "krdict",
    }


def main():
    api_key = get_api_key()
    output_path = Path(__file__).parent.parent / "terms" / "science_3-4_krdict.json"

    print(f"=== 한국어기초사전 API 크롤러 ===")
    print(f"수집 대상: {len(SCIENCE_TERMS)}개 용어")
    print(f"출력 파일: {output_path}")
    print()

    collected = []
    for i, term in enumerate(SCIENCE_TERMS, 1):
        print(f"[{i}/{len(SCIENCE_TERMS)}] '{term}' 수집 중...")
        result = collect_term(api_key, term)
        if result:
            collected.append(result)
            langs = list(result["translations"].keys())
            print(f"  OK: {', '.join(langs)}")
        time.sleep(0.2)  # API 부하 방지

    # 결과 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collected, f, ensure_ascii=False, indent=2)

    print(f"\n=== 완료 ===")
    print(f"수집 성공: {len(collected)}/{len(SCIENCE_TERMS)}개")
    print(f"저장: {output_path}")


if __name__ == "__main__":
    main()
