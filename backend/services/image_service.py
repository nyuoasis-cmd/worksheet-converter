"""이미지 바운딩 박스 추출 + base64 삽입 + 그리드 감지 서비스.

Gemini가 출력한 data-bbox 좌표로 원본 이미지에서 그림 영역을 크롭하여
HTML에 실제 이미지(base64 JPEG)로 삽입한다.
또한 bbox 좌표를 분석하여 같은 행 이미지를 flex 컨테이너로 자동 래핑한다.
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
_Y_OVERLAP_THRESHOLD = 0.3  # Y좌표 겹침 30% 이상 → 같은 행
_MIN_HEIGHT_FALLBACK = 50   # 높이가 0일 때 fallback 값
_MAX_DISPLAY_COLS = 3       # flex 행당 최대 열 수 (flex-wrap으로 자동 줄바꿈)

# HTML 태그 매칭 (between-text에서 태그 제거용)
_TAG_RE = re.compile(r"<[^>]+>")

# 그리드 래퍼 opening tag (expand용)
_GRID_WRAPPER_OPEN_RE = re.compile(
    r'<div\s+class="ws-grid[^"]*"[^>]*>\s*$'
)

# image-hint with optional data-bbox, capturing bbox value and inner content
_HINT_RE = re.compile(
    r'<div\s+class="image-hint"(?:\s+data-bbox="([^"]*)")?\s*>(.*?)</div>',
    re.DOTALL,
)

# image-hint WITH data-bbox (그리드 감지용, bbox 필수)
_BBOX_HINT_RE = re.compile(
    r'<div\s+class="image-hint"\s+data-bbox="([^"]+)"\s*>.*?</div>',
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


# ──────────────────────────────────────────────────────────
# bbox 기반 이미지 그리드 감지
# ──────────────────────────────────────────────────────────

def _parse_bbox_normalized(bbox_str: str) -> tuple[int, int, int, int] | None:
    """'y1,x1,y2,x2' 정규화 좌표(0~1000) 파싱. 실패 시 None."""
    parts = bbox_str.split(",")
    if len(parts) != 4:
        return None
    try:
        y1, x1, y2, x2 = (int(p.strip()) for p in parts)
    except ValueError:
        return None
    if not all(0 <= v <= BBOX_COORD_MAX for v in (y1, x1, y2, x2)):
        return None
    if y1 >= y2 or x1 >= x2:
        return None
    return (y1, x1, y2, x2)


def _find_consecutive_runs(html: str, items: list[dict]) -> list[list[dict]]:
    """HTML에서 연속된 image-hint 그룹을 찾는다.

    image-hint 사이에 div 래퍼 태그만 있으면 (텍스트 콘텐츠 없음) 연속으로 간주.
    Gemini가 ws-grid-item 등으로 감싸는 경우에도 정상 그룹핑.
    """
    if not items:
        return []
    runs: list[list[dict]] = []
    current_run = [items[0]]
    for i in range(1, len(items)):
        between = html[items[i - 1]["end"]:items[i]["start"]]
        # Strip all HTML tags — if only whitespace remains, treat as consecutive
        text_only = _TAG_RE.sub("", between).strip()
        if text_only == "":
            current_run.append(items[i])
        else:
            runs.append(current_run)
            current_run = [items[i]]
    runs.append(current_run)
    return runs


def _group_by_y_overlap(items: list[dict]) -> list[list[dict]]:
    """Y좌표 겹침 기준으로 같은 행에 있는 이미지를 그룹핑한다."""
    if not items:
        return []
    sorted_items = sorted(items, key=lambda x: x["y1"])
    rows: list[list[dict]] = []
    current_row = [sorted_items[0]]
    for i in range(1, len(sorted_items)):
        ref = current_row[0]
        curr = sorted_items[i]
        ref_h = ref["y2"] - ref["y1"]
        curr_h = curr["y2"] - curr["y1"]
        min_h = min(ref_h, curr_h) if min(ref_h, curr_h) > 0 else _MIN_HEIGHT_FALLBACK
        overlap_top = max(ref["y1"], curr["y1"])
        overlap_bottom = min(ref["y2"], curr["y2"])
        overlap = max(0, overlap_bottom - overlap_top)
        if overlap / min_h >= _Y_OVERLAP_THRESHOLD:
            current_row.append(curr)
        else:
            rows.append(current_row)
            current_row = [curr]
    rows.append(current_row)
    return rows


def _expand_to_wrappers(html: str, start: int, end: int) -> tuple[int, int]:
    """run range를 확장하여 주변 그리드 래퍼 div 태그를 포함시킨다.

    Gemini가 image-hint를 ws-grid-2, ws-grid-item 등으로 감싸는 경우,
    교체 범위를 래퍼 태그까지 넓혀서 고아 태그를 방지한다.
    """
    open_count = 0

    # 뒤로 확장: 래퍼 opening tag 소비
    while True:
        prefix = html[:start].rstrip()
        m = _GRID_WRAPPER_OPEN_RE.search(prefix)
        if m:
            start = m.start()
            open_count += 1
        else:
            break

    # 앞으로 확장: 소비한 opening tag 수만큼 closing </div> 소비
    for _ in range(open_count):
        suffix = html[end:]
        m = re.match(r"\s*</div>", suffix)
        if m:
            end += m.end()
        else:
            break

    return start, end


def detect_image_grid(html: str) -> str:
    """data-bbox 좌표를 분석하여 같은 행 이미지를 flex 컨테이너로 감싼다.

    파이프라인: Gemini HTML → **detect_image_grid** → extract_and_embed_images
    extract_and_embed_images의 regex는 내부 image-hint div만 매칭하므로
    이 함수가 삽입한 부모 flex 컨테이너는 보존된다.

    Returns:
        그리드 래핑이 적용된 HTML. 변경 불필요 시 원본 그대로.
    """
    matches = list(_BBOX_HINT_RE.finditer(html))
    if len(matches) < 2:
        return html

    # bbox 파싱
    items: list[dict] = []
    for m in matches:
        bbox = _parse_bbox_normalized(m.group(1))
        if bbox:
            items.append({
                "y1": bbox[0], "x1": bbox[1],
                "y2": bbox[2], "x2": bbox[3],
                "start": m.start(), "end": m.end(),
            })
    if len(items) < 2:
        return html

    # 연속 런 → Y-overlap 그룹핑 → flex 래핑
    runs = _find_consecutive_runs(html, items)
    replacements: list[tuple[int, int, str]] = []  # (start, end, new_html)

    for run in runs:
        if len(run) < 2:
            continue
        rows = _group_by_y_overlap(run)
        has_grid = any(len(row) >= 2 for row in rows)
        if not has_grid:
            continue

        run_start = run[0]["start"]
        run_end = run[-1]["end"]

        # 래퍼 div 확장 (ws-grid-2, ws-grid-item 등 포함)
        run_start, run_end = _expand_to_wrappers(html, run_start, run_end)

        parts: list[str] = []

        for row in rows:
            row.sort(key=lambda item: item["x1"])
            if len(row) >= 2:
                cols = min(len(row), _MAX_DISPLAY_COLS)
                w = f"{100 / cols:.1f}"
                parts.append(
                    '<div class="ws-img-row" style="display:flex;flex-wrap:wrap;'
                    'gap:8px;justify-content:center;margin:12px 0;">\n'
                )
                for item in row:
                    parts.append(
                        f'  <div class="ws-img-cell" style="flex:0 0 calc({w}% - 8px);'
                        f'max-width:calc({w}% - 8px);text-align:center;">\n'
                        f'    {html[item["start"]:item["end"]]}\n'
                        f'  </div>\n'
                    )
                parts.append('</div>\n')
            else:
                parts.append(html[row[0]["start"]:row[0]["end"]] + "\n")

        replacements.append((run_start, run_end, "".join(parts)))

    if not replacements:
        return html

    # 뒤에서부터 교체 (위치 보존)
    for start, end, new_html in reversed(replacements):
        html = html[:start] + new_html + html[end:]

    return html
