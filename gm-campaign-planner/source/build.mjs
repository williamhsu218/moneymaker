// Builds the planner PDFs (US Letter + A4), a free one-page sample, and
// page preview PNGs used for the listing images.
//
//   node source/build.mjs [outDir]
//
// Needs Playwright's Chromium (set PLAYWRIGHT_PATH to the playwright package
// if it isn't resolvable from here).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { renderPages, contents, PAGE_COUNT, TITLE } from './pages.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const previewDir = path.resolve(process.argv[2] || path.join(root, 'build'));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

// Runs in the page: sizes the page, then fills lines, rows, grids and the TOC
// to whatever space each page has left.
const FILL_SCRIPT = `(async () => {
  const size = new URLSearchParams(location.search).get('size') || 'letter';
  document.documentElement.classList.add(size);
  await document.fonts.ready;
  const toc = ${JSON.stringify(contents())};
  for (const el of document.querySelectorAll('[data-toc]')) {
    let last = '';
    el.innerHTML = toc.map((t) => {
      const head = t.section !== last ? '<div class="sec">' + t.section + '</div>' : '';
      last = t.section;
      return head + '<div class="item"><span>' + t.title + '</span><span class="leader"></span><span>' + t.n + '</span></div>';
    }).join('');
  }
  for (const el of document.querySelectorAll('[data-fill="lines"]')) {
    el.innerHTML = '';
    while (el.scrollHeight <= el.clientHeight && el.children.length < 200) {
      const d = document.createElement('div'); d.className = 'ln'; el.appendChild(d);
    }
    if (el.scrollHeight > el.clientHeight && el.lastChild) el.lastChild.remove();
  }
  for (const tb of document.querySelectorAll('tbody[data-fill="rows"]')) {
    const wrap = tb.closest('.tw');
    const tpl = tb.rows[0].cloneNode(true);
    while (wrap.scrollHeight <= wrap.clientHeight && tb.rows.length < 200) tb.appendChild(tpl.cloneNode(true));
    if (wrap.scrollHeight > wrap.clientHeight) tb.lastElementChild.remove();
  }
  const svg = (w, h, inner) => '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' + inner + '</svg>';
  for (const el of document.querySelectorAll('[data-hex]')) {
    const w = el.clientWidth, h = el.clientHeight, r = 26, dy = Math.sqrt(3) * r;
    let d = '';
    for (let c = 0; c * 1.5 * r < w + r; c++) {
      for (let k = -1; k * dy < h + dy; k++) {
        const cx = c * 1.5 * r, cy = k * dy + (c % 2 ? dy / 2 : 0);
        for (let i = 0; i < 6; i++) {
          const a = Math.PI / 3 * i;
          d += (i ? 'L' : 'M') + (cx + r * Math.cos(a)).toFixed(1) + ' ' + (cy + r * Math.sin(a)).toFixed(1);
        }
        d += 'Z';
      }
    }
    el.innerHTML = svg(w, h, '<path d="' + d + '" stroke="#9c948a" stroke-width="0.7" fill="none"/>');
  }
  for (const el of document.querySelectorAll('[data-squares]')) {
    const w = el.clientWidth, h = el.clientHeight, s = 24;
    let thin = '', thick = '';
    for (let x = 0, i = 0; x <= w; x += s, i++) (i % 4 ? (thin += 'M' + x + ' 0V' + h) : (thick += 'M' + x + ' 0V' + h));
    for (let y = 0, i = 0; y <= h; y += s, i++) (i % 4 ? (thin += 'M0 ' + y + 'H' + w) : (thick += 'M0 ' + y + 'H' + w));
    el.innerHTML = svg(w, h, '<path d="' + thin + '" stroke="#c4bcb1" stroke-width="0.6"/><path d="' + thick + '" stroke="#8f877d" stroke-width="0.8"/>');
  }
  for (const el of document.querySelectorAll('[data-dots]')) {
    const w = el.clientWidth, h = el.clientHeight, s = 19.2;
    let c = '';
    for (let y = s / 2; y < h; y += s) for (let x = s / 2; x < w; x += s) c += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="0.9"/>';
    el.innerHTML = svg(w, h, c);
  }
  document.body.dataset.ready = '1';
})();`;

function html(pages) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${TITLE}</title>
<link rel="stylesheet" href="planner.css">
</head>
<body>
${pages.join('\n')}
<script>${FILL_SCRIPT}</script>
</body>
</html>`;
}

const SIZES = {
  letter: { width: '8.5in', height: '11in', px: [816, 1056] },
  a4: { width: '210mm', height: '297mm', px: [794, 1123] },
};

const productDir = path.join(root, 'product');
fs.mkdirSync(productDir, { recursive: true });
fs.mkdirSync(path.join(previewDir, 'pages'), { recursive: true });

const pages = renderPages();
const fullHtml = path.join(here, 'planner.html');
const sampleHtml = path.join(here, 'sample.html');
fs.writeFileSync(fullHtml, html(pages));
// Free sample: the Session Prep page (page 21), great for giveaways.
fs.writeFileSync(sampleHtml, html([pages[20]]));

const browser = await chromium.launch();
async function print(file, size, out) {
  const s = SIZES[size];
  const page = await browser.newPage({ viewport: { width: s.px[0], height: s.px[1] } });
  await page.goto(`${pathToFileURL(file)}?size=${size}`);
  await page.waitForSelector('body[data-ready]');
  await page.pdf({ path: out, width: s.width, height: s.height, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await page.close();
  console.log(`wrote ${path.relative(root, out)}`);
}

await print(fullHtml, 'letter', path.join(productDir, 'GM-Campaign-Planner-US-Letter.pdf'));
await print(fullHtml, 'a4', path.join(productDir, 'GM-Campaign-Planner-A4.pdf'));
await print(sampleHtml, 'letter', path.join(productDir, 'FREE-Session-Prep-Page-US-Letter.pdf'));

// High-res page images for listing mockups.
const shot = await browser.newPage({ viewport: { width: 816, height: 1056 }, deviceScaleFactor: 2.5 });
await shot.goto(`${pathToFileURL(fullHtml)}?size=letter`);
await shot.waitForSelector('body[data-ready]');
const handles = await shot.$$('.page');
for (let i = 0; i < handles.length; i++) {
  await handles[i].screenshot({ path: path.join(previewDir, 'pages', `page-${String(i + 1).padStart(2, '0')}.png`) });
}
console.log(`wrote ${handles.length} page previews to ${previewDir}/pages (expected ${PAGE_COUNT})`);
await browser.close();
