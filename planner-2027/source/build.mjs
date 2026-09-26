// 生成 2027 电子手帐（米色版 + 护眼黑版）PDF，并截取部分页面用于商品图。
//
//   node source/build.mjs [previewDir]
//
// 需要 Playwright 的 Chromium（找不到时用 PLAYWRIGHT_PATH 指定 playwright 包路径），
// 以及 source/fonts 下的字体（见 kp-planner-cn/source/fetch-fonts.sh）。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { renderPages } from './pages.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const previewDir = path.resolve(process.argv[2] || path.join(root, 'build'));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

// 在页面里运行：按剩余空间填充横线、表格行和网格（先统一读取尺寸，再统一写入）。
const FILL_SCRIPT = `(async () => {
  const theme = new URLSearchParams(location.search).get('theme');
  if (theme === 'dark') document.documentElement.classList.add('dark');
  await document.fonts.ready;
  const lineEls = [...document.querySelectorAll('[data-fill]')];
  const rowEls = [...document.querySelectorAll('tbody[data-fill-rows]')];
  const gridEls = [...document.querySelectorAll('[data-grid], [data-dot]')];
  const lineH = (el) => (el.classList.contains('sheet') ? 30 : el.closest('.wday') ? 26 : 28);
  const plan = lineEls.map((el) => Math.floor(el.clientHeight / lineH(el)));
  const rowPlan = rowEls.map((tb) => {
    const wrap = tb.closest('.tfill');
    const head = tb.parentElement.tHead ? tb.parentElement.tHead.offsetHeight : 0;
    return Math.floor((wrap.clientHeight - head) / 34);
  });
  const gridPlan = gridEls.map((el) => [el.clientWidth, el.clientHeight]);
  lineEls.forEach((el, i) => { el.innerHTML = '<i></i>'.repeat(Math.max(0, plan[i])); });
  rowEls.forEach((tb, i) => { const tpl = tb.rows[0].outerHTML; tb.innerHTML = tpl.repeat(Math.max(1, rowPlan[i])); });
  gridEls.forEach((el, i) => {
    const [w, h] = gridPlan[i];
    const s = el.hasAttribute('data-grid') ? 22 : 20;
    let inner = '';
    if (el.hasAttribute('data-grid')) {
      let d = '';
      for (let x = 0; x <= w; x += s) d += 'M' + x + ' 0V' + h;
      for (let y = 0; y <= h; y += s) d += 'M0 ' + y + 'H' + w;
      inner = '<path d="' + d + '" style="stroke:var(--line);stroke-width:1"/>';
    } else {
      for (let y = s / 2; y < h; y += s) for (let x = s / 2; x < w; x += s) inner += '<circle cx="' + x + '" cy="' + y + '" r="1.1" style="fill:var(--soft);stroke:none"/>';
    }
    el.innerHTML = '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' + inner + '</svg>';
  });
  document.body.dataset.ready = '1';
})();`;

const html = (pages) => `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>2027 电子手帐 · 农历节气版</title>
<link rel="stylesheet" href="planner.css"></head>
<body>${pages.join('\n')}<script>${FILL_SCRIPT}</script></body></html>`;

const productDir = path.join(root, 'product');
fs.mkdirSync(productDir, { recursive: true });
fs.mkdirSync(path.join(previewDir, 'pages'), { recursive: true });

const pages = renderPages();
const file = path.join(here, 'planner.html');
fs.writeFileSync(file, html(pages));
console.log(`${pages.length} pages`);

const PREVIEW_IDS = ['cover', 'index', 'year', 'goals', 'm-2', 'mp-2', 'w-6', 'd-20270206', 'd-20270915', 'm-9', 'extras', 'cornell-1', 'vocab-1'];

const browser = await chromium.launch();
for (const theme of ['light', 'dark']) {
  const page = await browser.newPage({ viewport: { width: 834, height: 1194 }, deviceScaleFactor: 2 });
  await page.goto(`${pathToFileURL(file)}?theme=${theme}`);
  await page.waitForSelector('body[data-ready]', { timeout: 300000 });
  const name = theme === 'dark' ? 'Planner-2027-Dark.pdf' : 'Planner-2027-Light.pdf';
  await page.pdf({ path: path.join(productDir, name), width: '834px', height: '1194px', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  console.log(`wrote product/${name}`);
  for (const id of PREVIEW_IDS) {
    await page.locator(`[id="${id}"]`).screenshot({ path: path.join(previewDir, 'pages', `${theme}-${id}.png`) });
  }
  await page.close();
}
await browser.close();
console.log(`previews in ${previewDir}/pages`);
