#!/usr/bin/env python3
"""
krdict 다국어 교과 어휘 수집 스크립트
=====================================
한국어기초사전 API에서 교과 용어의 다국어 번역을 일괄 추출한다.

사용법:
  # STEP 1: 언어 코드 확인
  python crawl_krdict_multilang.py --test-langs

  # STEP 2: 교과 용어 크롤링 (과학 초3-4)
  python crawl_krdict_multilang.py --subject science_e34

  # STEP 3: 추가 교과
  python crawl_krdict_multilang.py --subject math_e36
  python crawl_krdict_multilang.py --subject social_e36
  python crawl_krdict_multilang.py --subject school_admin

  # STEP 4: 전체 병합
  python crawl_krdict_multilang.py --merge

  # 중단된 크롤링 이어하기 (자동 감지)
  python crawl_krdict_multilang.py --subject science_e34  # 기존 진행분 자동 로드

환경변수:
  KRDICT_API_KEY  — krdict API 인증키 (필수)
"""

import os
import sys
import json
import time
import logging
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ requests 라이브러리가 필요합니다: pip install requests")
    sys.exit(1)

# ─── 설정 ───────────────────────────────────────────────

BASE_URL = "https://krdict.korean.go.kr/api/search"
VIEW_URL = "https://krdict.korean.go.kr/api/view"
OUTPUT_DIR = Path("data/vocab/krdict_multilang")
LOG_DIR = Path("logs")

RATE_LIMIT_BETWEEN_TERMS = 0.4  # 용어 간 대기 (초)
RATE_LIMIT_BETWEEN_LANGS = 0.2  # 언어 간 대기 (초)
MAX_RETRIES = 3
RETRY_DELAY = 2  # 재시도 대기 (초)
INCREMENTAL_SAVE_INTERVAL = 5  # N개 용어마다 중간 저장

# krdict 언어 코드 (STEP 1에서 확인 후 업데이트)
# 아래는 추정치 — --test-langs로 정확한 코드를 확인할 것
LANG_CODES = {
    1: ("en", "영어"),
    2: ("ja", "일본어"),
    3: ("fr", "프랑스어"),
    4: ("es", "스페인어"),
    5: ("ar", "아랍어"),
    6: ("mn", "몽골어"),
    7: ("vi", "베트남어"),
    8: ("th", "태국어"),
    9: ("id", "인도네시아어"),
    10: ("ru", "러시아어"),
    11: ("zh", "중국어"),
}

# ISO → 언어명 역매핑 (parse_translations의 lang_name 매칭 보강용)
ISO_TO_NAMES = {
    "en": ["영어", "English"],
    "ja": ["일본어", "Japanese"],
    "fr": ["프랑스어", "French"],
    "es": ["스페인어", "Spanish"],
    "ar": ["아랍어", "Arabic"],
    "mn": ["몽골어", "Mongolian"],
    "vi": ["베트남어", "Vietnamese"],
    "th": ["태국어", "Thai"],
    "id": ["인도네시아어", "Indonesian"],
    "ru": ["러시아어", "Russian"],
    "zh": ["중국어", "Chinese"],
}

# ─── 교과별 용어 리스트 ─────────────────────────────────

SUBJECTS = {
    "science_e34": {
        "name": "과학",
        "grade": "3-4",
        "terms": [
            "동물", "식물", "곤충", "포유류", "파충류", "양서류", "조류", "어류",
            "광합성", "뿌리", "줄기", "잎", "꽃", "열매", "씨앗",
            "자석", "나침반", "인력", "척력",
            "혼합물", "용해", "용액", "증발", "끓는점",
            "지층", "화석", "퇴적암", "화성암", "변성암", "화산", "지진",
            "온도", "온도계", "전도", "대류", "복사",
            "그림자", "반사", "굴절", "렌즈", "거울",
            "소리", "진동",
            "날씨", "기온", "습도", "이슬", "안개", "구름", "바람",
            "태양", "달", "지구", "별자리", "계절", "행성",
            "세포", "현미경", "산소", "이산화탄소", "물질", "에너지",
            "생태계", "먹이사슬", "환경", "오염", "재활용",
            "무게", "부력", "밀도", "속력", "운동",
            "수증기", "응결", "녹는점", "고체", "액체", "기체",
            "전기", "전류", "전압", "전지", "회로", "저항",
            "호흡", "소화", "혈액", "심장", "폐", "뼈", "근육",
        ],
    },
    "math_e36": {
        "name": "수학",
        "grade": "3-6",
        "terms": [
            "덧셈", "뺄셈", "곱셈", "나눗셈", "분수", "소수", "약분", "통분",
            "배수", "약수", "최대공약수", "최소공배수",
            "삼각형", "사각형", "원", "정사각형", "직사각형",
            "평행사변형", "마름모", "사다리꼴",
            "넓이", "둘레", "부피", "높이", "밑변", "꼭짓점", "모서리",
            "대칭", "회전", "이동", "좌표", "비율", "백분율", "비례",
            "평균", "그래프", "막대그래프",
            "각도", "직각", "예각", "둔각", "수직", "평행",
            "자연수", "정수", "홀수", "짝수",
            "무게", "길이", "시간", "거리",
            "정다각형", "원기둥", "원뿔", "구", "직육면체",
            "방정식", "규칙", "수열", "확률",
        ],
    },
    "social_e36": {
        "name": "사회",
        "grade": "3-6",
        "terms": [
            "지도", "방위", "축척", "등고선", "범례",
            "마을", "도시", "농촌", "어촌", "산촌",
            "시장", "경제", "생산", "소비", "무역", "수출", "수입",
            "민주주의", "선거", "국회", "정부", "법원", "헌법", "권리", "의무",
            "역사", "문화", "유산", "전통",
            "인구", "환경", "교통", "통신", "정보",
            "세계", "대륙", "국기", "수도",
            "독립", "전쟁", "평화", "조약", "외교",
            "국민", "시민", "법률", "세금", "복지",
            "산업", "농업", "공업", "서비스업",
        ],
    },
    "school_admin": {
        "name": "학교행정",
        "grade": "전학년",
        "terms": [
            "가정통신문", "알림장", "방과후학교", "돌봄교실",
            "현장체험학습", "수학여행",
            "급식", "식단표", "알레르기",
            "교복", "실내화", "준비물", "체육복",
            "결석", "지각", "조퇴", "출석",
            "학기", "방학", "개학", "졸업식", "입학식",
            "시험", "평가", "성적", "수행평가",
            "학부모", "담임", "교장", "상담",
            "교과서", "공책", "숙제", "과제", "도서관",
            "안전", "소방훈련", "대피훈련",
            "장학금", "교육비",
            "운동회", "학예회", "동아리",
            "교무실", "보건실", "급식실", "체육관",
        ],
    },
}

# ─── 유틸리티 ───────────────────────────────────────────

def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "crawl_krdict.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

def get_api_key():
    key = os.environ.get("KRDICT_API_KEY")
    if not key:
        print("❌ 환경변수 KRDICT_API_KEY가 설정되지 않았습니다.")
        print("   export KRDICT_API_KEY=your_key_here")
        print("   발급: https://krdict.korean.go.kr/openApi/openApiRegister")
        sys.exit(1)
    return key

def api_call(url, params, retries=MAX_RETRIES):
    """API 호출 + 재시도 로직"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logging.warning(f"API 에러 (시도 {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
    return None

def find_translation(translations_dict, iso_code):
    """lang_name 기반으로 번역을 찾되, 다양한 표기를 허용"""
    expected_names = ISO_TO_NAMES.get(iso_code, [])
    for lang_name, trans in translations_dict.items():
        if lang_name in expected_names or iso_code in lang_name.lower():
            return trans
    # 1개만 있으면 그걸 반환 (translated_language 파라미터로 1개 언어만 요청했으므로)
    if len(translations_dict) == 1:
        return list(translations_dict.values())[0]
    return None

def parse_translations(xml_text):
    """XML 응답에서 번역 정보를 추출"""
    if not xml_text:
        return []

    results = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            entry = {
                "target_code": "",
                "word": "",
                "definition": "",
                "translations": {},
            }

            tc = item.find("target_code")
            if tc is not None:
                entry["target_code"] = tc.text or ""

            word = item.find("word")
            if word is not None:
                entry["word"] = (word.text or "").strip().replace("-", "")

            # 한국어 뜻풀이 + 번역
            for sense in item.iter("sense"):
                dfn = sense.find("definition")
                if dfn is not None and not entry["definition"]:
                    entry["definition"] = dfn.text or ""

                for trans in sense.iter("translation"):
                    lang_el = trans.find("trans_lang")
                    word_el = trans.find("trans_word")
                    dfn_el = trans.find("trans_dfn")

                    if lang_el is not None:
                        lang_name = lang_el.text or ""
                        trans_word = word_el.text if word_el is not None else ""
                        trans_dfn = dfn_el.text if dfn_el is not None else ""

                        entry["translations"][lang_name] = {
                            "word": trans_word or "",
                            "definition": trans_dfn or "",
                        }

            results.append(entry)
    except ET.ParseError as e:
        logging.error(f"XML 파싱 에러: {e}")

    return results

def save_json(data, filepath):
    """JSON 저장 (UTF-8, 한글 보존) — 원자적 쓰기"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp = filepath.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(filepath)
    logging.info(f"저장: {filepath} ({len(data) if isinstance(data, list) else 'dict'})")

def dedup_terms(terms):
    """용어 리스트 중복 제거 (순서 유지)"""
    seen = set()
    result = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result

# ─── STEP 1: 언어 코드 테스트 ──────────────────────────

def test_language_codes(api_key):
    """krdict API의 translated_language 코드를 1~15까지 테스트"""
    print("\n🔍 STEP 1: krdict 언어 코드 테스트")
    print("=" * 60)

    test_word = "나무"
    results = {}

    for code in range(1, 16):
        params = {
            "key": api_key,
            "q": test_word,
            "translated_language": code,
            "advanced": "y",
            "method": "exact",
            "type_search": "search",
        }

        xml = api_call(BASE_URL, params)
        if not xml:
            continue

        parsed = parse_translations(xml)
        if parsed:
            for entry in parsed:
                if entry["word"] == test_word:
                    for lang_name, trans in entry["translations"].items():
                        results[str(code)] = {
                            "lang_name": lang_name,
                            "trans_word": trans["word"],
                        }
                    break

        time.sleep(0.5)
        status = "✅" if str(code) in results else "❌"
        lang = results.get(str(code), {}).get("lang_name", "없음")
        print(f"  코드 {code:2d}: {status} {lang}")

    # ISO 코드 매핑 (이름 기반)
    name_to_iso = {}
    for iso, names in ISO_TO_NAMES.items():
        for name in names:
            name_to_iso[name] = iso

    for code, info in results.items():
        info["iso_code"] = name_to_iso.get(info["lang_name"], "??")

    output = {
        "test_word": test_word,
        "lang_codes": results,
        "tested_at": datetime.now().isoformat(),
    }

    outfile = OUTPUT_DIR / "krdict_lang_test.json"
    save_json(output, outfile)

    # 요약 테이블
    print("\n" + "=" * 60)
    print(f"{'코드':>4} | {'언어명':<10} | {'ISO':<4} | {'번역어'}")
    print("-" * 60)
    for code in sorted(results.keys(), key=int):
        info = results[code]
        print(f"{code:>4} | {info['lang_name']:<10} | {info.get('iso_code','??'):<4} | {info['trans_word']}")

    print(f"\n총 {len(results)}개 언어 확인됨")
    print(f"결과 저장: {outfile}")
    print(f"\n✅ STEP 2 실행 시 이 결과가 자동으로 로드됩니다.")
    return results

# ─── STEP 2: 교과 용어 크롤링 ──────────────────────────

def load_checkpoint(outfile):
    """기존 크롤링 결과 로드 (이어하기용)"""
    if not outfile.exists():
        return [], set()
    try:
        with open(outfile, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            done_terms = {e["term_ko"] for e in data if e.get("term_ko")}
            return data, done_terms
    except (json.JSONDecodeError, KeyError):
        pass
    return [], set()

def crawl_subject(api_key, subject_key):
    """특정 교과의 용어를 다국어로 크롤링 (중간 저장 + 이어하기 지원)"""
    if subject_key not in SUBJECTS:
        print(f"❌ 알 수 없는 교과: {subject_key}")
        print(f"   사용 가능: {', '.join(SUBJECTS.keys())}")
        sys.exit(1)

    subject = SUBJECTS[subject_key]
    terms = dedup_terms(subject["terms"])
    total = len(terms)
    outfile = OUTPUT_DIR / f"krdict_{subject_key}.json"

    print(f"\n📚 교과: {subject['name']} ({subject['grade']})")
    print(f"   용어 수: {total}개")
    print(f"   대상 언어: {len(LANG_CODES)}개")

    # ── 이어하기: 기존 결과 로드 ──
    results, done_terms = load_checkpoint(outfile)
    if done_terms:
        print(f"   🔄 기존 진행분 발견: {len(done_terms)}개 완료, {total - len(done_terms)}개 남음")

    # ── 언어 코드 로드 (STEP 1 결과가 있으면 사용) ──
    lang_test_file = OUTPUT_DIR / "krdict_lang_test.json"
    active_langs = dict(LANG_CODES)

    if lang_test_file.exists():
        with open(lang_test_file, "r", encoding="utf-8") as f:
            test_data = json.load(f)
        active_langs = {}
        for code, info in test_data.get("lang_codes", {}).items():
            iso = info.get("iso_code", "??")
            name = info.get("lang_name", "")
            if iso != "??":
                active_langs[int(code)] = (iso, name)
        print(f"   ✅ STEP 1 결과 로드: {len(active_langs)}개 언어")
    else:
        print(f"   ⚠️  STEP 1 미실행. 기본 코드 사용 (정확도 보장 안 됨)")

    print("=" * 70)

    # ── 통계 초기화 (기존 결과 반영) ──
    stats = {iso: 0 for _, (iso, _) in active_langs.items()}
    for entry in results:
        for _, (iso, _) in active_langs.items():
            trans = entry.get("translations", {}).get(iso, {})
            if isinstance(trans, dict) and trans.get("word"):
                stats[iso] += 1

    # ── 크롤링 루프 ──
    newly_crawled = 0
    try:
        for idx, term in enumerate(terms, 1):
            if term in done_terms:
                continue

            entry = {
                "term_ko": term,
                "definition_ko": "",
                "target_code": "",
                "translations": {iso: {"word": "", "definition": ""} for _, (iso, _) in active_langs.items()},
                "subject": subject["name"],
                "grade": subject["grade"],
                "source": "krdict",
            }

            status_parts = []

            for lang_code, (iso, lang_name) in active_langs.items():
                params = {
                    "key": api_key,
                    "q": term,
                    "translated_language": lang_code,
                    "advanced": "y",
                    "method": "exact",
                    "type_search": "search",
                }

                xml = api_call(BASE_URL, params)
                parsed = parse_translations(xml) if xml else []

                found = False
                for p in parsed:
                    if p["word"] == term:
                        if not entry["definition_ko"] and p["definition"]:
                            entry["definition_ko"] = p["definition"]
                        if not entry["target_code"] and p["target_code"]:
                            entry["target_code"] = p["target_code"]

                        trans = find_translation(p["translations"], iso)
                        if trans and trans.get("word"):
                            entry["translations"][iso] = trans
                            stats[iso] += 1
                            found = True
                        break

                status_parts.append(f"{iso}:{'✅' if found else '❌'}")
                time.sleep(RATE_LIMIT_BETWEEN_LANGS)

            results.append(entry)
            done_terms.add(term)
            newly_crawled += 1
            status_str = " ".join(status_parts)
            print(f"[{idx}/{total}] {term} → {status_str}")

            # 중간 저장
            if newly_crawled % INCREMENTAL_SAVE_INTERVAL == 0:
                save_json(results, outfile)
                logging.info(f"중간 저장 ({len(results)}개)")

            time.sleep(RATE_LIMIT_BETWEEN_TERMS)

    except KeyboardInterrupt:
        print(f"\n\n⚠️  중단됨! 현재까지 {len(results)}개 저장 중...")
        save_json(results, outfile)
        print(f"   저장 완료: {outfile}")
        print(f"   같은 명령으로 재실행하면 이어서 크롤링합니다.")
        sys.exit(0)

    # ── 최종 저장 ──
    save_json(results, outfile)

    # ── 통계 ──
    crawled_total = len(results)
    print("\n" + "=" * 70)
    print(f"✅ {subject['name']} 크롤링 완료: {crawled_total}개 용어 (신규 {newly_crawled}개)")
    print(f"\n언어별 번역 확보율:")
    for lang_code, (iso, lang_name) in sorted(active_langs.items()):
        count = stats[iso]
        pct = (count / crawled_total * 100) if crawled_total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {iso:>3} ({lang_name:<6}): {bar} {pct:5.1f}% ({count}/{crawled_total})")

    # 번역 확보율 낮은 언어 경고
    for lang_code, (iso, lang_name) in active_langs.items():
        pct = (stats[iso] / crawled_total * 100) if crawled_total > 0 else 0
        if pct < 50:
            print(f"\n  ⚠️  {iso} ({lang_name}) 확보율 {pct:.0f}% — STEP 5 Gemini 보충 권장")

    print(f"\n결과 저장: {outfile}")

    # 샘플 출력
    print("\n📋 샘플 (처음 3개):")
    for entry in results[:3]:
        print(f"\n  {entry['term_ko']} (tc: {entry['target_code']})")
        for iso, trans in entry["translations"].items():
            if isinstance(trans, dict) and trans.get("word"):
                word = trans["word"][:30]
                print(f"    {iso}: {word}")

    return results

# ─── STEP 4: 병합 ──────────────────────────────────────

def merge_all():
    """모든 교과 JSON을 하나로 병합"""
    print("\n🔄 STEP 4: 전체 병합")
    print("=" * 60)

    all_entries = []
    seen_terms = set()

    skip_files = {"krdict_lang_test.json", "krdict_full_multilang.json"}

    for json_file in sorted(OUTPUT_DIR.glob("krdict_*.json")):
        if json_file.name in skip_files:
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            continue

        added = 0
        for entry in data:
            term = entry.get("term_ko", "")
            if term and term not in seen_terms:
                seen_terms.add(term)
                all_entries.append(entry)
                added += 1

        print(f"  📄 {json_file.name}: {len(data)}개 중 {added}개 추가")

    if not all_entries:
        print("❌ 병합할 파일이 없습니다. STEP 2~3을 먼저 실행하세요.")
        return

    # vocab_final.json 호환 포맷으로 변환
    # tl(필리핀어)은 krdict 미지원 — 빈값으로 유지
    all_isos = ["en", "ja", "zh", "vi", "tl", "fr", "es", "ru", "ar", "th", "id", "mn"]
    flat_entries = []
    for entry in all_entries:
        flat = {
            "term_ko": entry["term_ko"],
            "definition_ko": entry.get("definition_ko", ""),
            "easy_ko": "",
            "subject": entry.get("subject", ""),
            "grade": entry.get("grade", ""),
            "source": "krdict",
            "target_code": entry.get("target_code", ""),
        }

        translations = entry.get("translations", {})
        for iso in all_isos:
            trans = translations.get(iso, {})
            flat[iso] = trans.get("word", "") if isinstance(trans, dict) else ""

        flat_entries.append(flat)

    outfile = OUTPUT_DIR / "krdict_full_multilang.json"
    save_json(flat_entries, outfile)

    # 통계
    print(f"\n{'=' * 60}")
    print(f"총 어휘 수: {len(flat_entries)}개")

    print(f"\n언어별 번역 확보율:")
    for iso in all_isos:
        count = sum(1 for e in flat_entries if e.get(iso))
        pct = (count / len(flat_entries) * 100) if flat_entries else 0
        note = " (krdict 미지원)" if iso == "tl" and count == 0 else ""
        print(f"  {iso:>3}: {pct:5.1f}% ({count}/{len(flat_entries)}){note}")

    print(f"\n교과별 분포:")
    subject_counts = {}
    for e in flat_entries:
        subj = e.get("subject", "기타")
        subject_counts[subj] = subject_counts.get(subj, 0) + 1
    for subj, count in sorted(subject_counts.items()):
        print(f"  {subj}: {count}개")

    # vocab_final.json 교차 분석
    vocab_final = Path("data/vocab/vocab_final.json")
    if vocab_final.exists():
        with open(vocab_final, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_terms = {e.get("term_ko", "") for e in existing if e.get("term_ko")}
        new_terms = seen_terms - existing_terms
        overlap = seen_terms & existing_terms
        print(f"\nvocab_final.json 교차 분석:")
        print(f"  기존: {len(existing_terms)}개 | 신규: {len(new_terms)}개 | 교집합: {len(overlap)}개")

    print(f"\n결과 저장: {outfile}")

# ─── 메인 ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="krdict 다국어 교과 어휘 수집")
    parser.add_argument("--test-langs", action="store_true", help="STEP 1: 언어 코드 테스트")
    parser.add_argument("--subject", type=str, help="STEP 2-3: 교과 크롤링 (science_e34, math_e36, social_e36, school_admin)")
    parser.add_argument("--merge", action="store_true", help="STEP 4: 전체 병합")
    args = parser.parse_args()

    setup_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not any([args.test_langs, args.subject, args.merge]):
        parser.print_help()
        print("\n사용 예:")
        print("  python crawl_krdict_multilang.py --test-langs")
        print("  python crawl_krdict_multilang.py --subject science_e34")
        print("  python crawl_krdict_multilang.py --merge")
        return

    if args.test_langs:
        api_key = get_api_key()
        test_language_codes(api_key)

    if args.subject:
        api_key = get_api_key()
        crawl_subject(api_key, args.subject)

    if args.merge:
        merge_all()

if __name__ == "__main__":
    main()
