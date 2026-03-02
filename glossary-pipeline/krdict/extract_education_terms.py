#!/usr/bin/env python3
"""
krdict 교육 용어 추출 스크립트

한국어기초사전(krdict) XML 데이터에서 교육 관련 용어를 추출하여
vocab_final.json 호환 형식으로 저장합니다.

사용법:
    python3 extract_education_terms.py [--data-dir /tmp/krdict-data] [--output krdict_education_terms.json]
"""

import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# ─── 필터 키워드 ─────────────────────────────────────────────────
# 키워드는 (keyword, min_word_len) 튜플. word 자체가 키워드를 포함하는 경우와
# definition이 키워드를 포함하는 경우를 구분하여 처리.
#
# 전략:
#   - word에 키워드가 포함되면 바로 매칭 (단, 2글자 이상 키워드만)
#   - definition에 키워드가 포함되면 word가 명사이고 2글자 이상일 때만 매칭
#   - 1글자 키워드("수","힘" 등)는 word 자체가 정확히 일치할 때만 매칭

# 과학 키워드 (word에 포함되거나, definition에 포함)
SCIENCE_WORD_KEYWORDS = [
    # 2글자 이상: word에 포함되면 매칭
    "지구", "생물", "화학", "물리", "세포", "원자", "에너지", "운동", "전기",
    "파동", "생태", "유전", "진화", "지층", "암석", "화산", "대기",
    "해양", "우주", "광합성", "호흡", "소화", "순환", "신경", "호르몬",
    "분자", "원소", "반응", "용액", "산화", "환원", "전자", "양성자",
    "중성자", "이온", "염기", "중력", "가속도", "속력",
    "마찰", "전류", "전압", "저항", "렌즈", "거울", "스펙트럼",
    "방사선", "방사능", "동위원소", "촉매", "효소", "단백질", "탄수화물", "지질",
    "핵산", "염색체", "유전자", "돌연변이", "자연선택", "적응",
    "군집", "개체군", "먹이사슬", "분해자", "생산자", "소비자",
    "지각", "맨틀", "지진", "습곡", "단층", "풍화", "침식",
    "퇴적", "화석", "대륙", "해류", "조류", "태양", "행성", "항성",
    "은하", "성운", "혜성", "소행성", "위성", "궤도",
    "밀도", "부력", "압력", "온도", "전도", "대류", "복사",
    "증발", "응결", "승화", "기체", "액체", "고체", "용해", "농도",
    "삼투", "확산", "조직", "개체",
    "현미경", "실험", "관찰", "측정", "가설",
    "광물", "지권", "기권", "수권", "생물권", "외권",
    "지자기", "자기장", "전기장", "중력장",
    "렌즈", "프리즘", "반사", "굴절", "회절", "간섭",
    "질량", "무게", "관성", "작용", "가속",
    "산성", "알칼리", "중화", "전해질",
    "광합", "세포막", "세포벽", "핵막", "미토콘드리아", "엽록체",
    "염록소", "기공", "증산", "삼투압",
    "신장", "심장", "폐", "간", "위장", "소장", "대장",
    "적혈구", "백혈구", "혈소판", "혈장", "항체", "항원", "면역",
    "척추", "골격", "근육", "건", "인대",
    "지구온난화", "온실효과", "오존층", "산성비",
    "생태계", "먹이그물", "에너지흐름", "물질순환",
    "생식", "수정", "발생", "감수분열", "체세포분열",
    "자극", "반응속도", "촉매작용",
]

SCIENCE_DEF_KEYWORDS = [
    # definition에 이 키워드가 있으면 과학 관련 용어
    "화학 원소", "화학 반응", "화학적", "화학에서", "물리학에서", "물리적",
    "생물학에서", "생물학적", "지구과학", "천문학",
    "세포의", "세포를", "세포가", "원자의", "원자를", "분자의", "분자를",
    "에너지를", "에너지의", "에너지가",
    "생태계", "먹이 사슬", "먹이 그물",
    "유전의", "유전적", "유전자",
    "광합성", "호흡 작용", "소화 기관",
    "자기장", "전기장", "전류가", "전압을",
    "화산 활동", "지진이", "지층이",
    "행성의", "항성의", "은하의", "태양의",
    "기체의", "액체의", "고체의",
    "산화와", "환원과", "중화 반응",
    "원소 기호", "주기율표",
]

MATH_WORD_KEYWORDS = [
    "방정식", "함수", "도형", "삼각", "넓이", "부피", "확률", "통계",
    "집합", "벡터", "미분", "적분", "수열", "급수", "극한",
    "다항식", "분수", "소수", "정수", "유리수", "무리수", "실수", "허수",
    "복소수", "절댓값", "제곱", "제곱근", "거듭제곱", "로그", "지수함수",
    "비례", "반비례", "비율", "백분율", "평균", "분산", "표준편차",
    "중앙값", "최빈값", "상관관계", "회귀",
    "직선", "곡선", "타원", "포물선", "쌍곡선",
    "대칭", "합동", "닮음", "평행", "수직", "교점", "접선",
    "부채꼴", "각도", "예각", "둔각", "직각",
    "삼각형", "사각형", "오각형", "육각형", "다각형",
    "정육면체", "직육면체", "원기둥", "원뿔",
    "좌표", "그래프", "기울기", "절편", "점근선",
    "순열", "조합", "독립사건",
    "행렬", "역행렬", "고유값",
    "연립", "부등식", "인수분해",
    "덧셈", "뺄셈", "곱셈", "나눗셈",
    "피타고라스", "유클리드",
    "호도법", "라디안",
    "정비례", "등차수열", "등비수열",
    "약수", "배수", "공약수", "공배수", "최대공약수", "최소공배수",
]

MATH_DEF_KEYWORDS = [
    "수학에서", "수학적", "방정식의", "방정식을",
    "함수의", "함수를", "도형의", "도형을",
    "삼각형의", "사각형의", "원의 넓이",
    "확률을", "확률의", "통계에서", "통계적",
    "집합의", "집합을", "벡터의", "벡터를",
    "미분하", "적분하", "수열의", "수열을",
]

SOCIAL_WORD_KEYWORDS = [
    "민주", "경제", "헌법", "인권", "정치",
    "선거", "투표", "정당", "시민", "주권", "삼권분립", "사법", "입법",
    "조세", "세금", "예산", "무역", "수출", "수입", "관세",
    "환율", "물가", "인플레이션", "디플레이션", "실업", "고용",
    "소득", "분배", "복지", "연금",
    "자본주의", "사회주의", "공산주의", "민족",
    "식민", "봉건", "왕조",
    "외교", "세계화",
    "위도", "경도", "적도", "열대", "온대", "한대",
    "평야", "고원", "분지", "반도",
    "산업화", "도시화",
    "계급", "계층", "불평등", "다문화",
    "권력", "정의", "의무",
    "독재", "공화", "군주", "입헌",
    "국민총생산", "국내총생산",
    "노동", "자본", "기업", "시장경제", "계획경제",
    "공급", "수요", "균형가격",
    "인구밀도", "도시문제", "환경문제",
    "남북문제", "냉전", "통일",
    "유엔", "국제연합", "세계무역기구",
]

SOCIAL_DEF_KEYWORDS = [
    "정치에서", "정치적", "경제에서", "경제적", "경제학에서",
    "사회에서", "사회적", "사회학에서",
    "역사에서", "역사적", "역사학에서",
    "지리에서", "지리적", "지리학에서",
    "법률에서", "법률적", "법학에서",
    "헌법에서", "헌법의", "헌법을",
    "민주주의", "민주적", "인권의", "인권을",
]

KOREAN_WORD_KEYWORDS = [
    "문장", "문법", "주어", "서술어",
    "접속사", "어미", "접사", "어근", "어간", "어절",
    "음운", "음절", "자음", "모음", "받침", "성조",
    "형태소", "음소",
    "유의어", "반의어", "다의어", "동음이의어",
    "은유", "직유", "상징", "풍자", "역설", "반어", "도치",
    "서사", "서정", "수필", "희곡",
    "서술자", "시점",
    "운율", "비유", "묘사",
    "독해", "작문",
    "존댓말", "높임말", "경어",
    "띄어쓰기", "맞춤법", "표준어", "방언",
    "관형사", "감탄사", "대명사", "수사",
    "합성어", "파생어", "단일어",
    "주성분", "부속성분", "독립성분",
    "홑문장", "겹문장", "이어진문장", "안은문장",
    "능동", "피동", "사동",
    "높임법", "시제", "양태",
]

KOREAN_DEF_KEYWORDS = [
    "문법에서", "문법적", "국어에서", "국어학에서",
    "언어에서", "언어학에서", "언어적",
    "문장의", "문장에서", "문장을",
    "품사의", "품사에서", "품사를",
    "어근의", "어간의", "어미의",
    "주어의", "서술어의", "목적어의",
]

# ─── 의미 범주 → 과목 매핑 ─────────────────────────────────────

SEMANTIC_TO_SUBJECT = {
    "교육 > 학문 용어": "교육",
    "교육 > 전공과 교과목": "교육",
    "교육 > 교수 학습 행위": "교육",
    "교육 > 교수 학습 주체": "교육",
    "교육 > 교육 기관": "교육",
    "교육 > 학교 시설": "교육",
    "교육 > 학문 행위": "교육",
    "교육 > 학습 관련 사물": "교육",
    "자연 > 기상 및 기후": "과학",
    "자연 > 자원": "과학",
    "자연 > 재해": "과학",
    "자연 > 지형": "과학",
    "자연 > 천체": "과학",
    "동식물 > 곤충류": "과학",
    "동식물 > 동물류": "과학",
    "동식물 > 동물의 부분": "과학",
    "동식물 > 식물류": "과학",
    "동식물 > 식물의 부분": "과학",
    "정치와 행정 > 정치 및 행정 행위": "사회",
    "정치와 행정 > 정치 및 행정 주체": "사회",
    "정치와 행정 > 사법 및 치안 행위": "사회",
    "정치와 행정 > 사법 및 치안 주체": "사회",
    "정치와 행정 > 공공 기관": "사회",
    "경제 생활 > 경제 행위": "사회",
    "경제 생활 > 경제 상태": "사회",
    "경제 생활 > 경제 수단": "사회",
    "경제 생활 > 경제 행위 장소": "사회",
    "경제 생활 > 경제 행위 주체": "사회",
}

# 언어 매핑: XML val -> output key
LANG_MAP = {
    "영어": "en",
    "일본어": "ja",
    "베트남어": "vi",
    # 중국어는 krdict에 없음 -> zh는 항상 빈 문자열
}

# 지나치게 일반적이어서 제외할 단어 패턴
EXCLUDE_WORDS = {
    # 너무 일반적인 1글자/2글자
    "것", "이", "그", "저", "때", "말", "일", "안", "밖", "위", "아래",
    "앞", "뒤", "옆", "속", "데", "곳", "날", "해", "달",
    # 일반 동사/형용사 (명사형이 아닌 것)
    "하다", "되다", "있다", "없다", "보다", "가다", "오다", "나다",
    "주다", "받다", "알다", "모르다", "살다", "죽다",
}

# 포함 보장할 핵심 용어 (이 단어가 word에 정확히 일치하면 무조건 포함)
MUST_INCLUDE = {
    "지권": ["과학"], "기권": ["과학"], "수권": ["과학"],
    "생물권": ["과학"], "외권": ["과학"], "광합성": ["과학"],
    "세포": ["과학"], "유전": ["과학"], "방정식": ["수학"],
    "함수": ["수학"], "확률": ["수학"], "민주주의": ["사회"],
    "경제": ["사회"], "인권": ["사회"],
}


def fix_xml_file(filepath: str) -> str:
    """XML 파일의 잘못된 문자를 수정한 임시 파일 경로를 반환한다."""
    with open(filepath, "rb") as f:
        content = f.read()

    # val="..." 안에 이스케이프 안 된 <> 검사
    if b'val="' in content and re.search(rb'val="[^"]*<[^"]*"', content):
        content_str = content.decode("utf-8")
        # val 속성 내부의 < 를 &lt;로, > 를 &gt;로 교체
        def fix_val(m):
            inner = m.group(1)
            inner = inner.replace("<", "&lt;").replace(">", "&gt;")
            return f'val="{inner}"'

        # val="...내부에 <가 있는..." 패턴만 교체
        content_str = re.sub(
            r'val="([^"]*<[^"]*)"',
            fix_val,
            content_str,
        )
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        )
        tmp.write(content_str)
        tmp.close()
        return tmp.name

    return filepath


def parse_xml_file(filepath: str):
    """XML 파일을 iterparse로 스트리밍 파싱한다."""
    actual_path = filepath
    tmp_path = None

    try:
        # 먼저 원본으로 시도, 실패하면 fix
        try:
            for event, elem in ET.iterparse(actual_path, events=("end",)):
                if elem.tag == "LexicalEntry":
                    yield elem
                    elem.clear()
        except ET.ParseError as e:
            print(f"\n  Parse error: {e}")
            print(f"  Fixing XML and retrying...", end=" ", flush=True)
            tmp_path = fix_xml_file(actual_path)
            if tmp_path != actual_path:
                for event, elem in ET.iterparse(tmp_path, events=("end",)):
                    if elem.tag == "LexicalEntry":
                        yield elem
                        elem.clear()
                print("Fixed!", end=" ", flush=True)
            else:
                print("No fixable issues found, skipping.", end=" ", flush=True)
    finally:
        if tmp_path and tmp_path != actual_path:
            os.unlink(tmp_path)


def classify_subjects(word: str, definition: str, semantic_category: str) -> list[str]:
    """용어를 과목으로 분류한다. 빈 리스트이면 교육 관련 아님."""
    subjects = set()

    # 0) must-include 확인
    if word in MUST_INCLUDE:
        return MUST_INCLUDE[word]

    # 1) 의미 범주 기반 분류 (가장 신뢰도 높음)
    if semantic_category in SEMANTIC_TO_SUBJECT:
        subjects.add(SEMANTIC_TO_SUBJECT[semantic_category])

    # 2) word에 키워드가 포함된 경우 (2글자 이상 키워드만)
    #    이것이 가장 정확한 매칭: "광합성" 이 word에 포함 → 확실히 과학 용어
    for kw in SCIENCE_WORD_KEYWORDS:
        if len(kw) >= 2 and kw in word:
            subjects.add("과학")
            break

    for kw in MATH_WORD_KEYWORDS:
        if len(kw) >= 2 and kw in word:
            subjects.add("수학")
            break

    for kw in SOCIAL_WORD_KEYWORDS:
        if len(kw) >= 2 and kw in word:
            subjects.add("사회")
            break

    for kw in KOREAN_WORD_KEYWORDS:
        if len(kw) >= 2 and kw in word:
            subjects.add("국어")
            break

    # 3) definition 기반 매칭은 word가 3글자 이상 명사일 때만 적용
    #    (2글자 일반 단어가 definition에 "경제" "사회" 등을 언급하는 것 방지)
    if len(word) >= 3:
        for kw in SCIENCE_DEF_KEYWORDS:
            if kw in definition:
                subjects.add("과학")
                break

        for kw in MATH_DEF_KEYWORDS:
            if kw in definition:
                subjects.add("수학")
                break

        for kw in SOCIAL_DEF_KEYWORDS:
            if kw in definition:
                subjects.add("사회")
                break

        for kw in KOREAN_DEF_KEYWORDS:
            if kw in definition:
                subjects.add("국어")
                break

    # "교육" -> 더 구체적인 과목이 있으면 교육은 제외
    specific = subjects - {"교육"}
    if specific:
        subjects = specific

    return sorted(subjects) if subjects else []


def extract_translations(sense_elem) -> dict:
    """Sense 요소에서 번역 정보를 추출한다."""
    translations = {"en": "", "ja": "", "zh": "", "vi": ""}

    for equiv in sense_elem.findall("Equivalent"):
        lang = ""
        lemma = ""
        for feat in equiv.findall("feat"):
            att = feat.get("att")
            val = feat.get("val", "")
            if att == "language":
                lang = val
            elif att == "lemma":
                lemma = val

        if lang in LANG_MAP and lemma:
            key = LANG_MAP[lang]
            if not translations[key]:
                translations[key] = lemma.strip()

    return translations


def should_include_word(word: str, pos: str) -> bool:
    """기본 필터: 포함할 단어인지 판별."""
    # 제외 목록
    if word in EXCLUDE_WORDS:
        return False

    # 접미사/접사("-"로 시작) 제외
    if word.startswith("-") or word.startswith("~"):
        return False

    # 1글자는 must-include에 있는 것만
    if len(word) <= 1:
        return word in MUST_INCLUDE

    # 명사 우선 (명사가 아닌 경우 3글자 이상일 때만)
    if pos == "명사":
        return True
    elif pos in ("동사", "형용사", "부사"):
        return len(word) >= 3
    else:
        return len(word) >= 2


def extract_education_terms(data_dir: str) -> list[dict]:
    """모든 XML 파일에서 교육 용어를 추출한다."""
    terms = {}  # word -> term dict (중복 방지)
    total_entries = 0
    files_processed = 0

    xml_files = sorted(
        [f for f in os.listdir(data_dir) if f.endswith(".xml")],
        key=lambda x: int(x.replace(".xml", "")),
    )

    print(f"Processing {len(xml_files)} XML files from {data_dir}...")

    for xml_file in xml_files:
        filepath = os.path.join(data_dir, xml_file)
        file_count = 0
        file_edu = 0
        print(f"\n  Processing {xml_file}...", end=" ", flush=True)

        for entry in parse_xml_file(filepath):
            total_entries += 1
            file_count += 1

            # 기본 정보 추출
            word = ""
            pos = ""
            semantic_category = ""
            target_code = entry.get("val", "")

            for feat in entry.findall("feat"):
                att = feat.get("att")
                val = feat.get("val", "")
                if att == "partOfSpeech":
                    pos = val
                elif att == "semanticCategory":
                    semantic_category = val

            # 표제어
            lemma_elem = entry.find("Lemma")
            if lemma_elem is not None:
                for feat in lemma_elem.findall("feat"):
                    if feat.get("att") == "writtenForm":
                        word = feat.get("val", "")

            if not word:
                continue

            # 기본 단어 필터
            if not should_include_word(word, pos):
                continue

            # Sense에서 정의 및 번역 추출 (첫 번째 매칭 sense만)
            for sense in entry.findall("Sense"):
                definition = ""
                for feat in sense.findall("feat"):
                    if feat.get("att") == "definition":
                        definition = feat.get("val", "")

                if not definition:
                    continue

                # 과목 분류 (빈 리스트면 교육 관련 아님)
                subjects = classify_subjects(word, definition, semantic_category)
                if not subjects:
                    continue

                # 중복 체크: 같은 단어가 이미 있으면 과목 병합
                key = word
                if key in terms:
                    existing = terms[key]
                    merged_subjects = sorted(set(existing["subjects"] + subjects))
                    existing["subjects"] = merged_subjects
                    # 번역이 비어있으면 채움
                    translations = extract_translations(sense)
                    for lang in ["en", "ja", "vi"]:
                        if not existing[lang] and translations[lang]:
                            existing[lang] = translations[lang]
                    continue

                # 번역 추출
                translations = extract_translations(sense)

                term = {
                    "term_ko": word,
                    "definition_ko": definition,
                    "easy_ko": "",
                    "en": translations["en"],
                    "ja": translations["ja"],
                    "zh": translations["zh"],  # krdict에 없으므로 항상 빈 문자열
                    "vi": translations["vi"],
                    "tl": "",  # krdict에 필리핀어 없음
                    "subjects": subjects,
                    "source": "krdict",
                    "krdict_target_code": target_code,
                }

                terms[key] = term
                file_edu += 1

        files_processed += 1
        print(f"({file_count} entries, {file_edu} education terms found)")

    print(f"\n{'='*60}")
    print(f"Total entries scanned: {total_entries}")
    print(f"Files processed: {files_processed}/{len(xml_files)}")
    print(f"Education terms extracted: {len(terms)}")

    return sorted(terms.values(), key=lambda x: x["term_ko"])


def print_statistics(terms: list[dict]):
    """통계를 출력한다."""
    print(f"\n{'='*60}")
    print(f"EXTRACTION STATISTICS")
    print(f"{'='*60}")
    print(f"Total terms: {len(terms)}")

    # 카테고리별 분포
    print(f"\n--- Subject Distribution ---")
    subject_counts = Counter()
    for t in terms:
        for s in t["subjects"]:
            subject_counts[s] += 1
    for subject, count in subject_counts.most_common():
        print(f"  {subject}: {count}")

    # 언어별 채움률
    print(f"\n--- Translation Fill Rate ---")
    for lang in ["en", "ja", "zh", "vi"]:
        filled = sum(1 for t in terms if t[lang])
        rate = filled / len(terms) * 100 if terms else 0
        print(f"  {lang}: {filled}/{len(terms)} ({rate:.1f}%)")

    # 필수 테스트 용어 포함 여부
    print(f"\n--- Required Test Terms ---")
    required_terms = [
        "지권", "기권", "수권", "생물권", "외권", "광합성",
        "세포", "유전", "방정식", "함수", "확률",
        "민주주의", "경제", "인권",
    ]
    term_set = {t["term_ko"] for t in terms}
    for rt in required_terms:
        status = "FOUND" if rt in term_set else "MISSING"
        if status == "FOUND":
            # 해당 용어의 번역 상태도 표시
            term_data = next(t for t in terms if t["term_ko"] == rt)
            langs = []
            for lang in ["en", "ja", "vi"]:
                if term_data[lang]:
                    langs.append(f"{lang}=OK")
                else:
                    langs.append(f"{lang}=--")
            print(f"  {rt}: {status} ({', '.join(langs)})")
        else:
            print(f"  {rt}: {status}")

    found = sum(1 for rt in required_terms if rt in term_set)
    print(f"\n  Found {found}/{len(required_terms)} required terms")

    # 샘플 출력
    print(f"\n--- Sample Terms (first 10) ---")
    for t in terms[:10]:
        subj = "/".join(t["subjects"])
        print(f"  {t['term_ko']} [{subj}] en={t['en'][:30]} ja={t['ja'][:20]} vi={t['vi'][:20]}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="krdict 교육 용어 추출")
    parser.add_argument(
        "--data-dir",
        default="/tmp/krdict-data",
        help="krdict XML 데이터 디렉토리",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="출력 JSON 파일 경로",
    )
    args = parser.parse_args()

    # 기본 출력 경로
    if args.output is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output = os.path.join(script_dir, "krdict_education_terms.json")

    # 데이터 디렉토리 확인
    if not os.path.isdir(args.data_dir):
        print(f"Error: Data directory not found: {args.data_dir}")
        print("Please clone the repository first:")
        print("  git clone --depth 1 https://github.com/spellcheck-ko/korean-dict-nikl-krdict.git /tmp/krdict-data")
        sys.exit(1)

    # 추출
    terms = extract_education_terms(args.data_dir)

    # 저장
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(terms, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(terms)} terms to {args.output}")

    # 통계
    print_statistics(terms)

    return terms


if __name__ == "__main__":
    main()
