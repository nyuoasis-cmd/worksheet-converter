"""API 라우트 — /api/convert 엔드포인트 1개로 모든 변환 처리.

파이프라인:
  1. Gemini 1회 → 쉬운 한국어 HTML (구조 확정)
  2. 언어 선택 시 → Google Translate로 텍스트만 번역 + ko-ref 주입
"""

import io

import requests as req_lib
from flask import Blueprint, request, jsonify

from backend.config import MAX_IMAGE_SIZE_MB, ALLOWED_EXTENSIONS
from backend.services.gemini_service import convert_worksheet
from backend.services.rag_service import build_rag_context
from backend.services.translation_service import translate_html

convert_bp = Blueprint("convert", __name__)


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@convert_bp.route("/api/convert", methods=["POST"])
def convert():
    """문제지 이미지를 쉬운 한국어 HTML로 변환한다.

    파이프라인:
        이미지 → Gemini(1회, 한국어) → [Google Translate(텍스트만)] → HTML

    요청:
        - image: 문제지 이미지 파일 (multipart/form-data)
        - languages: 다국어 코드 (쉼표 구분, 옵션)
        - difficulty: 변환 난이도 (옵션, 기본 "쉬움")
        - subject: 과목 힌트 (옵션, RAG 검색용)
        - grade_group: 학년군 힌트 (옵션, RAG 검색용)

    응답:
        {
            "html": "<div class='worksheet'>...</div>",
            "mode": "rag" | "prompt_only"
        }
    """
    # 이미지 검증
    if "image" not in request.files:
        return jsonify({"error": "이미지 파일이 필요합니다."}), 400

    file = request.files["image"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({"error": f"허용된 이미지 형식: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    image_bytes = file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        return jsonify({"error": f"이미지 크기는 {MAX_IMAGE_SIZE_MB}MB 이하여야 합니다."}), 400

    # MIME 타입 결정
    ext = file.filename.rsplit(".", 1)[1].lower()
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "bmp": "image/bmp",
    }
    mime_type = mime_map.get(ext, "image/png")

    # 옵션 파싱
    languages_str = request.form.get("languages", "")
    difficulty = request.form.get("difficulty", "쉬움")
    subject = request.form.get("subject", None)
    grade_group = request.form.get("grade_group", None)

    # 언어가 선택된 경우 과목/학년 필수
    if languages_str and (not subject or not grade_group):
        return jsonify({
            "error": "다국어 변환 시 과목과 학년을 선택해주세요.",
            "code": "MISSING_SUBJECT_GRADE"
        }), 400

    languages = [l.strip() for l in languages_str.split(",") if l.strip()] if languages_str else []

    # RAG 조회 (한국어 전용 — 언어 번역은 포함하지 않음)
    rag_context = build_rag_context(
        subject=subject,
        grade_group=grade_group,
        languages=None,  # Gemini는 한국어만 생성하므로 번역 불필요
    )

    mode = "rag" if rag_context else "prompt_only"

    # Step 1: Gemini → 쉬운 한국어 HTML (구조 1회 확정)
    try:
        html = convert_worksheet(
            image_bytes=image_bytes,
            mime_type=mime_type,
            rag_context=rag_context,
            difficulty_level=difficulty,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"변환 중 오류가 발생했습니다: {str(e)}"}), 500

    # Step 2: 언어 선택 시 → Google Translate로 텍스트만 번역
    if languages:
        try:
            html = translate_html(html, languages)
        except Exception as e:
            # 번역 실패 시 한국어 HTML 그대로 반환 (구조는 이미 확정)
            import logging
            logging.getLogger(__name__).error("번역 실패, 한국어 HTML 반환: %s", e)

    return jsonify({"html": html, "mode": mode})


@convert_bp.route("/api/convert/pdf", methods=["POST"])
def convert_pdf():
    """HTML을 PDF로 변환한다.

    요청:
        - html: 변환할 HTML 문자열 (JSON body)

    응답:
        PDF 파일 (application/pdf)
    """
    data = request.get_json()
    if not data or "html" not in data:
        return jsonify({"error": "HTML 데이터가 필요합니다."}), 400

    try:
        from weasyprint import HTML as WeasyprintHTML

        pdf_bytes = WeasyprintHTML(
            string=_wrap_html_for_pdf(data["html"]),
            url_fetcher=_weasyprint_url_fetcher,
        ).write_pdf()
        return (
            pdf_bytes,
            200,
            {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=worksheet.pdf",
            },
        )
    except ImportError:
        return jsonify({"error": "PDF 변환 라이브러리(weasyprint)가 설치되지 않았습니다."}), 500
    except Exception as e:
        return jsonify({"error": f"PDF 변환 중 오류: {str(e)}"}), 500


@convert_bp.route("/api/convert/hwpx", methods=["POST"])
def convert_hwpx():
    """HTML을 HWPX로 변환한다. (추후 구현)"""
    return jsonify({"error": "HWPX 변환은 아직 구현되지 않았습니다."}), 501


def _weasyprint_url_fetcher(url: str, timeout: int = 15) -> dict:
    """WeasyPrint용 URL fetcher — Google Fonts에 브라우저 User-Agent를 사용."""
    headers = {}
    if "fonts.googleapis.com" in url or "fonts.gstatic.com" in url:
        headers["User-Agent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    try:
        resp = req_lib.get(url, headers=headers, timeout=timeout)
        mime_type = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
        return {"string": resp.content, "mime_type": mime_type, "encoding": resp.apparent_encoding}
    except Exception:
        from weasyprint.urls import default_url_fetcher
        return default_url_fetcher(url)


def _wrap_html_for_pdf(body_html: str) -> str:
    """HTML 본문을 PDF용 전체 문서로 감싼다."""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&family=Noto+Sans+JP:wght@400;700" rel="stylesheet">
<style>
  @font-face {{
    font-family: 'Noto Sans KR';
    src: local('Noto Sans CJK KR'), local('NotoSansCJKkr-Regular'), local('NotoSansKR-Regular');
  }}
  @font-face {{
    font-family: 'Noto Sans JP';
    src: local('Noto Sans CJK JP'), local('NotoSansCJKjp-Regular'), local('NotoSansJP-Regular');
  }}
  body {{ font-family: 'Noto Sans JP', 'Noto Sans KR', 'Noto Sans CJK JP', 'Noto Sans CJK KR', 'UnDotum', sans-serif; margin: 20mm; font-size: 14px; line-height: 1.6; }}
  .worksheet-header {{ page-break-after: avoid; margin-bottom: 16px; }}
  .worksheet-header + * {{ page-break-before: avoid; }}
  .worksheet-header h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .worksheet-header .grade {{ color: #666; margin-bottom: 0; }}
  .question-type-label {{ font-size: 13px; font-weight: 700; color: #1E40AF; background: #EFF6FF; border-left: 3px solid #3B82F6; padding: 5px 12px; margin: 16px 0 8px; border-radius: 0 4px 4px 0; }}
  .question {{ margin-bottom: 18px; page-break-inside: avoid; }}
  .image-hint {{ font-size: 12px; color: #7C3AED; background: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 6px; padding: 6px 12px; margin-bottom: 8px; }}
  .image-region {{ margin-bottom: 12px; text-align: center; }}
  .image-region img {{ max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #DDD6FE; }}
  .image-region .image-desc {{ font-size: 12px; color: #7C3AED; margin-top: 4px; font-style: italic; }}
  .image-region .ko-ref {{ display: block; font-size: 11px; color: #94A3B8; margin-top: 1px; }}
  .ws-two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; margin: 12px 0; }}
  .ws-col-img {{ text-align: center; }}
  .ws-col-img img {{ max-width: 100%; border-radius: 4px; }}
  .ws-grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 12px 0; }}
  .ws-grid-item {{ border: 1px solid #E0E0E0; border-radius: 8px; padding: 12px; }}
  .ws-blank {{ display: inline-block; width: 60px; height: 24px; border-bottom: 2px solid #333; margin: 0 4px; vertical-align: middle; }}
  .question-text {{ margin-bottom: 8px; }}
  .choices {{ margin-left: 20px; }}
  .choice {{ margin-bottom: 4px; }}
  .explanation {{ color: #2563eb; }}
  .term-multilingual {{ color: #7c3aed; font-weight: 500; }}
  .ko-ref {{ display: block; font-size: 11px; color: #94A3B8; margin-top: 1px; }}
  .question-type-label .ko-ref {{ display: inline; margin-left: 6px; font-weight: 400; }}
  .image-hint .ko-ref {{ display: inline; margin-left: 4px; }}
</style>
</head>
<body>{body_html}</body>
</html>"""
