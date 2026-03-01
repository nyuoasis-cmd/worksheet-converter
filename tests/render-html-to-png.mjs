/**
 * HTML → PNG 렌더링 스크립트 — 시각 검증용
 *
 * worksheet-converter 테스트 결과 HTML을 Puppeteer로 PNG 이미지로 변환한다.
 * 에이전트가 Read 도구로 PNG를 열어 시각 검증할 수 있다.
 *
 * 사용법:
 *   node tests/render-html-to-png.mjs                          # results/ 내 모든 HTML
 *   node tests/render-html-to-png.mjs tests/results/test2.html # 특정 파일
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.join(__dirname, "results");

// api.ts의 wrapHtmlForPdf와 동일한 CSS (PDF/PNG 렌더링용)
function wrapHtml(bodyHtml) {
  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
<style>
  body { font-family: 'Noto Sans JP', 'Noto Sans KR', sans-serif; margin: 40px; font-size: 14px; line-height: 1.6; color: #1a1a1a; }
  .worksheet-header { margin-bottom: 20px; }
  .worksheet-header h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
  .worksheet-header .grade { color: #555; font-size: 13px; margin-bottom: 0; }
  .question-type-label { font-size: 13px; font-weight: 700; color: #1E40AF; background: #EFF6FF; border-left: 3px solid #3B82F6; padding: 5px 12px; margin: 16px 0 8px; border-radius: 0 4px 4px 0; }
  .question { margin-bottom: 20px; }
  .image-hint { font-size: 12px; color: #7C3AED; background: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 6px; padding: 6px 12px; margin-bottom: 8px; }
  .question-text { margin-bottom: 8px; }
  .choices { margin-left: 20px; }
  .choice { margin-bottom: 4px; }
  .explanation { color: #2563eb; }
  .term-multilingual { color: #7c3aed; font-weight: 500; }
  .ko-ref { display: block; font-size: 11px; color: #94A3B8; margin-top: 2px; }
  .question-type-label .ko-ref { display: inline; margin-left: 6px; font-weight: 400; }
  .image-hint .ko-ref { display: inline; margin-left: 4px; }
</style>
</head>
<body>${bodyHtml}</body>
</html>`;
}

async function renderToPng(htmlPath) {
  const bodyHtml = fs.readFileSync(htmlPath, "utf-8");
  const fullHtml = wrapHtml(bodyHtml);
  const pngPath = htmlPath.replace(/\.html$/, ".png");

  // Puppeteer를 동적 import (youthschool의 node_modules 활용)
  let puppeteer;
  try {
    puppeteer = await import("puppeteer");
  } catch {
    // youthschool의 puppeteer 경로 직접 시도
    const ysPath = path.join(__dirname, "..", "..", "youthschool", "node_modules", "puppeteer", "lib", "esm", "puppeteer", "puppeteer.js");
    puppeteer = await import(ysPath);
  }

  const browser = await puppeteer.default.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 800, height: 1200 });
    await page.setContent(fullHtml, { waitUntil: "networkidle0", timeout: 15000 });

    // 전체 페이지 높이에 맞춰 스크린샷
    await page.screenshot({ path: pngPath, fullPage: true });
    console.log(`  OK  ${path.basename(htmlPath)} → ${path.basename(pngPath)}`);
    return pngPath;
  } finally {
    await browser.close();
  }
}

async function main() {
  let files = process.argv.slice(2);

  if (files.length === 0) {
    // results/ 내 모든 HTML 파일
    if (!fs.existsSync(RESULTS_DIR)) {
      console.error("results/ 디렉토리 없음. 먼저 run_convert_test.py를 실행하세요.");
      process.exit(1);
    }
    files = fs.readdirSync(RESULTS_DIR)
      .filter((f) => f.endsWith(".html"))
      .sort()
      .map((f) => path.join(RESULTS_DIR, f));
  } else {
    // 상대경로 → 절대경로
    files = files.map((f) => path.resolve(f));
  }

  if (files.length === 0) {
    console.error("렌더링할 HTML 파일 없음.");
    process.exit(1);
  }

  console.log(`\nHTML → PNG 렌더링 (${files.length}개 파일)\n`);

  const results = [];
  for (const file of files) {
    try {
      const png = await renderToPng(file);
      results.push(png);
    } catch (err) {
      console.error(`  FAIL  ${path.basename(file)}: ${err.message}`);
    }
  }

  console.log(`\n완료: ${results.length}/${files.length}개 PNG 생성`);
  if (results.length > 0) {
    console.log(`출력 경로: ${path.dirname(results[0])}/`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
