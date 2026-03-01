"""Flask 앱 설정. API 키는 환경변수에서 읽는다."""

import os

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
VOCAB_DIR = os.path.join(DATA_DIR, "vocab")
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")

MAX_IMAGE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
