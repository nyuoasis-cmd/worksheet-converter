"""Gemini Vision API 호출 서비스.

이미지 → OCR + 쉬운 한국어 변환을 단일 호출로 처리한다.
"""

import base64
import re

from google import genai
from google.genai import types

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.prompts.convert_prompt import build_prompt
from backend.services.glossary_postprocess import apply_glossary_postprocess


def _get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    return genai.Client(api_key=GEMINI_API_KEY)


def convert_worksheet(
    image_bytes: bytes,
    mime_type: str,
    rag_context: str = "",
    selected_languages: str = "",
    difficulty_level: str = "쉬움",
    vocab: list[dict] = None,
    languages: list[str] = None,
) -> str:
    """문제지 이미지를 받아 쉬운 한국어 HTML로 변환한다.

    Args:
        image_bytes: 이미지 바이너리 데이터.
        mime_type: 이미지 MIME 타입 (예: "image/png").
        rag_context: RAG 조회 결과. 빈 문자열이면 모드1.
        selected_languages: 쉼표 구분 외국어 목록.
        difficulty_level: 변환 난이도.
        vocab: glossary 후처리용 어휘 리스트.
        languages: glossary 후처리용 언어 코드 리스트.

    Returns:
        변환된 HTML 문자열.
    """
    client = _get_client()

    system_prompt = build_prompt(
        rag_context=rag_context,
        selected_languages=selected_languages,
        difficulty_level=difficulty_level,
    )

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    image_part,
                    types.Part.from_text(text="이 문제지를 변환해주세요."),
                ],
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
        ),
    )

    html = response.text

    # Gemini가 markdown 코드 블록으로 감싸는 경우 제거
    html = re.sub(r"^```html\s*", "", html.strip())
    html = re.sub(r"\s*```$", "", html.strip())

    # Gemini가 HTML 안에 **bold** 마크다운을 출력하는 경우 변환
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)

    # 빈 괄호 잔재 제거: "; ( )", ": ( )" (데이터 없는 언어 슬롯)
    # 주의: 독립 "( )" 패턴은 학생 작성용 빈칸일 수 있으므로 보존
    html = re.sub(r"[;:]\s*\(\s*\)", "", html)  # "; ( )" 또는 ": ( )" 패턴만 제거

    # glossary 기반 강제 치환 (ko-ref 역참조)
    if vocab and languages:
        html = apply_glossary_postprocess(html, vocab, languages)

    return html
