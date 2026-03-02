#!/usr/bin/env python3
"""
편수자료(교과서 편수자료) PDF에서 교과 용어표를 추출하는 파서.

pyeonsu_3.pdf: 수학, 물리, 화학, 생명과학, 지구과학, 정보
pyeonsu_2.pdf: 지리, 한국사, 세계사, 일반사회, 체육, 음악, 미술
(학교문법은 영어 대역이 없으므로 제외)

pdftotext -layout 출력물을 파싱하여 용어-영어 쌍을 추출한다.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ─── 설정 ────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "pdf"
OUT_FILE = BASE_DIR / "pyeonsu_terms.json"

# 과목 매핑 (subjects 필드에 들어갈 값)
SUBJECT_MAP = {
    "수학": "수학",
    "물리": "과학-물리",
    "화학": "과학-화학",
    "생명과학": "과학-생명과학",
    "지구과학": "과학-지구과학",
    "정보": "정보",
    "지리": "사회-지리",
    "한국사": "사회-한국사",
    "세계사": "사회-세계사",
    "일반사회": "사회-일반사회",
    "체육": "체육",
    "음악서양": "음악",
    "음악국악": "음악-국악",
    "미술": "미술",
}

# 기대 용어 수 (참고용, 검증에 사용)
EXPECTED_COUNTS = {
    "수학": 1440, "물리": 2524, "화학": 1869,
    "생명과학": 2674, "지구과학": 2785, "정보": 1617,
    "지리": 1348, "한국사": 1200, "세계사": 544,
    "일반사회": 1133, "체육": 2134, "음악서양": 3397,
    "미술": 2097,
}


@dataclass
class Term:
    term_ko: str
    en: str
    hanja: str = ""
    note: str = ""
    subject: str = ""

    def to_output(self):
        return {
            "term_ko": self.term_ko,
            "definition_ko": "",
            "easy_ko": "",
            "en": self.en,
            "ja": "",
            "zh": "",
            "vi": "",
            "tl": "",
            "subjects": [SUBJECT_MAP.get(self.subject, self.subject)],
            "source": "pyeonsu",
            "krdict_target_code": "",
        }


# ─── 텍스트 추출 ──────────────────────────────────────────────────────────

def extract_text(pdf_path: Path) -> str:
    """pdftotext -layout 으로 텍스트 추출"""
    txt_path = pdf_path.with_suffix(".txt")
    if not txt_path.exists():
        subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
            check=True,
        )
    return txt_path.read_text(encoding="utf-8")


# ─── 섹션 분할 ──────────────────────────────────────────────────────────

def find_roman_section_pages(lines: list[str]) -> dict[str, int]:
    """독립된 로마자 줄 + 다음줄 과목명으로 섹션 타이틀 페이지 찾기.

    예:
      "     I"        → 다음줄 "수학과"
      "     XI"       → 다음줄 "미술"
    """
    result = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i < 100:  # 발간사/차례 건너뛰기
            continue
        # 로마자 독립 줄: I, II, III, IV, V, VI, VII, VIII, IX, X, XI
        if re.match(r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3}|XII{0,3})$', stripped):
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                result[next_stripped] = i
    return result


def find_term_start(lines: list[str], from_line: int, patterns: list[str],
                    occurrence: int = 2) -> Optional[int]:
    """from_line 이후에서 특정 패턴(예: '2. 용어')을 찾아 라인 번호 반환.

    occurrence=2: 두 번째 출현 반환 (첫 번째는 섹션 타이틀 페이지의 TOC).
    섹션 타이틀 페이지에는 "1. 기본방향..." / "2. 용어" / "3. ..." 이 TOC로 나열되고,
    실제 용어 목록은 그 뒤에 다시 "2. 용어" 가 나온다.
    """
    count = 0
    for i in range(from_line, min(from_line + 500, len(lines))):
        stripped = lines[i].strip()
        for pat in patterns:
            if re.match(pat, stripped):
                count += 1
                if count >= occurrence:
                    return i
    return None


def find_section_end(lines: list[str], from_line: int, end_patterns: list[str],
                     max_line: int = None) -> int:
    """from_line 이후에서 종료 패턴을 찾아 라인 번호 반환.

    from_line 이후 10줄 이내에 나오는 패턴은 무시 (TOC 잔재).
    """
    limit = max_line or len(lines)
    for i in range(from_line + 10, limit):  # +10: skip nearby TOC residues
        stripped = lines[i].strip()
        for pat in end_patterns:
            if re.match(pat, stripped):
                return i
    return limit


def find_section_ranges_p3(lines: list[str]) -> dict[str, tuple[int, int]]:
    """pyeonsu_3.txt에서 과목별 용어 섹션 라인 범위 찾기"""
    sections = {}
    roman_pages = find_roman_section_pages(lines)
    print(f"  Roman numeral pages found: {roman_pages}")

    # 과목별 정의: (subject_key, section_title, term_start_patterns, end_patterns)
    subject_defs = [
        ("수학", "수학과",
         [r'^2\.\s*용어\s*$'],
         [r'^(I{1,3}|IV|V|VI{0,3}|IX|X)$']),  # 다음 섹션 로마자
        ("물리", "물리학",
         [r'^2\.\s*용어\s*$'],
         [r'^3\.\s*국제단위계']),
        ("화학", "화학",
         [r'^2\.\s*용어\s*$'],
         [r'^3\.\s*화학\s*실험']),
        ("생명과학", "생명과학",
         [r'^2\.\s*용어\s*$'],
         [r'^3\.\s*동물계와']),
        ("지구과학", "지구과학",
         [r'^2\.\s*용어\s*$'],
         [r'^3\.\s*지질시대']),
        ("정보", "정보과",
         [r'^2\.\s*용어\s*$'],
         []),  # 마지막 섹션
    ]

    for subject, title, start_pats, end_pats in subject_defs:
        page_line = roman_pages.get(title)
        if page_line is None:
            print(f"  [WARN] Section title page not found for '{title}'")
            continue

        term_start = find_term_start(lines, page_line, start_pats)
        if term_start is None:
            print(f"  [WARN] Term start not found for {subject}")
            continue

        if end_pats:
            term_end = find_section_end(lines, term_start, end_pats)
        else:
            term_end = len(lines)

        sections[subject] = (term_start, term_end)
        print(f"  [{subject}] lines {term_start}–{term_end} ({term_end - term_start} lines)")

    return sections


def find_section_ranges_p2(lines: list[str]) -> dict[str, tuple[int, int]]:
    """pyeonsu_2.txt에서 과목별 용어 섹션 라인 범위 찾기"""
    sections = {}
    roman_pages = find_roman_section_pages(lines)
    print(f"  Roman numeral pages found: {roman_pages}")

    subject_defs = [
        ("지리", "지리",
         [r'^2\.\s*용어\s*$'],
         [r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3})$']),
        ("한국사", "한국사",
         [r'^2\.\s*용어\s*$'],
         [r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3})$']),
        ("세계사", "세계사",
         [r'^2\.\s*용어\s*$'],
         [r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3})$']),
        ("일반사회", "일반 사회",
         [r'^2\.\s*용어\s*$'],
         [r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,3})$']),
        ("체육", "체육",
         [r'^2\.\s*신체활동'],
         [r'^3\.\s*인명']),
        ("음악서양", "음악",
         [r'^2\.\s*음악\s*일반'],
         [r'^3\.\s*국악']),
        ("미술", "미술",
         [r'^2\.\s*일반\s*용어'],
         [r'^3\.\s*한국\s*전통']),
    ]

    for subject, title, start_pats, end_pats in subject_defs:
        page_line = roman_pages.get(title)
        if page_line is None:
            print(f"  [WARN] Section title page not found for '{title}'")
            continue

        term_start = find_term_start(lines, page_line, start_pats)
        if term_start is None:
            print(f"  [WARN] Term start not found for {subject}")
            continue

        if end_pats:
            term_end = find_section_end(lines, term_start, end_pats)
        else:
            term_end = len(lines)

        sections[subject] = (term_start, term_end)
        print(f"  [{subject}] lines {term_start}–{term_end} ({term_end - term_start} lines)")

    return sections


# ─── 노이즈 필터 ──────────────────────────────────────────────────────────

# 영어 판별: 영문 2글자 이상
EN_PATTERN = re.compile(r'[A-Za-z]{2,}')

# 페이지 번호 패턴
PAGE_NUM_PATTERN = re.compile(r'^\s*\d{1,4}\s*$')

# 페이지 헤더/풋터 패턴
PAGE_HEADER_PATTERNS = [
    re.compile(r'[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫXxIiVv]+\.\s*(수학과|물리학|화학|생명과학|지구과학|정보과)'),
    re.compile(r'[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫXxIiVv]+\.\s*(지리|한국사|세계사|일반\s*사회|체육|음악|미술)'),
    re.compile(r'2022\s*개정\s*교육과정'),
    re.compile(r'편수자료'),
]

# 테이블 헤더 패턴
TABLE_HEADER_PATTERNS = [
    re.compile(r'^\s*용어\s{2,}(동의어|한자)\s{2,}(외국어|외국어\s+)'),
    re.compile(r'^\s*용어\s{2,}한자\s+(외국어|외국어\s+)'),
    re.compile(r'^\s*용어\s{2,}한자\s+외국어\s+(비고|동의어)'),
]


def is_noise_line(line: str) -> bool:
    """페이지 번호, 헤더, 빈 줄 등 노이즈 줄 판별"""
    stripped = line.strip()
    if not stripped:
        return True
    if PAGE_NUM_PATTERN.match(stripped):
        return True
    for pat in PAGE_HEADER_PATTERNS:
        if pat.search(stripped):
            return True
    for pat in TABLE_HEADER_PATTERNS:
        if pat.match(stripped):
            return True
    # Form feed character
    if stripped == '\x0c' or (len(stripped) < 3 and '\x0c' in stripped):
        return True
    return False


def clean_english(en: str) -> str:
    """영어 필드 정리"""
    en = en.strip()
    en = en.rstrip(",").strip()
    en = re.sub(r'\s+', ' ', en)
    # form feed 제거
    en = en.replace('\x0c', '')
    return en


def clean_korean(ko: str) -> str:
    """한국어 용어 정리"""
    ko = ko.strip()
    ko = re.sub(r'\s+', ' ', ko)
    ko = ko.replace('\x0c', '')
    return ko


# ─── 용어 파싱 ──────────────────────────────────────────────────────────

def parse_math_section(lines: list[str], start: int, end: int) -> list[Term]:
    """수학: 3열 — 용어 / 동의어 / 외국어 (한자 없음)

    수학의 경우 한자 열이 없고, 용어 / 동의어 / 외국어 3열 구조.
    동의어도 한글이므로 영어 부분은 큰 공백(2+) 뒤의 영문 부분으로 판별.

    특수 케이스: p값 → p-value, t분포 → t-distribution 등
    영문 1글자 + 한글 형태의 용어 처리.
    """
    terms = []
    pending_ko = None
    pending_en_parts = []

    for i in range(start, end):
        line = lines[i]
        if is_noise_line(line):
            if pending_ko and pending_en_parts:
                en = clean_english(" ".join(pending_en_parts))
                if en and EN_PATTERN.search(en):
                    terms.append(Term(term_ko=clean_korean(pending_ko), en=en, subject="수학"))
                pending_ko = None
                pending_en_parts = []
            continue

        # 영어 부분 찾기: 한글 뒤 큰 공백(2+) 다음의 영문
        # 특수: p값, t분포 등 "영문1글자+한글" 용어는 한글 취급
        # 전략: 큰 공백(2+) 뒤의 영문 시작점을 찾는다
        en_match = re.search(r'(?<=[가-힣\s])\s{2,}([A-Za-z])', line)
        if not en_match:
            # 동의어 열 뒤의 영어 패턴도 시도
            en_match = re.search(r'\s{2,}([A-Za-z][A-Za-z\-])', line)

        if en_match:
            en_start_pos = en_match.start(1)
            ko_part = line[:en_match.start()].strip()
            en_part = line[en_start_pos:].strip()

            # 한글 부분에서 용어 추출 (큰 공백으로 분리)
            ko_tokens = re.split(r'\s{2,}', ko_part)
            ko_tokens = [t.strip() for t in ko_tokens if t.strip()]

            if ko_tokens and re.search(r'[가-힣]', ko_tokens[0]):
                main_term = ko_tokens[0]
                # Flush previous
                if pending_ko and pending_en_parts:
                    en = clean_english(" ".join(pending_en_parts))
                    if en and EN_PATTERN.search(en):
                        terms.append(Term(term_ko=clean_korean(pending_ko), en=en, subject="수학"))

                pending_ko = main_term
                pending_en_parts = [en_part]
            elif pending_ko:
                # 영어만 있는 줄 -> continuation
                pending_en_parts.append(en_part)
        else:
            # 영어 없는 줄 — 한글만 있는 새 용어 or continuation
            stripped = line.strip()
            if re.search(r'[가-힣]', stripped):
                # Flush previous
                if pending_ko and pending_en_parts:
                    en = clean_english(" ".join(pending_en_parts))
                    if en and EN_PATTERN.search(en):
                        terms.append(Term(term_ko=clean_korean(pending_ko), en=en, subject="수학"))
                    pending_ko = None
                    pending_en_parts = []

    # Final flush
    if pending_ko and pending_en_parts:
        en = clean_english(" ".join(pending_en_parts))
        if en and EN_PATTERN.search(en):
            terms.append(Term(term_ko=clean_korean(pending_ko), en=en, subject="수학"))

    return terms


def parse_standard_section(lines: list[str], start: int, end: int, subject: str) -> list[Term]:
    """표준 4열 파싱: 용어 / 한자 / 외국어 / 비고

    물리, 화학, 생명과학, 지구과학, 정보, 지리, 한국사, 세계사,
    일반사회, 체육, 음악, 미술 공통.

    핵심 로직:
    1. 줄 맨 앞에 한글이 있고 + 영어가 있으면 → 새 용어
    2. 줄 맨 앞에 한글이 있고 + 영어가 없으면 → 영어 없는 새 용어 (flush previous)
    3. 줄 앞부분이 공백이고 영어가 있으면 → 이전 용어의 영어 continuation
    4. 비고/동의어는 영어 뒤 큰 공백 이후의 한글 부분
    """
    terms = []
    pending_ko = None
    pending_hanja = ""
    pending_en_parts = []
    pending_note = ""

    def flush():
        nonlocal pending_ko, pending_hanja, pending_en_parts, pending_note
        if pending_ko and pending_en_parts:
            en = clean_english(" ".join(pending_en_parts))
            if en and EN_PATTERN.search(en):
                terms.append(Term(
                    term_ko=clean_korean(pending_ko),
                    en=en,
                    hanja=pending_hanja,
                    note=pending_note,
                    subject=subject,
                ))
        pending_ko = None
        pending_hanja = ""
        pending_en_parts = []
        pending_note = ""

    for i in range(start, end):
        line = lines[i]
        if is_noise_line(line):
            flush()
            continue

        stripped = line.strip()
        if not stripped:
            flush()
            continue

        leading_spaces = len(line) - len(line.lstrip())

        # 영어 있는지 확인
        en_match = re.search(r'[A-Za-z][A-Za-z]', line)

        # 줄 맨 앞에 한글 용어가 있는지 확인
        # 한글 용어: 한글로 시작, 공백/특수문자 포함 가능
        ko_at_start = re.match(
            r'^(\s{0,6})([가-힣][가-힣\s·‧ㆍ/()（）0-9\-～~ㅡ━,*]*)',
            line
        )

        if ko_at_start and en_match:
            ko_raw = ko_at_start.group(2).strip()
            ko_end_pos = ko_at_start.end()
            en_start_pos = en_match.start()

            if not re.search(r'[가-힣]', ko_raw):
                # 한글이 아닌 경우 스킵
                if pending_ko:
                    pending_en_parts.append(stripped)
                continue

            # 한자 추출: 한글 끝~영어 시작 사이
            between = line[ko_end_pos:en_start_pos]
            hanja_matches = re.findall(r'[\u4E00-\u9FFF\u3400-\u4DBF——()（）·‧\s]+', between)
            hanja = "".join(hanja_matches).strip() if hanja_matches else ""
            # 한자에서 공백/기호 정리
            hanja = re.sub(r'\s+', '', hanja)

            # 영어 부분
            en_part = line[en_start_pos:].strip()

            # 비고 분리: 영어 뒤 큰 공백(3+) + 한글
            note = ""
            note_split = re.split(r'\s{3,}', en_part)
            if len(note_split) > 1:
                en_clean_parts = [note_split[0]]
                for p in note_split[1:]:
                    if re.search(r'[가-힣]', p):
                        note = p.strip()
                    else:
                        en_clean_parts.append(p)
                en_part = " ".join(en_clean_parts)

            # Flush previous & start new
            flush()
            pending_ko = ko_raw
            pending_hanja = hanja
            pending_en_parts = [en_part] if en_part else []
            pending_note = note

        elif ko_at_start and not en_match and leading_spaces < 7:
            ko_raw = ko_at_start.group(2).strip()
            if re.search(r'[가-힣]', ko_raw):
                # 영어 없는 새 용어 → flush previous
                flush()

                # 한자 확인
                rest = line[ko_at_start.end():]
                hanja_matches = re.findall(r'[\u4E00-\u9FFF\u3400-\u4DBF——()（）·‧\s]+', rest)
                hanja = "".join(hanja_matches).strip() if hanja_matches else ""
                hanja = re.sub(r'\s+', '', hanja)

                # 비고 확인 (한자 뒤 한글)
                note = ""
                note_match = re.search(r'[\u4E00-\u9FFF\u3400-\u4DBF——()（）·‧\s]+\s+(.*)', rest)
                if note_match:
                    note_text = note_match.group(1).strip()
                    if re.search(r'[가-힣]', note_text):
                        note = note_text

                pending_ko = ko_raw
                pending_hanja = hanja
                pending_en_parts = []
                pending_note = note

        elif en_match and leading_spaces >= 5:
            # 영어 continuation 줄 (들여쓰기됨)
            if pending_ko:
                en_part = stripped
                # 비고 분리
                note_split = re.split(r'\s{3,}', en_part)
                if len(note_split) > 1 and re.search(r'[가-힣]', note_split[-1]):
                    pending_en_parts.append(note_split[0])
                    if not pending_note:
                        pending_note = note_split[-1].strip()
                else:
                    pending_en_parts.append(en_part)

    # Final flush
    flush()
    return terms


# ─── 후처리 ──────────────────────────────────────────────────────────────

def clean_term(t: Term) -> Optional[Term]:
    """용어 정리 및 필터링"""
    t.term_ko = clean_korean(t.term_ko)
    t.en = clean_english(t.en)

    # 한국어 용어 유효성 검사
    if len(t.term_ko) < 1:
        return None
    if not re.search(r'[가-힣]', t.term_ko):
        return None

    # 용어에서 trailing *, / 제거
    t.term_ko = t.term_ko.rstrip("*/ ").strip()
    # 용어에서 ㅡ, ━ 대시 마커 제거
    t.term_ko = re.sub(r'\s*[ㅡ━]\s*$', '', t.term_ko)
    t.term_ko = re.sub(r'^[ㅡ━]\s*', '', t.term_ko)
    # 용어에서 leading/trailing 특수문자 정리
    t.term_ko = t.term_ko.strip("/ ,;-ㅡ━")

    if not t.term_ko or not re.search(r'[가-힣]', t.term_ko):
        return None

    # 영어 유효성: 최소 2글자 영어 단어
    if not EN_PATTERN.search(t.en):
        return None

    # 영어에서 leading ——(em-dash, 한자 bleed) 제거
    t.en = re.sub(r'^[——━ㅡ\-]+\s*', '', t.en)

    # 영어에서 잔여 한자 제거
    t.en = re.sub(r'[\u4E00-\u9FFF\u3400-\u4DBF]+', '', t.en).strip()

    # 영어에서 잔여 한글 분리 (비고 미분리 케이스)
    # 단, 외래어 표기 주석 (프), (독), (이), (네) 등은 보존
    parts = re.split(r'\s{2,}', t.en)
    en_parts = []
    for p in parts:
        # 한글이 있으면서 외래어 주석이 아닌 경우 비고로 분리
        if re.search(r'[가-힣]', p) and en_parts:
            # "(프)", "(독)", "(이)", "(네)", "(영)" 등 외래어 표기 주석은 보존
            if not re.match(r'^.*\((프|독|이|네|영|라|에|일|러|아|포)\).*$', p):
                if not t.note:
                    t.note = p.strip()
                break
        en_parts.append(p)
    t.en = clean_english(" ".join(en_parts))

    # 한자 필드 정리
    t.hanja = re.sub(r'\s+', '', t.hanja)
    t.hanja = t.hanja.replace('——', '').replace('━', '').replace('ㅡ', '')
    t.hanja = re.sub(r'^[——━ㅡ\-]+$', '', t.hanja)

    # 영어 정리
    t.en = re.sub(r'\s+', ' ', t.en).strip()
    t.en = t.en.strip("/ ,;-ㅡ━——")

    # 한글 단독 외래어 주석만 남은 경우 제거: "(프)" 만 남은 것
    if re.match(r'^\((프|독|이|네|영|라|에|일|러|아|포)\)$', t.en):
        return None

    # "-" 만 있는 경우 제거 (정보과에서 동의어 없음 표시)
    if t.en in ("-", "—", "ㅡ", "━"):
        return None

    if not t.en or not EN_PATTERN.search(t.en):
        return None

    return t


def deduplicate(terms: list[Term]) -> list[Term]:
    """중복 제거 (동일 term_ko + en + subject)"""
    seen = set()
    result = []
    for t in terms:
        key = (t.term_ko, t.en, t.subject)
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


# ─── 메인 ────────────────────────────────────────────────────────────────

def main():
    all_terms: list[Term] = []
    stats = {"raw_lines": {}, "parsed": {}, "filtered": {}}

    # ── pyeonsu_3.pdf ────────────────────────────────────────────────
    print("=" * 70)
    print("Processing pyeonsu_3.pdf (기초과학/정보)")
    print("=" * 70)

    p3_path = PDF_DIR / "pyeonsu_3.pdf"
    text3 = extract_text(p3_path)
    lines3 = text3.split("\n")
    print(f"Total lines: {len(lines3)}")

    sections3 = find_section_ranges_p3(lines3)

    for subject, (start, end) in sections3.items():
        stats["raw_lines"][subject] = end - start
        if subject == "수학":
            terms = parse_math_section(lines3, start, end)
        else:
            terms = parse_standard_section(lines3, start, end, subject)

        stats["parsed"][subject] = len(terms)

        cleaned = [ct for t in terms if (ct := clean_term(t)) is not None]
        stats["filtered"][subject] = len(cleaned)

        expected = EXPECTED_COUNTS.get(subject, "?")
        pct = f"{len(cleaned)/expected*100:.0f}%" if isinstance(expected, int) else "?"
        print(f"  {subject}: {len(terms)} parsed → {len(cleaned)} final "
              f"(expected ~{expected}, {pct})")
        all_terms.extend(cleaned)

    # ── pyeonsu_2.pdf ────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("Processing pyeonsu_2.pdf (인문사회/체육/음악/미술)")
    print("=" * 70)

    p2_path = PDF_DIR / "pyeonsu_2.pdf"
    text2 = extract_text(p2_path)
    lines2 = text2.split("\n")
    print(f"Total lines: {len(lines2)}")

    sections2 = find_section_ranges_p2(lines2)

    for subject, (start, end) in sections2.items():
        stats["raw_lines"][subject] = end - start
        terms = parse_standard_section(lines2, start, end, subject)

        stats["parsed"][subject] = len(terms)

        cleaned = [ct for t in terms if (ct := clean_term(t)) is not None]
        stats["filtered"][subject] = len(cleaned)

        expected = EXPECTED_COUNTS.get(subject, "?")
        # 한국사, 일반사회 등은 영어 비율 낮으므로 추출률 별도 표시
        pct = f"{len(cleaned)/expected*100:.0f}%" if isinstance(expected, int) else "?"
        print(f"  {subject}: {len(terms)} parsed → {len(cleaned)} final "
              f"(expected ~{expected}, {pct})")
        all_terms.extend(cleaned)

    # ── 후처리 ────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("Post-processing")
    print("=" * 70)

    all_terms = deduplicate(all_terms)
    print(f"After dedup: {len(all_terms)} terms")

    # 정렬: subject → term_ko
    all_terms.sort(key=lambda t: (t.subject, t.term_ko))

    # JSON 출력
    output = [t.to_output() for t in all_terms]
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUT_FILE}")

    # ── 통계 ─────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"{'과목':<15} {'원본줄':>8} {'파싱':>8} {'최종':>8} {'기대':>8} {'추출률':>8}")
    print("-" * 70)
    total_raw = 0
    total_parsed = 0
    total_final = 0

    for subj in sorted(stats["filtered"].keys()):
        raw = stats["raw_lines"].get(subj, 0)
        parsed = stats["parsed"].get(subj, 0)
        final = stats["filtered"].get(subj, 0)
        expected = EXPECTED_COUNTS.get(subj, 0)
        total_raw += raw
        total_parsed += parsed
        total_final += final
        pct = f"{final/expected*100:.0f}%" if expected else "N/A"
        print(f"{subj:<15} {raw:>8} {parsed:>8} {final:>8} {expected:>8} {pct:>8}")

    print("-" * 70)
    print(f"{'합계':<15} {total_raw:>8} {total_parsed:>8} {total_final:>8}")
    print()
    print(f"Total unique terms with English: {len(all_terms)}")
    print()

    # 영어가 없어서 제외된 과목 별도 표시
    print("NOTE: 한국사, 일반사회 등은 대부분의 용어에 영어가 없어 추출률이 낮습니다.")
    print("      이들 과목의 기대 수는 전체 용어 수이며, 영어가 있는 용어만 추출합니다.")


if __name__ == "__main__":
    main()
