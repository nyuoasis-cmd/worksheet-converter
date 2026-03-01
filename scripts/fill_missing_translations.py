#!/usr/bin/env python3
"""
Google Cloud Translation API로 vocab_all.json의 빈 번역 필드를 채웁니다.

사용법:
  python3 scripts/fill_missing_translations.py
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request


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
API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")
TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
DATA_DIR = Path(__file__).parent.parent / "data" / "vocab"
BATCH_SIZE = 128
RATE_LIMIT = 0.5

# 언어 코드 매핑 (Google Translate 코드)
LANG_MAP = {
    "en": "en",
    "ja": "ja",
    "zh": "zh-CN",
    "vi": "vi",
    "tl": "tl",
}

# 교과별 파일 매핑
SUBJECT_FILES = {
    "과학 3-4": "vocab_science_e34.json",
    "사회 3-4": "vocab_social_e34.json",
    "수학 3-4": "vocab_math_e34.json",
    "과학 5-6": "vocab_science_e56.json",
    "사회 5-6": "vocab_social_e56.json",
}


def google_translate_batch(texts: list[str], source: str, target: str) -> list[str]:
    """Google Cloud Translation API 배치 호출."""
    if not texts:
        return []

    results = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        body = json.dumps({
            "q": batch,
            "source": source,
            "target": target,
            "format": "text",
        }).encode("utf-8")
        req = Request(
            f"{TRANSLATE_URL}?key={API_KEY}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for t in data["data"]["translations"]:
            results.append(t["translatedText"])
        if i + BATCH_SIZE < len(texts):
            time.sleep(RATE_LIMIT)

    return results


def main():
    if not API_KEY:
        print("ERROR: GOOGLE_TRANSLATE_API_KEY 환경변수를 설정하세요.")
        print('  export GOOGLE_TRANSLATE_API_KEY="your-key"')
        sys.exit(1)

    all_file = DATA_DIR / "vocab_all.json"
    if not all_file.exists():
        print(f"ERROR: {all_file} 파일이 없습니다. merge_vocab.py를 먼저 실행하세요.")
        sys.exit(1)

    # 백업
    backup_file = DATA_DIR / "vocab_all_before_google.json"
    shutil.copy2(all_file, backup_file)
    print(f"백업 완료: {backup_file.name}")

    with open(all_file, encoding="utf-8") as f:
        vocab = json.load(f)

    # ─── 1단계: en/ja/zh/vi 누락 채우기 (ko → 해당 언어) ───
    filled_log: dict[str, list[str]] = {lang: [] for lang in LANG_MAP}

    for lang in ["en", "ja", "zh", "vi"]:
        missing_indices = [i for i, v in enumerate(vocab) if not v.get(lang)]
        if not missing_indices:
            print(f"  {lang}: 누락 없음")
            continue

        terms = [vocab[i]["term_ko"] for i in missing_indices]
        print(f"  {lang}: {len(terms)}개 누락 → Google Translate 호출 중...")
        translations = google_translate_batch(terms, "ko", LANG_MAP[lang])
        time.sleep(RATE_LIMIT)

        for idx, trans in zip(missing_indices, translations):
            vocab[idx][lang] = trans
            filled = vocab[idx].get("filled_by_google", [])
            if lang not in filled:
                filled.append(lang)
            vocab[idx]["filled_by_google"] = filled
            filled_log[lang].append(vocab[idx]["term_ko"])

    # ─── 2단계: tl 전체 채우기 (en → tl) ───
    # en이 없는 용어는 1단계에서 이미 채워졌으므로 모두 en 존재
    tl_indices = [i for i, v in enumerate(vocab) if not v.get("tl")]
    if tl_indices:
        en_texts = [vocab[i]["en"] for i in tl_indices]
        print(f"  tl: {len(tl_indices)}개 누락 → en 경유 Google Translate 호출 중...")
        tl_translations = google_translate_batch(en_texts, "en", "tl")
        time.sleep(RATE_LIMIT)

        for idx, trans in zip(tl_indices, tl_translations):
            vocab[idx]["tl"] = trans
            filled = vocab[idx].get("filled_by_google", [])
            if "tl" not in filled:
                filled.append("tl")
            vocab[idx]["filled_by_google"] = filled
            filled_log["tl"].append(vocab[idx]["term_ko"])

    # ─── 저장: vocab_all.json ───
    with open(all_file, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)
    print(f"\n저장 완료: {all_file.name}")

    # ─── 교과별 파일 업데이트 ───
    # vocab_all 기준으로 교과별 파일에 반영
    lookup: dict[str, dict] = {v["term_ko"]: v for v in vocab}

    for subject_label, filename in SUBJECT_FILES.items():
        filepath = DATA_DIR / filename
        if not filepath.exists():
            continue
        with open(filepath, encoding="utf-8") as f:
            subject_data = json.load(f)

        updated = 0
        for entry in subject_data:
            term = entry["term_ko"]
            if term not in lookup:
                continue
            merged = lookup[term]
            changed = False
            for lang in ["en", "ja", "zh", "vi", "tl"]:
                if not entry.get(lang) and merged.get(lang):
                    entry[lang] = merged[lang]
                    changed = True
            if changed:
                filled = merged.get("filled_by_google", [])
                if filled:
                    entry["filled_by_google"] = filled
                updated += 1

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(subject_data, f, ensure_ascii=False, indent=2)
        print(f"  {filename}: {updated}개 업데이트")

    # ─── 출력 ───
    print(f"\n{'='*50}")
    print(f"===== 번역 보완 완료 =====")
    print(f"{'='*50}")

    print("Google Translate로 채운 항목:")
    for lang in ["en", "ja", "zh", "vi", "tl"]:
        terms = filled_log[lang]
        if lang == "tl":
            print(f"  {lang}: {len(terms)}개 (전체)")
        elif terms:
            print(f"  {lang}: {len(terms)}개 ({', '.join(terms)})")
        else:
            print(f"  {lang}: 0개")

    total = len(vocab)
    print(f"\n최종 번역 완료율:")
    for lang in ["en", "ja", "zh", "vi", "tl"]:
        filled = sum(1 for v in vocab if v.get(lang))
        pct = filled / total * 100 if total else 0
        print(f"  {lang}: {pct:.0f}% ({filled}/{total})")

    # ─── 검증 ───
    empty_count = 0
    for v in vocab:
        for lang in ["en", "ja", "zh", "vi", "tl"]:
            if not v.get(lang):
                empty_count += 1
    print(f"\n빈 필드 수: {empty_count}개")

    google_filled_count = sum(1 for v in vocab if v.get("filled_by_google"))
    print(f"filled_by_google 표시 용어: {google_filled_count}개")

    # 샘플 3개
    samples = [v for v in vocab if v.get("filled_by_google")][:3]
    if samples:
        print(f"\n샘플 (Google로 채운 용어):")
        for s in samples:
            print(f"  {s['term_ko']}:")
            print(f"    filled_by_google: {s['filled_by_google']}")
            for lang in s["filled_by_google"]:
                print(f"    {lang}: {s.get(lang, '')}")


if __name__ == "__main__":
    main()
