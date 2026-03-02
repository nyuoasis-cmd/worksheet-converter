#!/usr/bin/env python3
"""학습지 변환 자동화 파이프라인 — 생성 ↔ 검증 루프.

verify/ 폴더의 이미지를 스캔하여:
  1. Gemini Vision으로 HTML 변환 (convert_worksheet 직접 호출)
  2. HTML 구조 검증 (verify_output.py)
  3. HTML → PNG 렌더링 (render-html-to-png.mjs)
  4. Gemini Vision 시각 검증 (verify_visual.py)

실패 시 에러 피드백을 포함하여 최대 3회 재시도.
최종 결과: verify/output/{이미지명}.html + .png + _report.json

사용법:
  cd /home/claude/worksheet-converter
  python3 scripts/auto_pipeline.py                     # verify/ 내 모든 이미지 처리
  python3 scripts/auto_pipeline.py "중학교 과학.png"    # 특정 파일만 처리
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERIFY_DIR = PROJECT_ROOT / "verify"
OUTPUT_DIR = VERIFY_DIR / "output"
TESTS_DIR = PROJECT_ROOT / "tests"

# sys.path에 프로젝트 루트 추가 (backend 임포트용)
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import GEMINI_API_KEY
from backend.services.gemini_service import convert_worksheet
from backend.services.rag_service import build_rag_context, search_vocab
from tests.verify_output import verify_html as structural_verify
from tests.verify_visual import verify_visual

# 지원 이미지 확장자
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# 최대 재시도 횟수
MAX_RETRIES = 3


def scan_images(target_file: str | None = None) -> list[Path]:
    """verify/ 폴더에서 이미지 파일을 스캔."""
    if not VERIFY_DIR.exists():
        print(f"verify/ 폴더 없음: {VERIFY_DIR}")
        return []

    images = []
    for f in sorted(VERIFY_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            if target_file and f.name != target_file:
                continue
            images.append(f)

    return images


def load_metadata(image_path: Path) -> dict:
    """사이드카 .json 메타데이터 로드. 없으면 기본값 반환."""
    json_path = image_path.with_suffix(".json")
    defaults = {
        "languages": "zh",
        "difficulty": "쉬움",
        "subject": "",
        "grade_group": "",
    }

    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                overrides = json.load(f)
            defaults.update(overrides)
            print(f"  메타데이터 로드: {json_path.name}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  메타데이터 파싱 실패 ({json_path.name}): {e}")

    return defaults


def step1_convert(image_path: Path, metadata: dict, error_feedback: str = "") -> str:
    """Step 1: 이미지 → HTML 변환."""
    print(f"\n  [Step 1] 변환 중...")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = image_path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/png")

    # RAG 컨텍스트 구축
    languages = metadata.get("languages", "")
    lang_list = [l.strip() for l in languages.split(",") if l.strip()] if languages else None
    rag_context = build_rag_context(
        subject=metadata.get("subject") or None,
        grade_group=metadata.get("grade_group") or None,
        languages=lang_list,
    )

    # 에러 피드백이 있으면 RAG 컨텍스트에 추가
    if error_feedback:
        feedback_section = f"\n\n### 이전 변환의 문제점 (반드시 수정하세요)\n{error_feedback}\n"
        rag_context = feedback_section + rag_context

    # glossary 후처리용 어휘 데이터 조회
    vocab_items = search_vocab(
        subject=metadata.get("subject") or None,
        grade_group=metadata.get("grade_group") or None,
        languages=lang_list,
    ) if lang_list else []

    html = convert_worksheet(
        image_bytes=image_bytes,
        mime_type=mime_type,
        rag_context=rag_context,
        selected_languages=languages,
        difficulty_level=metadata.get("difficulty", "쉬움"),
        vocab=vocab_items,
        languages=lang_list or [],
    )

    print(f"    HTML 생성 완료 ({len(html)} 바이트)")
    return html


def step2_structural_verify(html_path: Path, languages: list[str]) -> tuple[bool, list[dict]]:
    """Step 2: HTML 구조 검증."""
    print(f"  [Step 2] 구조 검증 중...")

    results = structural_verify(str(html_path), languages=languages)
    all_pass = all(r["passed"] for r in results)

    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"    {r['check']:<20} {mark:<6} {r['detail']}")

    return all_pass, results


def step3_render_png(html_path: Path) -> Path | None:
    """Step 3: HTML → PNG 렌더링."""
    print(f"  [Step 3] PNG 렌더링 중...")

    render_script = TESTS_DIR / "render-html-to-png.mjs"
    if not render_script.exists():
        print(f"    렌더링 스크립트 없음: {render_script}")
        return None

    try:
        result = subprocess.run(
            ["node", str(render_script), str(html_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            print(f"    렌더링 실패: {result.stderr}")
            return None

        png_path = html_path.with_suffix(".png")
        if png_path.exists():
            print(f"    PNG 생성 완료: {png_path.name}")
            return png_path

        print(f"    PNG 파일 미생성: {png_path.name}")
        return None
    except subprocess.TimeoutExpired:
        print(f"    렌더링 타임아웃 (30초)")
        return None


def step4_visual_verify(original_path: Path, output_png: Path) -> tuple[bool, dict]:
    """Step 4: Gemini Vision 시각 검증."""
    print(f"  [Step 4] 시각 검증 중...")

    try:
        result = verify_visual(str(original_path), str(output_png))
        overall = result.get("overall", "error")
        checks = result.get("checks", [])

        for check in checks:
            name = check.get("name", "?")
            passed = check.get("pass", False)
            detail = check.get("detail", "")
            mark = "PASS" if passed else "FAIL"
            print(f"    {name:<20} {mark:<6} {detail}")

        if result.get("summary"):
            print(f"    요약: {result['summary']}")

        return overall == "pass", result
    except Exception as e:
        print(f"    시각 검증 오류: {e}")
        return False, {"checks": [], "overall": "error", "summary": str(e)}


def build_error_feedback(structural_results: list[dict], visual_result: dict) -> str:
    """실패한 검증 항목을 에러 피드백 문자열로 조합."""
    lines = []

    # 구조 검증 실패 항목
    for r in structural_results:
        if not r["passed"]:
            lines.append(f"- [구조] {r['check']}: {r['detail']}")

    # 시각 검증 실패 항목
    for check in visual_result.get("checks", []):
        if not check.get("pass", False):
            lines.append(f"- [시각] {check['name']}: {check.get('detail', '')}")

    return "\n".join(lines) if lines else ""


def process_image(image_path: Path) -> dict:
    """단일 이미지 파일에 대해 전체 파이프라인 실행."""
    stem = image_path.stem
    print(f"\n{'═' * 70}")
    print(f"  처리 중: {image_path.name}")
    print(f"{'═' * 70}")

    # 출력 디렉토리 보장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata = load_metadata(image_path)
    languages_str = metadata.get("languages", "")
    lang_list = [l.strip() for l in languages_str.split(",") if l.strip()] if languages_str else []

    report = {
        "image": image_path.name,
        "metadata": metadata,
        "attempts": [],
        "final_status": "pending",
        "output_html": None,
        "output_png": None,
    }

    error_feedback = ""
    best_result = None  # 최선의 결과를 추적

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n  ── 시도 {attempt}/{MAX_RETRIES} ──")
        attempt_log = {"attempt": attempt, "structural": None, "visual": None}

        # Step 1: 변환
        try:
            html = step1_convert(image_path, metadata, error_feedback)
        except Exception as e:
            print(f"    변환 오류: {e}")
            attempt_log["error"] = str(e)
            report["attempts"].append(attempt_log)
            continue

        # HTML 저장
        html_path = OUTPUT_DIR / f"{stem}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        report["output_html"] = str(html_path)

        # Step 2: 구조 검증
        struct_pass, struct_results = step2_structural_verify(html_path, lang_list)
        attempt_log["structural"] = {
            "passed": struct_pass,
            "checks": struct_results,
        }

        # Step 3: PNG 렌더링
        png_path = step3_render_png(html_path)
        if not png_path:
            attempt_log["visual"] = {"passed": False, "error": "PNG 렌더링 실패"}
            report["attempts"].append(attempt_log)
            error_feedback = build_error_feedback(struct_results, {})
            if not struct_pass:
                error_feedback += "\n- [렌더링] PNG 렌더링 실패"
            continue

        report["output_png"] = str(png_path)

        # Step 4: 시각 검증
        visual_pass, visual_result = step4_visual_verify(image_path, png_path)
        attempt_log["visual"] = {
            "passed": visual_pass,
            "result": visual_result,
        }

        report["attempts"].append(attempt_log)
        best_result = attempt_log

        if struct_pass and visual_pass:
            report["final_status"] = "pass"
            print(f"\n  ✓ 전체 PASS (시도 {attempt})")
            break

        # 에러 피드백 구축 (다음 시도용)
        error_feedback = build_error_feedback(struct_results, visual_result)
        if attempt < MAX_RETRIES:
            print(f"\n  재시도 예정... 에러 피드백 {len(error_feedback)} 바이트")

    else:
        # MAX_RETRIES 소진
        report["final_status"] = "best_effort"
        print(f"\n  ⚠ {MAX_RETRIES}회 시도 완료. 최선 결과 유지.")

    # 리포트 저장
    report_path = OUTPUT_DIR / f"{stem}_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  리포트: {report_path.name}")

    return report


def main():
    """메인 실행."""
    print("=" * 70)
    print("  학습지 변환 자동화 파이프라인")
    print("=" * 70)

    if not GEMINI_API_KEY:
        print("\nGEMINI_API_KEY 환경변수를 설정하세요.")
        sys.exit(1)

    # 특정 파일 지정 가능
    target = sys.argv[1] if len(sys.argv) > 1 else None

    images = scan_images(target)
    if not images:
        msg = f"처리할 이미지 없음"
        if target:
            msg += f" (대상: {target})"
        else:
            msg += f" (경로: {VERIFY_DIR})"
        print(f"\n{msg}")
        sys.exit(1)

    print(f"\n대상 이미지: {len(images)}개")
    for img in images:
        print(f"  - {img.name}")

    # 각 이미지 처리
    results = []
    for img in images:
        report = process_image(img)
        results.append(report)

    # 최종 요약
    print(f"\n{'═' * 70}")
    print(f"  최종 요약")
    print(f"{'═' * 70}")

    pass_count = sum(1 for r in results if r["final_status"] == "pass")
    best_count = sum(1 for r in results if r["final_status"] == "best_effort")
    fail_count = len(results) - pass_count - best_count

    for r in results:
        status = r["final_status"].upper()
        attempts = len(r["attempts"])
        print(f"  {r['image']:<40} {status:<12} ({attempts}회 시도)")

    print(f"\n  PASS: {pass_count} / BEST_EFFORT: {best_count} / FAIL: {fail_count}")
    print(f"  결과 경로: {OUTPUT_DIR}/")
    print(f"{'═' * 70}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
