"""Flask 앱 설정. API 키는 환경변수에서 읽는다."""

import os
from pathlib import Path

# .env 로드 (개발 환경)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GOOGLE_TRANSLATE_API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
VOCAB_DIR = os.path.join(DATA_DIR, "vocab")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")

VOCAB_FINAL_PATH = os.path.join(VOCAB_DIR, "vocab_final.json")

MAX_IMAGE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
