"""테스트용 초등 과학 문제지 이미지 3장을 생성한다."""

import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_worksheets")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 시스템 한글 폰트 찾기
FONT_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
font_path = None
for p in FONT_PATHS:
    if os.path.exists(p):
        font_path = p
        break


def get_font(size: int):
    if font_path:
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def draw_text_wrapped(draw, text, x, y, max_width, font, fill="black", line_spacing=8):
    """줄바꿈을 처리하며 텍스트를 그린다."""
    lines = text.split("\n")
    current_y = y
    for line in lines:
        words = list(line)
        current_line = ""
        for char in words:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > max_width and current_line:
                draw.text((x, current_y), current_line, font=font, fill=fill)
                bbox2 = draw.textbbox((0, 0), current_line, font=font)
                current_y += (bbox2[3] - bbox2[1]) + line_spacing
                current_line = char
            else:
                current_line = test_line
        if current_line:
            draw.text((x, current_y), current_line, font=font, fill=fill)
            bbox2 = draw.textbbox((0, 0), current_line, font=font)
            current_y += (bbox2[3] - bbox2[1]) + line_spacing
    return current_y


# === 시험지 1: 3학년 과학 - 물질의 성질 ===
def create_test1():
    img = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(img)

    title_font = get_font(28)
    body_font = get_font(18)
    small_font = get_font(16)

    # 헤더
    draw.text((250, 30), "3학년 1학기 과학", font=title_font, fill="black")
    draw.text((270, 70), "1단원. 물질의 성질", font=title_font, fill="black")
    draw.line([(50, 110), (750, 110)], fill="black", width=2)

    y = 130
    questions = [
        (
            "1. 물체와 물질의 차이점을 바르게 설명한 것은?",
            [
                "① 물체는 재료이고, 물질은 물건이다.",
                "② 물체는 물건이고, 물질은 그 물건을 만드는 재료이다.",
                "③ 물체와 물질은 같은 뜻이다.",
                "④ 물질은 눈에 보이지 않는다.",
            ],
        ),
        (
            "2. 다음 중 물질의 단단한 정도를 비교하는 방법으로 알맞은 것은?",
            [
                "① 물질을 물에 넣어 본다.",
                "② 물질을 서로 긁어 본다.",
                "③ 물질의 무게를 재 본다.",
                "④ 물질의 색깔을 비교한다.",
            ],
        ),
        (
            "3. 물에 뜨는 물질로만 짝지어진 것은?",
            [
                "① 나무, 쇠못",
                "② 나무, 스티로폼",
                "③ 쇠못, 유리구슬",
                "④ 스티로폼, 동전",
            ],
        ),
        (
            "4. 우산을 만들 때 알맞은 재료의 성질은?",
            [
                "① 물이 잘 스며드는 재료",
                "② 물이 스며들지 않는 재료",
                "③ 아주 단단한 재료",
                "④ 아주 가벼운 재료",
            ],
        ),
        (
            "5. 같은 물질로 만든 물체를 모두 고르시오.",
            [
                "① 유리컵, 유리창",
                "② 나무 의자, 쇠 숟가락",
                "③ 고무장갑, 종이컵",
                "④ 플라스틱 자, 유리컵",
            ],
        ),
    ]

    for q_text, choices in questions:
        y = draw_text_wrapped(draw, q_text, 60, y, 680, body_font)
        y += 5
        for choice in choices:
            y = draw_text_wrapped(draw, choice, 80, y, 660, small_font)
        y += 15

    path = os.path.join(OUTPUT_DIR, "test1_science_3_1_materials.png")
    img.save(path)
    print(f"Created: {path}")
    return path


# === 시험지 2: 4학년 과학 - 식물의 한살이 ===
def create_test2():
    img = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(img)

    title_font = get_font(28)
    body_font = get_font(18)
    small_font = get_font(16)

    draw.text((250, 30), "4학년 1학기 과학", font=title_font, fill="black")
    draw.text((250, 70), "2단원. 식물의 한살이", font=title_font, fill="black")
    draw.line([(50, 110), (750, 110)], fill="black", width=2)

    y = 130
    questions = [
        (
            "1. 씨가 싹트는 것을 무엇이라고 합니까?",
            [
                "① 발아",
                "② 광합성",
                "③ 증산 작용",
                "④ 수분",
            ],
        ),
        (
            "2. 씨가 싹트는 데 반드시 필요한 조건으로 알맞은 것은?",
            [
                "① 빛과 흙",
                "② 물과 알맞은 온도",
                "③ 바람과 비료",
                "④ 흙과 비료",
            ],
        ),
        (
            "3. 식물의 한살이 순서로 알맞은 것은?",
            [
                "① 씨 → 꽃 → 싹 → 열매",
                "② 씨 → 싹 → 꽃 → 열매",
                "③ 꽃 → 씨 → 열매 → 싹",
                "④ 열매 → 꽃 → 싹 → 씨",
            ],
        ),
        (
            "4. 꽃이 진 후에 생기는 것은 무엇입니까?",
            [
                "① 잎",
                "② 줄기",
                "③ 뿌리",
                "④ 열매",
            ],
        ),
        (
            "5. 강낭콩의 싹이 자라는 과정에서 가장 먼저 나오는 부분은?",
            [
                "① 잎",
                "② 뿌리",
                "③ 꽃",
                "④ 줄기",
            ],
        ),
    ]

    for q_text, choices in questions:
        y = draw_text_wrapped(draw, q_text, 60, y, 680, body_font)
        y += 5
        for choice in choices:
            y = draw_text_wrapped(draw, choice, 80, y, 660, small_font)
        y += 15

    path = os.path.join(OUTPUT_DIR, "test2_science_4_1_plants.png")
    img.save(path)
    print(f"Created: {path}")
    return path


# === 시험지 3: 3학년 과학 - 자석의 이용 ===
def create_test3():
    img = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(img)

    title_font = get_font(28)
    body_font = get_font(18)
    small_font = get_font(16)

    draw.text((250, 30), "3학년 1학기 과학", font=title_font, fill="black")
    draw.text((260, 70), "3단원. 자석의 이용", font=title_font, fill="black")
    draw.line([(50, 110), (750, 110)], fill="black", width=2)

    y = 130
    questions = [
        (
            "1. 자석에 붙는 물체로만 짝지어진 것은?",
            [
                "① 클립, 쇠못",
                "② 나무젓가락, 지우개",
                "③ 클립, 유리컵",
                "④ 지우개, 쇠못",
            ],
        ),
        (
            "2. 자석의 같은 극끼리 가까이 하면 어떻게 됩니까?",
            [
                "① 서로 끌어당긴다.",
                "② 서로 밀어낸다.",
                "③ 아무 일도 일어나지 않는다.",
                "④ 자석이 부러진다.",
            ],
        ),
        (
            "3. 나침반의 바늘이 가리키는 방향은?",
            [
                "① 동쪽과 서쪽",
                "② 남쪽과 북쪽",
                "③ 위쪽과 아래쪽",
                "④ 오른쪽과 왼쪽",
            ],
        ),
        (
            "4. 다음 중 자석을 이용한 것이 아닌 것은?",
            [
                "① 냉장고 문",
                "② 필통 뚜껑",
                "③ 나무 의자",
                "④ 자석 칠판",
            ],
        ),
        (
            "5. 자석의 N극과 S극에 대한 설명으로 틀린 것은?",
            [
                "① 자석에는 N극과 S극이 있다.",
                "② N극과 S극은 서로 끌어당긴다.",
                "③ 같은 극끼리는 끌어당긴다.",
                "④ 자석을 반으로 나누면 새로운 N극과 S극이 생긴다.",
            ],
        ),
    ]

    for q_text, choices in questions:
        y = draw_text_wrapped(draw, q_text, 60, y, 680, body_font)
        y += 5
        for choice in choices:
            y = draw_text_wrapped(draw, choice, 80, y, 660, small_font)
        y += 15

    path = os.path.join(OUTPUT_DIR, "test3_science_3_1_magnets.png")
    img.save(path)
    print(f"Created: {path}")
    return path


if __name__ == "__main__":
    create_test1()
    create_test2()
    create_test3()
    print("All test images created.")
