#!/usr/bin/env python3
"""
krdict (국립국어원 한국어기초사전) Open API 크롤러
교과 용어를 크롤링하여 다문화 학습지 변환기 어휘 DB를 구축합니다.

API: https://krdict.korean.go.kr/api/search
라이선스: CC BY-SA 2.0 KR
"""

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def load_dotenv(env_path: Path):
    """간단한 .env 로더. KEY=VALUE 형식만 지원."""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip("'\"")
            os.environ.setdefault(key.strip(), value)


# .env 로드 (프로젝트 루트)
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── 설정 ───
API_KEY = "11F88D4CFF040DCC5823C8583129F025"
BASE_URL = "https://krdict.korean.go.kr/api/search"
LANG_CODES = {"en": 1, "ja": 2, "vi": 7, "zh": 11}
RATE_LIMIT = 0.4  # 초당 2-3건
MAX_RETRIES = 3
DATA_DIR = Path(__file__).parent.parent / "data" / "vocab"

# Google Translation API (필리핀어용, 선택)
GOOGLE_API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")


# ─── 교과 용어 리스트 ───

TERMS = {
    "과학_e34": {
        "subject": "과학",
        "grade": "3-4",
        "output": "vocab_science_e34.json",
        "terms": [
            # 생물
            "동물", "식물", "곤충", "포유류", "파충류", "양서류", "조류", "어류",
            "광합성", "뿌리", "줄기", "잎", "꽃", "열매", "씨앗",
            "나무", "풀", "균류", "세균", "생물",
            # 자석
            "자석", "나침반", "극", "인력", "척력", "자기장",
            # 혼합물
            "혼합물", "용해", "용액", "거름", "증발", "녹이다",
            # 지층
            "지층", "화석", "퇴적암", "화성암", "변성암", "광물", "암석",
            # 온도/열
            "온도", "온도계", "열", "전도", "대류", "복사",
            # 빛/그림자
            "그림자", "빛", "반사", "굴절", "투명",
            # 소리
            "소리", "진동", "높낮이", "소음",
            # 날씨
            "날씨", "기온", "습도", "이슬", "안개", "구름", "비", "눈", "바람",
            # 천체
            "태양", "달", "지구", "별자리", "계절", "행성",
        ],
    },
    "사회_e34": {
        "subject": "사회",
        "grade": "3-4",
        "output": "vocab_social_e34.json",
        "terms": [
            # 지도
            "지도", "방위", "축척", "등고선", "기호", "범례",
            # 경제
            "시장", "생산", "소비", "교환", "화폐", "저축", "은행", "가격",
            # 공공기관
            "공공기관", "시청", "도청", "경찰서", "소방서", "우체국", "도서관", "병원",
            # 전통문화
            "문화재", "전통", "풍습", "명절", "한복", "한옥", "김치",
            # 지역
            "도시", "농촌", "어촌", "산촌", "마을", "고장",
            # 교통/통신
            "교통", "통신", "정보", "인터넷", "신호등",
            # 환경
            "환경", "오염", "재활용", "분리수거", "쓰레기",
            # 인권/법
            "인권", "평등", "차별", "법", "규칙",
            # 민주주의
            "민주주의", "선거", "투표", "국회", "대통령", "시민",
        ],
    },
    "수학_e34": {
        "subject": "수학",
        "grade": "3-4",
        "output": "vocab_math_e34.json",
        "terms": [
            # 수와 연산
            "분수", "소수", "자연수", "덧셈", "뺄셈", "곱셈", "나눗셈",
            "몫", "나머지", "배수", "약수",
            # 도형
            "각도", "직각", "예각", "둔각", "삼각형", "사각형",
            "원", "반지름", "지름", "둘레", "넓이",
            "평행", "수직", "대칭",
            # 그래프
            "막대그래프", "꺾은선그래프", "표",
            # 측정
            "들이", "무게", "시간", "킬로그램", "리터",
            # 입체
            "평면도형", "입체도형", "직육면체", "정육면체",
            # 추가
            "수직선", "크기", "단위",
        ],
    },
    "과학_e56": {
        "subject": "과학",
        "grade": "5-6",
        "output": "vocab_science_e56.json",
        "terms": [
            # 생물
            "세포", "조직", "기관", "기관계",
            "호흡", "소화", "순환", "배설",
            # 생태계
            "생태계", "먹이사슬", "먹이그물", "생산자", "소비자", "분해자",
            "적응", "환경오염",
            # 날씨
            "기압", "기단", "전선", "태풍", "습도",
            # 전기
            "전기", "전류", "전압", "저항", "직렬", "병렬", "전지", "스위치",
            # 렌즈/빛
            "렌즈", "볼록렌즈", "오목렌즈", "프리즘", "무지개",
            # 산/염기
            "산", "염기", "산성", "염기성", "중성", "지시약",
            # 연소
            "연소", "소화기", "산소", "이산화탄소",
            # 천체
            "태양계", "위성", "항성", "은하", "별",
            # 운동/힘
            "속력", "속도", "힘", "중력", "마찰력", "무게",
        ],
    },
    "사회_e56": {
        "subject": "사회",
        "grade": "5-6",
        "output": "vocab_social_e56.json",
        "terms": [
            # 국토
            "국토", "영토", "영해", "영공", "위도", "경도",
            # 지형/기후
            "기후", "지형", "산맥", "평야", "해안", "반도", "섬",
            # 경제
            "경제성장", "산업화", "도시화", "무역", "수출", "수입", "산업",
            # 정치/법
            "헌법", "삼권분립", "입법", "사법", "행정", "국민",
            # 역사
            "광복", "독립운동", "민주화",
            # 세계화
            "세계화", "다문화", "편견", "상호존중",
            # 국제
            "국제기구",
            # 정보화
            "저작권", "개인정보",
            # 자원
            "자원", "에너지", "지속가능발전",
            # 추가
            "통일", "외교", "조약", "난민", "이민",
            "의무", "권리", "인구", "유엔", "세금", "문화유산", "정보화사회",
        ],
    },
}


def fetch_url(url: str) -> str:
    """URL에서 텍스트 응답을 가져온다. 최대 3회 재시도."""
    for attempt in range(MAX_RETRIES):
        try:
            req = Request(url)
            with urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8")
        except (URLError, HTTPError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
            else:
                raise e
    return ""


def search_krdict(term: str, lang_code: int) -> dict | None:
    """krdict API로 용어를 검색하고 번역 결과를 반환한다."""
    encoded = quote(term)
    url = (
        f"{BASE_URL}?key={API_KEY}&q={encoded}"
        f"&translated=y&trans_lang={lang_code}&num=100&start=1"
    )
    xml_text = fetch_url(url)
    if not xml_text:
        return None

    root = ET.fromstring(xml_text)
    # 정확히 일치하는 표제어 찾기
    for item in root.iter("item"):
        word_el = item.find("word")
        if word_el is None:
            continue
        # 표제어에서 하이픈/공백 제거 후 비교
        word = word_el.text.strip().replace("-", "").replace(" ", "")
        if word != term.replace("-", "").replace(" ", ""):
            continue

        result = {
            "target_code": "",
            "definition": "",
            "translation": "",
        }
        tc = item.find("target_code")
        if tc is not None and tc.text:
            result["target_code"] = tc.text.strip()

        sense = item.find("sense")
        if sense is not None:
            defn = sense.find("definition")
            if defn is not None and defn.text:
                result["definition"] = defn.text.strip()
            trans = sense.find("translation")
            if trans is not None:
                tw = trans.find("trans_word")
                if tw is not None and tw.text:
                    result["translation"] = tw.text.strip()
        return result
    return None


def translate_to_filipino(en_word: str) -> str:
    """Google Cloud Translation API로 영어→필리핀어 번역."""
    if not GOOGLE_API_KEY or not en_word:
        return ""
    try:
        import json as _json
        url = f"https://translation.googleapis.com/language/translate/v2?key={GOOGLE_API_KEY}"
        body = _json.dumps({
            "q": en_word,
            "source": "en",
            "target": "tl",
            "format": "text",
        }).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            return data["data"]["translations"][0]["translatedText"]
    except Exception:
        return ""


def crawl_subject(subject_key: str) -> list[dict]:
    """한 교과의 용어를 전부 크롤링한다."""
    config = TERMS[subject_key]
    subject = config["subject"]
    grade = config["grade"]
    terms = config["terms"]
    results = []

    print(f"\n{'='*60}")
    print(f"📚 {subject} {grade} 크롤링 시작 ({len(terms)}개 용어)")
    print(f"{'='*60}")

    for i, term in enumerate(terms, 1):
        entry = {
            "term_ko": term,
            "definition_ko": "",
            "easy_ko": "",
            "en": "",
            "ja": "",
            "zh": "",
            "vi": "",
            "tl": "",
            "subject": subject,
            "grade": grade,
            "source": "krdict",
            "krdict_target_code": "",
        }

        translations = {}
        for lang, code in LANG_CODES.items():
            time.sleep(RATE_LIMIT)
            try:
                result = search_krdict(term, code)
                if result:
                    translations[lang] = result["translation"]
                    if not entry["definition_ko"] and result["definition"]:
                        entry["definition_ko"] = result["definition"]
                    if not entry["krdict_target_code"] and result["target_code"]:
                        entry["krdict_target_code"] = result["target_code"]
                else:
                    translations[lang] = ""
            except Exception as e:
                print(f"  ⚠️ {term}: {lang} 에러 — {e}")
                translations[lang] = ""

        entry["en"] = translations.get("en", "")
        entry["ja"] = translations.get("ja", "")
        entry["zh"] = translations.get("zh", "")
        entry["vi"] = translations.get("vi", "")

        # 번역 누락 경고
        missing = [lang for lang, val in translations.items() if not val]
        if missing:
            print(f"  ⚠️ {term}: {', '.join(missing)} 번역 없음")

        # 필리핀어
        if entry["en"]:
            entry["tl"] = translate_to_filipino(entry["en"])

        log_parts = []
        for lang in ["en", "ja", "zh", "vi"]:
            val = entry[lang]
            log_parts.append(f"{lang}: {val if val else '❌'}")

        print(f"[{i}/{len(terms)}] {term} → {', '.join(log_parts)}")
        results.append(entry)

    return results


def print_stats(results: list[dict], label: str):
    """번역 완료율 통계를 출력한다."""
    total = len(results)
    if total == 0:
        return
    langs = ["en", "ja", "zh", "vi", "tl"]
    print(f"\n--- {label} 통계 ---")
    print(f"총 어휘 수: {total}개")
    for lang in langs:
        filled = sum(1 for r in results if r[lang])
        pct = filled / total * 100
        print(f"  {lang}: {pct:.0f}% ({filled}/{total})")
    empty_terms = {
        lang: [r["term_ko"] for r in results if not r[lang]]
        for lang in langs
    }
    for lang, terms in empty_terms.items():
        if terms:
            preview = terms[:10]
            suffix = f" 외 {len(terms)-10}개" if len(terms) > 10 else ""
            print(f"  {lang} 누락: {', '.join(preview)}{suffix}")


def crawl_single(subject_key: str):
    """단일 교과를 크롤링하고 저장한다."""
    config = TERMS[subject_key]
    output_file = DATA_DIR / config["output"]
    results = crawl_subject(subject_key)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 저장 완료: {output_file} ({len(results)}개)")
    print_stats(results, f"{config['subject']} {config['grade']}")
    return results


def crawl_all():
    """모든 교과를 순차 크롤링한다."""
    all_results = {}
    for key in TERMS:
        results = crawl_single(key)
        all_results[key] = results
    return all_results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        key = sys.argv[1]
        if key not in TERMS:
            print(f"사용 가능한 키: {', '.join(TERMS.keys())}")
            sys.exit(1)
        crawl_single(key)
    else:
        # 인자 없으면 전체 크롤링
        crawl_all()
