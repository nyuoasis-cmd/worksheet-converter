"""이미지 바운딩 박스 추출 + base64 삽입 서비스.

Gemini가 출력한 data-bbox 좌표로 원본 이미지에서 그림 영역을 크롭하여
HTML에 실제 이미지(base64 JPEG)로 삽입한다.
"""

import base64
import io
import re

from PIL import Image

MAX_WIDTH_PX = 800
MAX_FALLBACK_WIDTH_PX = 320  # bbox 없는 fallback 이미지: 최대 320px
JPEG_QUALITY = 80
BBOX_COORD_MAX = 1000
MIN_CROP_PX = 20

# image-hint with optional data-bbox, capturing bbox value and inner content
_HINT_RE = re.compile(
    r'<div\s+class="image-hint"(?:\s+data-bbox="([^"]*)")?\s*>(.*?)</div>',
    re.DOTALL,
)


def _parse_bbox(
    bbox_str: str, img_w: int, img_h: int
) -> tuple[int, int, int, int] | None:
    """'y1,x1,y2,x2' 정규화 좌표 → Pillow (left, upper, right, lower) 픽셀 좌표.

    Returns None if invalid.
    """
    parts = bbox_str.split(",")
    if len(parts) != 4:
        return None
    try:
        y1, x1, y2, x2 = (int(p.strip()) for p in parts)
    except ValueError:
        return None

    # 범위 검증 (0~1000)
    if not all(0 <= v <= BBOX_COORD_MAX for v in (y1, x1, y2, x2)):
        return None
    if y1 >= y2 or x1 >= x2:
        return None

    # 정규화 좌표 → 픽셀
    left = int(x1 * img_w / BBOX_COORD_MAX)
    upper = int(y1 * img_h / BBOX_COORD_MAX)
    right = int(x2 * img_w / BBOX_COORD_MAX)
    lower = int(y2 * img_h / BBOX_COORD_MAX)

    # 최소 크롭 크기
    if (right - left) < MIN_CROP_PX or (lower - upper) < MIN_CROP_PX:
        return None

    return (left, upper, right, lower)


def _encode_image(image: Image.Image) -> str:
    """PIL Image → max 800px 리사이즈 → JPEG base64 문자열."""
    # 리사이즈 (가로 MAX_WIDTH_PX 초과 시)
    if image.width > MAX_WIDTH_PX:
        ratio = MAX_WIDTH_PX / image.width
        new_h = int(image.height * ratio)
        image = image.resize((MAX_WIDTH_PX, new_h), Image.LANCZOS)

    # RGBA → RGB (JPEG은 알파 불가)
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _crop_and_encode(image: Image.Image, bbox: tuple[int, int, int, int]) -> str | None:
    """크롭 → base64 JPEG. 실패 시 None."""
    try:
        cropped = image.crop(bbox)
        return _encode_image(cropped)
    except Exception:
        return None


def _make_full_image_base64(image: Image.Image) -> str:
    """원본 전체 이미지 → base64 JPEG (fallback용, MAX_FALLBACK_WIDTH_PX 제한)."""
    if image.width > MAX_FALLBACK_WIDTH_PX:
        ratio = MAX_FALLBACK_WIDTH_PX / image.width
        new_h = int(image.height * ratio)
        image = image.resize((MAX_FALLBACK_WIDTH_PX, new_h), Image.LANCZOS)
    return _encode_image(image)


def extract_and_embed_images(html: str, image_bytes: bytes) -> str:
    """HTML 내 image-hint를 실제 이미지(base64)로 교체한다.

    Args:
        html: Gemini가 생성한 HTML (data-bbox 속성 포함 가능).
        image_bytes: 원본 학습지 이미지 바이너리.

    Returns:
        이미지가 삽입된 HTML. 실패 시 원본 HTML 그대로.
    """
    # 빠른 탈출: image-hint 없으면 처리 불필요
    if 'class="image-hint"' not in html:
        return html

    # 원본 이미지 열기
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return html  # 이미지 열기 실패 → 텍스트 설명 유지

    img_w, img_h = image.size
    full_b64 = None  # lazy: 필요할 때만 생성

    def _replace_hint(match: re.Match) -> str:
        nonlocal full_b64
        bbox_str = match.group(1)  # None if no data-bbox
        inner = match.group(2).strip()

        b64 = None

        # bbox 크롭 시도
        if bbox_str:
            bbox = _parse_bbox(bbox_str, img_w, img_h)
            if bbox:
                b64 = _crop_and_encode(image, bbox)

        # fallback: 원본 전체 이미지
        if b64 is None:
            if full_b64 is None:
                full_b64 = _make_full_image_base64(image)
            b64 = full_b64

        # alt 텍스트용 설명 추출 (이모지 접두사·ko-ref 제거)
        desc_text = re.sub(r"^🖼\s*", "", inner)
        desc_text = re.sub(r'<span class="ko-ref">.*?</span>', "", desc_text, flags=re.DOTALL).strip()

        return (
            f'<div class="image-region">'
            f'\n    <img src="data:image/jpeg;base64,{b64}" alt="{_escape_attr(desc_text)}">'
            f"\n  </div>"
        )

    return _HINT_RE.sub(_replace_hint, html)


def _escape_attr(text: str) -> str:
    """HTML attribute 값 이스케이프."""
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
