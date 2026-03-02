"""번역 서비스 — Korean HTML → 다국어 HTML + ko-ref.

Gemini가 생성한 쉬운 한국어 HTML을 Google Cloud Translation API로
텍스트만 번역하고, 한국어 원문을 ko-ref 스팬으로 보존한다.

파이프라인:
1. BeautifulSoup으로 번역 대상 요소 추출
2. explanation 스팬 제거 (번역 불필요한 한국어 보조 설명)
3. Google Translate v2 API 배치 호출 (format=html, 태그 보존)
4. 번역된 텍스트 + ko-ref(한국어 원문) 주입
"""

import json
import logging
import os
import re
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── 설정 ───
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
BATCH_SIZE = 128  # Google Translate 최대 문자열 수/요청

# 내부 언어 코드 → Google Translate 코드
LANG_MAP = {
    "vi": "vi",
    "zh": "zh-CN",
    "ja": "ja",
    "en": "en",
    "tl": "tl",
    "ru": "ru",
}

# 번역 대상 CSS 선택자 (순서 유지: 부모→자식 문제 방지)
TRANSLATABLE_SELECTORS = [
    ".worksheet-header h1",
    ".worksheet-header .grade",
    ".question-type-label",
    ".question-text",
    ".choice",
    ".image-hint",  # image_service에서 교체되지 않은 잔여 hint
]

# 한국어 감지
_KOREAN_RE = re.compile(r"[\uAC00-\uD7A3]")

# explanation 스팬 제거 (번역 전 전처리)
_EXPLANATION_RE = re.compile(r'<span\s+class="explanation">[^<]*</span>')


def translate_html(
    korean_html: str,
    target_langs: list[str],
) -> str:
    """Korean HTML을 대상 언어로 번역하고 ko-ref를 추가한다.

    Args:
        korean_html: Gemini가 생성한 쉬운 한국어 HTML.
        target_langs: 대상 언어 코드 리스트 (예: ["vi", "zh"]).

    Returns:
        번역된 HTML (ko-ref 스팬 포함). 실패 시 원본 한국어 HTML.
    """
    if not target_langs:
        return korean_html

    api_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")
    if not api_key:
        logger.warning("GOOGLE_TRANSLATE_API_KEY 미설정 — 번역 건너뜀")
        return korean_html

    soup = BeautifulSoup(korean_html, "html.parser")

    # 1. 번역 대상 요소 수집 (중복 제거)
    elements = []
    seen_ids = set()
    for selector in TRANSLATABLE_SELECTORS:
        for elem in soup.select(selector):
            elem_id = id(elem)
            if elem_id not in seen_ids:
                seen_ids.add(elem_id)
                elements.append(elem)

    if not elements:
        return korean_html

    # 2. 각 요소의 innerHTML 추출 + explanation 제거
    items = []  # (element, clean_html_for_translation, original_inner_html)
    for elem in elements:
        original = elem.decode_contents()
        clean = _EXPLANATION_RE.sub("", original).strip()
        # 한국어가 없는 요소 건너뛰기 (숫자/기호만)
        if not _KOREAN_RE.search(clean):
            continue
        items.append((elem, clean, original.strip()))

    if not items:
        return korean_html

    texts_for_translation = [item[1] for item in items]

    # 3. 언어별 배치 번역
    translations_by_lang = {}
    for lang in target_langs:
        google_lang = LANG_MAP.get(lang, lang)
        translated = _batch_translate(texts_for_translation, "ko", google_lang, api_key)
        translations_by_lang[lang] = translated

    # 4. 요소 내용 교체: 번역문 + ko-ref
    for i, (elem, _, ko_original) in enumerate(items):
        _replace_element(soup, elem, target_langs, translations_by_lang, i, ko_original)

    # 5. img alt 속성 번역 (첫 번째 언어)
    _translate_img_alts(soup, target_langs[0], api_key)

    return str(soup)


def _replace_element(
    soup: BeautifulSoup,
    elem,
    target_langs: list[str],
    translations_by_lang: dict,
    index: int,
    ko_original: str,
):
    """요소 내용을 번역문 + ko-ref로 교체."""
    elem.clear()

    for j, lang in enumerate(target_langs):
        if j > 0:
            elem.append(soup.new_tag("br"))
        translated_html = translations_by_lang[lang][index]
        # Google Translate가 반환한 HTML 파싱 후 삽입
        frag = BeautifulSoup(translated_html, "html.parser")
        for node in list(frag.children):
            elem.append(node.extract())

    # ko-ref 스팬: 한국어 원문 보존
    ko_ref = soup.new_tag("span")
    ko_ref["class"] = ["ko-ref"]
    ko_frag = BeautifulSoup(ko_original, "html.parser")
    for node in list(ko_frag.children):
        ko_ref.append(node.extract())
    elem.append(ko_ref)


def _translate_img_alts(soup: BeautifulSoup, lang: str, api_key: str):
    """img 태그의 alt 속성을 번역한다 (접근성)."""
    google_lang = LANG_MAP.get(lang, lang)
    alt_texts = []
    alt_imgs = []

    for img in soup.find_all("img", alt=True):
        alt = img.get("alt", "")
        if alt and _KOREAN_RE.search(alt):
            alt_texts.append(alt)
            alt_imgs.append(img)

    if not alt_texts:
        return

    translated_alts = _batch_translate(alt_texts, "ko", google_lang, api_key)
    for img, new_alt in zip(alt_imgs, translated_alts):
        img["alt"] = unescape(new_alt)  # HTML entities 디코딩


def _batch_translate(
    texts: list[str],
    source: str,
    target: str,
    api_key: str,
) -> list[str]:
    """Google Cloud Translation v2 API 배치 번역.

    Args:
        texts: 번역할 텍스트/HTML 리스트.
        source: 소스 언어 코드.
        target: 대상 언어 코드.
        api_key: Google API 키.

    Returns:
        번역된 텍스트 리스트. API 오류 시 원본 텍스트 반환 (fallback).
    """
    if not texts:
        return []

    results = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        body = json.dumps({
            "q": batch,
            "source": source,
            "target": target,
            "format": "html",
        }).encode("utf-8")

        req = Request(
            f"{TRANSLATE_URL}?key={api_key}",
            data=body,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for t in data["data"]["translations"]:
                results.append(t["translatedText"])
        except (URLError, KeyError, json.JSONDecodeError, TimeoutError) as e:
            logger.error("Google Translate API 오류: %s", e)
            results.extend(batch)

    return results
