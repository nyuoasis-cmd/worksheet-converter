#!/bin/bash
# worksheet-converter 로컬 개발 환경
# Flask API(5001) + youthschool 프론트엔드(5000) 동시 실행
#
# 사용법: bash dev-local.sh
# 종료:   Ctrl+C
#
# .env 파일을 수정하지 않으므로 다른 프로젝트에 영향 없음

set -e

FLASK_PORT=5001
WC_DIR="$(cd "$(dirname "$0")" && pwd)"
YS_DIR="/home/claude/youthschool"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  worksheet-converter 로컬 개발 환경${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

# 1) 기존 프로세스 정리
pkill -f "tsx server/index.ts" 2>/dev/null || true
pkill -f "python.*port=${FLASK_PORT}" 2>/dev/null || true
sleep 1

# 2) youthschool .env에서 API 키 로드
source "$YS_DIR/.env" 2>/dev/null
export GEMINI_API_KEY="${GOOGLE_AI_API_KEY}"

# 3) Flask API 서버 시작 (백그라운드)
echo -e "\n${CYAN}[1/2] Flask API 시작 (port ${FLASK_PORT})${NC}"
cd "$WC_DIR"
python3 -c "
from backend.app import create_app
app = create_app()
app.run(debug=True, port=${FLASK_PORT}, host='0.0.0.0', use_reloader=False)
" &
FLASK_PID=$!
sleep 2

if curl -sf "http://localhost:${FLASK_PORT}/api/health" > /dev/null; then
  echo -e "  ${GREEN}✓ Flask API: http://localhost:${FLASK_PORT}${NC}"
else
  echo "  ✗ Flask 시작 실패"
  kill $FLASK_PID 2>/dev/null
  exit 1
fi

# 4) youthschool 프론트엔드 시작
#    VITE_ 환경변수를 셸에서 먼저 export → dotenv가 덮어쓰지 않음
echo -e "\n${CYAN}[2/2] youthschool 프론트엔드 시작 (port 5000)${NC}"
export VITE_WORKSHEET_API_URL="http://localhost:${FLASK_PORT}"
cd "$YS_DIR"
npm run dev &
YS_PID=$!
sleep 4

echo -e "\n${GREEN}═══════════════════════════════════════════${NC}"
echo -e "  프론트엔드: ${GREEN}http://localhost:5000/worksheet-converter${NC}"
echo -e "  Flask API:  ${GREEN}http://localhost:${FLASK_PORT}${NC}"
echo -e "  .env 원본 유지 (다른 프로젝트 영향 없음)"
echo -e "  종료: Ctrl+C"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

cleanup() {
  echo -e "\n${CYAN}서버 종료 중...${NC}"
  kill $FLASK_PID $YS_PID 2>/dev/null
  pkill -f "tsx server/index.ts" 2>/dev/null || true
  echo -e "${GREEN}완료${NC}"
}
trap cleanup INT TERM
wait
