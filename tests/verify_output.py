"""HTML 구조 검증 스크립트 — worksheet-converter 출력물 자동 검증.

tests/results/ 디렉토리의 HTML 파일을 검증한다.
검증 항목 5가지:
  1. 필수 클래스 존재 (.worksheet, .worksheet-header, .question, .question-text)
  2. 문제 번호 연속성 (data-number="1", "2", ... 빠짐 없이)
  3. 다국어 모드: 테스트 설정에 languages가 있으면 term-multilingual 존재 필수
  4. 이미지 레이블 언어 매칭 (zh→图, ja→図, vi→Hình, en→Picture, fil→Larawan)
  5. 마크다운 잔재 없음 (**bold** 패턴 미검출)

사용법:
  python3 tests/verify_output.py
  python3 tests/verify_output.py tests/results/test2_mode2_vi_zh.html
"""

import glob
import json
import os
import re
import sys

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
SUMMARY_PATH = os.path.join(RESULTS_DIR, "summary.json")

# 이미지 레이블 언어 매핑
IMAGE_LABEL_MAP = {
    "zh": "图",
    "ja": "図",
    "vi": "Hình",
    "en": "Picture",
    "fil": "Larawan",
    "ru": "Рисунок",
}

# 테스트 케이스별 언어 설정 (run_convert_test.py와 동기화)
TEST_LANGUAGES = {
    "test1_mode1_no_lang": [],
    "test2_mode2_vi_zh": ["vi", "zh"],
    "test3_mode1_vi_only": ["vi"],
}


def check_required_classes(html: str) -> tuple[bool, str]:
    """검증 1: 필수 CSS 클래스 존재 확인."""
    required = ["worksheet", "worksheet-header", "question", "question-text"]
    missing = []
    for cls in required:
        pattern = rf'class="[^"]*\b{cls}\b[^"]*"'
        if not re.search(pattern, html):
            missing.append(cls)
    if missing:
        return False, f"누락 클래스: {', '.join(missing)}"
    return True, "필수 클래스 4개 모두 존재"


def check_question_numbering(html: str) -> tuple[bool, str]:
    """검증 2: 문제 번호 연속성 확인."""
    numbers = [int(m) for m in re.findall(r'data-number="(\d+)"', html)]
    if not numbers:
        return False, "data-number 속성 없음"
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        return False, f"번호 불연속: 발견={numbers}, 기대={expected}"
    return True, f"문제 {len(numbers)}개, 번호 연속 (1~{len(numbers)})"


def check_multilingual(html: str, languages: list[str]) -> tuple[bool, str]:
    """검증 3: 다국어 모드 검증.

    언어 선택 시 두 가지 출력 패턴이 있다:
    - A) 외국어 본문 + ko-ref 한국어 참조 (완전 번역 모드)
    - B) 쉬운 한국어 본문 + term-multilingual 용어 병기 (용어 병기 모드)
    둘 중 하나 이상 존재하면 PASS.
    """
    if not languages:
        return True, "다국어 없음 (스킵)"

    has_koref = "ko-ref" in html
    has_multilingual = "term-multilingual" in html
    koref_count = len(re.findall(r'class="ko-ref"', html))
    multi_count = len(re.findall(r'class="term-multilingual"', html))

    if not has_koref and not has_multilingual:
        return False, f"languages={languages} 인데 ko-ref도 term-multilingual도 없음"

    parts = []
    if has_multilingual:
        parts.append(f"term-multilingual {multi_count}개")
    if has_koref:
        parts.append(f"ko-ref {koref_count}개")
    return True, f"{', '.join(parts)} (languages={languages})"


def check_image_labels(html: str, languages: list[str]) -> tuple[bool, str]:
    """검증 4: 이미지 힌트/이미지 영역 레이블 언어 매칭."""
    # image-hint (텍스트 설명) + image-region .image-desc (실제 이미지 삽입 후) 양쪽 검색
    image_hints = re.findall(r'class="image-hint"[^>]*>(.*?)</(?:div|p)', html, re.DOTALL)
    image_descs = re.findall(r'class="image-desc"[^>]*>(.*?)</(?:p|div)', html, re.DOTALL)
    all_labels = image_hints + image_descs
    if not all_labels:
        return True, "image-hint/image-region 없음 (스킵)"
    # 이미지 레이블이 있을 때만 언어 매칭 확인
    issues = []
    for lang in languages:
        expected_label = IMAGE_LABEL_MAP.get(lang)
        if expected_label and all_labels:
            found = any(expected_label in label for label in all_labels)
            if not found:
                issues.append(f"{lang}→'{expected_label}' 미발견")
    if issues:
        return False, f"레이블 불일치: {', '.join(issues)}"
    hint_count = len(image_hints)
    desc_count = len(image_descs)
    return True, f"이미지 레이블 {hint_count + desc_count}개 (hint={hint_count}, region={desc_count}), 정상"


def check_markdown_residue(html: str) -> tuple[bool, str]:
    """검증 5: 마크다운 잔재 없음 확인."""
    # **bold** 패턴 (HTML 태그 밖에서)
    bold_matches = re.findall(r'\*\*[^*]+\*\*', html)
    if bold_matches:
        samples = bold_matches[:3]
        return False, f"마크다운 잔재 {len(bold_matches)}개: {samples}"
    return True, "마크다운 잔재 없음"


def verify_html(filepath: str, languages: list[str] | None = None) -> list[dict]:
    """단일 HTML 파일 검증. 5개 항목 결과 리스트 반환."""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    basename = os.path.splitext(os.path.basename(filepath))[0]
    if languages is None:
        languages = TEST_LANGUAGES.get(basename, [])

    checks = [
        ("필수 클래스", check_required_classes(html)),
        ("문제 번호 연속성", check_question_numbering(html)),
        ("다국어 검증", check_multilingual(html, languages)),
        ("이미지 레이블", check_image_labels(html, languages)),
        ("마크다운 잔재", check_markdown_residue(html)),
    ]

    results = []
    for name, (passed, detail) in checks:
        results.append({"check": name, "passed": passed, "detail": detail})
    return results


def print_results(filename: str, results: list[dict]) -> bool:
    """결과 테이블 출력. 전체 PASS 여부 반환."""
    all_pass = all(r["passed"] for r in results)
    status = "PASS" if all_pass else "FAIL"

    print(f"\n{'─' * 70}")
    print(f"  {filename}  [{status}]")
    print(f"{'─' * 70}")
    print(f"  {'검증 항목':<20} {'결과':<6} {'상세'}")
    print(f"  {'─' * 64}")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['check']:<20} {mark:<6} {r['detail']}")

    return all_pass


def main():
    # 인자로 특정 파일 지정 가능
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.html")))

    if not files:
        print("검증할 HTML 파일 없음. 먼저 run_convert_test.py를 실행하세요.")
        sys.exit(1)

    total_pass = 0
    total_fail = 0

    for filepath in files:
        results = verify_html(filepath)
        passed = print_results(os.path.basename(filepath), results)
        if passed:
            total_pass += 1
        else:
            total_fail += 1

    # 최종 요약
    print(f"\n{'═' * 70}")
    total = total_pass + total_fail
    print(f"  총 {total}개 파일: PASS {total_pass} / FAIL {total_fail}")
    print(f"{'═' * 70}")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
