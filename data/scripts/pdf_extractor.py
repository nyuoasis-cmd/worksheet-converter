#!/usr/bin/env python3
"""
중앙다문화교육센터(edu4mc) 전자책 PDF 텍스트 추출기
"스스로 배우는 교과 속 어휘" 시리즈에서 과학 용어를 추출합니다.

사용법:
    python pdf_extractor.py <pdf_file_path>

PDF 다운로드: https://www.edu4mc.or.kr/edu/list.html
검색어: "스스로 배우는 교과 속 어휘"

의존성:
    pip install PyMuPDF  (또는 pip install pymupdf)
"""

import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF가 필요합니다.")
    print("  pip install PyMuPDF")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> list[str]:
    """PDF에서 페이지별 텍스트를 추출합니다."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        pages.append(text)
    doc.close()
    return pages


def parse_vocabulary_entries(pages: list[str]) -> list[dict]:
    """
    추출된 텍스트에서 어휘 항목을 파싱합니다.

    edu4mc 교재의 일반적 패턴:
    - 한국어 용어 (굵은 글씨)
    - 쉬운 설명
    - 다국어 번역 (베트남어, 중국어, 영어 등)
    """
    entries = []
    full_text = "\n".join(pages)

    # 패턴 1: "용어 - 설명" 형식
    pattern1 = re.compile(
        r"([가-힣]+)\s*[-:—]\s*([가-힣\s,\.]+?)(?:\n|$)"
    )

    # 패턴 2: 용어 뒤에 괄호로 외국어 병기
    pattern2 = re.compile(
        r"([가-힣]+)\s*\(([^)]+)\)"
    )

    # 패턴 3: 표 형식 (용어 | 뜻 | 번역)
    pattern3 = re.compile(
        r"([가-힣]+)\s*[|\t]\s*([^|\t\n]+)\s*[|\t]\s*([^|\t\n]+)"
    )

    # 각 패턴으로 추출 시도
    for match in pattern1.finditer(full_text):
        term = match.group(1).strip()
        explanation = match.group(2).strip()
        if len(term) >= 2 and len(explanation) >= 3:
            entries.append({
                "term_ko": term,
                "easy_ko": explanation,
                "raw_match": match.group(0).strip(),
                "pattern": "dash",
            })

    for match in pattern2.finditer(full_text):
        term = match.group(1).strip()
        foreign = match.group(2).strip()
        if len(term) >= 2:
            entries.append({
                "term_ko": term,
                "foreign_text": foreign,
                "raw_match": match.group(0).strip(),
                "pattern": "parentheses",
            })

    for match in pattern3.finditer(full_text):
        term = match.group(1).strip()
        meaning = match.group(2).strip()
        translation = match.group(3).strip()
        if len(term) >= 2:
            entries.append({
                "term_ko": term,
                "easy_ko": meaning,
                "foreign_text": translation,
                "raw_match": match.group(0).strip(),
                "pattern": "table",
            })

    return entries


def deduplicate(entries: list[dict]) -> list[dict]:
    """중복 용어 제거 (첫 번째 발견 항목 유지)."""
    seen = set()
    unique = []
    for entry in entries:
        term = entry["term_ko"]
        if term not in seen:
            seen.add(term)
            unique.append(entry)
    return unique


def to_schema(entries: list[dict]) -> list[dict]:
    """추출된 항목을 프로젝트 스키마 형식으로 변환합니다."""
    result = []
    for entry in entries:
        item = {
            "term_ko": entry["term_ko"],
            "easy_ko": entry.get("easy_ko", ""),
            "translations": {},
            "subject": "과학",
            "grade_group": "3-4",
            "source": "edu4mc",
        }
        # 외국어 텍스트가 있으면 언어 감지 시도
        foreign = entry.get("foreign_text", "")
        if foreign:
            # CJK 문자 → 중국어
            if re.search(r"[\u4e00-\u9fff]", foreign):
                item["translations"]["zh"] = foreign
            # 라틴 문자 → 영어/베트남어 구분
            elif re.search(r"[a-zA-Z]", foreign):
                # 베트남어 특수 문자 체크
                if re.search(r"[ăâđêôơưàảãáạ]", foreign, re.IGNORECASE):
                    item["translations"]["vi"] = foreign
                else:
                    item["translations"]["en"] = foreign
        result.append(item)
    return result


def main():
    if len(sys.argv) < 2:
        print("사용법: python pdf_extractor.py <pdf_file_path>")
        print()
        print("PDF 다운로드:")
        print("  https://www.edu4mc.or.kr/edu/list.html")
        print('  검색: "스스로 배우는 교과 속 어휘"')
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"ERROR: 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    output_path = Path(__file__).parent.parent / "terms" / "science_3-4_edu4mc.json"

    print(f"=== edu4mc PDF 어휘 추출기 ===")
    print(f"입력: {pdf_path}")
    print(f"출력: {output_path}")
    print()

    # 1. PDF에서 텍스트 추출
    print("1. PDF 텍스트 추출 중...")
    pages = extract_text_from_pdf(pdf_path)
    print(f"   {len(pages)}페이지 추출 완료")

    # 2. 어휘 항목 파싱
    print("2. 어휘 항목 파싱 중...")
    entries = parse_vocabulary_entries(pages)
    print(f"   {len(entries)}개 항목 발견")

    # 3. 중복 제거
    print("3. 중복 제거 중...")
    unique = deduplicate(entries)
    print(f"   {len(unique)}개 고유 항목")

    # 4. 스키마 변환 및 저장
    print("4. 스키마 변환 및 저장 중...")
    result = to_schema(unique)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n=== 완료 ===")
    print(f"추출 용어: {len(result)}개")
    print(f"저장: {output_path}")

    # 요약 출력
    print("\n--- 추출된 용어 목록 ---")
    for item in result[:20]:
        trans = item.get("translations", {})
        lang_str = ", ".join(f"{k}:{v}" for k, v in trans.items())
        print(f"  {item['term_ko']}: {item.get('easy_ko', '')} [{lang_str}]")
    if len(result) > 20:
        print(f"  ... 외 {len(result) - 20}개")


if __name__ == "__main__":
    main()
