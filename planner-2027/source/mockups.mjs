// 生成商品图：淘宝/闲鱼方图（1600x1600）+ 小红书竖图（1200x1600）。
// 素材来自 build.mjs 输出的页面截图。
//
//   node source/mockups.mjs [previewDir]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { MONTHS } from './data.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const previewDir = path.resolve(process.argv[2] || path.join(root, 'build'));
const outDir = path.join(root, 'listing-images');
fs.mkdirSync(outDir, { recursive: true });
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const pg = (theme, id) => pathToFileURL(path.join(previewDir, 'pages', `${theme}-${id}.png`)).href;
const font = (f) => pathToFileURL(path.join(here, 'fonts', f)).href;

const CSS = `
@font-face { font-family: 'Serif'; src: url('${font('NotoSerifSC-900.ttf')}'); font-weight: 900; }
@font-face { font-family: 'Serif'; src: url('${font('NotoSerifSC-700.ttf')}'); font-weight: 700; }
@font-face { font-family: 'Sans'; src: url('${font('NotoSansSC-400.ttf')}'); font-weight: 400; }
@font-face { font-family: 'Sans'; src: url('${font('NotoSansSC-700.ttf')}'); font-weight: 700; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { overflow: hidden; font-family: 'Sans'; color: #2e2b27; position: relative;
  background: radial-gradient(ellipse at 70% 30%, #fbf8f2 0%, #f1ebe0 60%, #e8e0d2 100%); }
.serif { font-family: 'Serif'; font-weight: 900; }
.ipad { position: absolute; background: #1b1b1d; border-radius: 30px; padding: 14px; box-shadow: 0 28px 60px rgba(60,45,30,.35), 0 6px 14px rgba(60,45,30,.25), inset 0 0 0 2px #3b3b3f; }
.ipad img { display: block; width: 100%; border-radius: 14px; }
.thumb { position: absolute; border-radius: 10px; overflow: hidden; box-shadow: 0 14px 30px rgba(60,45,30,.25); background: #fff; }
.thumb img { display: block; width: 100%; }
.badge { display: inline-block; border-radius: 999px; padding: 7px 15px; font-weight: 700; font-size: 15px; background: #2e2b27; color: #fbf8f2; }
.badge.l { background: transparent; color: #2e2b27; border: 1.5px solid #2e2b27; }
.kicker { font-weight: 700; font-size: 15px; letter-spacing: .32em; color: #8a8378; }
.h { font-family: 'Serif'; font-weight: 900; line-height: 1.2; letter-spacing: .03em; }
.call { list-style: none; }
.call li { padding: 12px 0 12px 22px; border-bottom: 1px solid #d9d0c1; position: relative; font-size: 17px; line-height: 1.45; }
.call li::before { content: ''; position: absolute; left: 0; top: 19px; width: 10px; height: 10px; border-radius: 50%; background: var(--c, #9b3b4a); }
.call b { display: block; font-family: 'Serif'; font-weight: 900; font-size: 19px; }
.arrow { position: absolute; font-size: 30px; color: #8a8378; }
`;

const ipadW = (w) => w; // page aspect is handled by the image itself

const SQUARE = {
  '01-main': `
    <div style="position:absolute; left:56px; top:160px; width:330px">
      <div class="kicker">农历节气版</div>
      <div class="serif" style="font-size:118px; line-height:1; margin-top:14px">2027</div>
      <div class="h" style="font-size:46px; margin-top:6px">电子手帐</div>
      <p style="font-size:18px; color:#6d665c; margin-top:14px; line-height:1.6">每一天，都有它的节气与名字</p>
      <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:26px">
        <span class="badge">458页 全超链接</span><span class="badge">农历 · 节气 · 节日</span><span class="badge l">米色 + 护眼黑</span><span class="badge l">GoodNotes 等通用</span>
      </div>
    </div>
    <div class="ipad" style="left:548px; top:176px; width:228px; transform:rotate(6deg)"><img src="${pg('dark', 'd-20270206')}"></div>
    <div class="ipad" style="left:418px; top:140px; width:296px; transform:rotate(-3deg)"><img src="${pg('light', 'm-2')}"></div>`,

  '02-structure': `
    <div style="position:absolute; top:70px; width:100%; text-align:center">
      <div class="kicker">全手帐超链接</div>
      <div class="h" style="font-size:44px; margin-top:10px">年 › 月 › 周 › 日　一点即达</div>
    </div>
    ${[['year', '年历'], ['m-2', '月历'], ['w-6', '周计划'], ['d-20270206', '日计划']].map(([id, t], i) => `
      <div class="thumb" style="left:${48 + i * 184}px; top:230px; width:160px"><img src="${pg('light', id)}"></div>
      <div class="h" style="position:absolute; left:${48 + i * 184}px; top:470px; width:160px; text-align:center; font-size:20px">${t}</div>
      ${i < 3 ? `<div class="arrow" style="left:${212 + i * 184}px; top:318px">›</div>` : ''}`).join('')}
    <div style="position:absolute; top:560px; left:70px; right:70px; display:grid; grid-template-columns:repeat(3,1fr); gap:18px; text-align:center">
      ${[['10,000+', '个页面链接'], ['右侧标签', '任意月份一键跳转'], ['前后翻页', '每页都能回到上一天']].map(([a, b]) => `<div style="background:#fbf8f2; border-radius:16px; padding:22px 10px; box-shadow:0 10px 24px rgba(60,45,30,.12)"><div class="h" style="font-size:28px">${a}</div><div style="font-size:15px; color:#6d665c; margin-top:6px">${b}</div></div>`).join('')}
    </div>`,

  '03-daily': `
    <div class="ipad" style="left:56px; top:70px; width:430px; transform:rotate(-2deg)"><img src="${pg('light', 'd-20270915')}"></div>
    <div style="position:absolute; left:520px; top:96px; width:230px">
      <div class="kicker">每日页</div>
      <div class="h" style="font-size:36px; margin:10px 0 18px">一页装下<br>完整的一天</div>
      <ul class="call" style="--c:#b0703a">
        <li><b>农历与干支</b>八月十五 · 丁未羊年</li>
        <li><b>节气节日</b>中秋、清明、冬至都标好</li>
        <li><b>全年进度</b>第 258 天，还剩 107 天</li>
        <li><b>时间轴</b>06:00 – 23:00</li>
        <li><b>心情 · 天气 · 喝水</b>小小打卡，天天坚持</li>
      </ul>
    </div>`,

  '04-colors': `
    <div style="position:absolute; top:70px; width:100%; text-align:center">
      <div class="kicker">每月一色</div>
      <div class="h" style="font-size:44px; margin-top:10px">十二个月，十二种中国传统色</div>
    </div>
    <div style="position:absolute; top:220px; left:70px; right:70px; display:grid; grid-template-columns:repeat(4,1fr); gap:34px 20px; text-align:center">
      ${MONTHS.map((m) => `<div><div style="width:92px; height:92px; margin:0 auto 12px; border-radius:50%; background:${m.color}; box-shadow:0 10px 22px rgba(60,45,30,.22)"></div><div class="h" style="font-size:22px">${m.colorName}</div><div style="font-size:14px; color:#8a8378; margin-top:2px">${m.zh}</div></div>`).join('')}
    </div>`,

  '05-themes': `
    <div style="position:absolute; top:62px; width:100%; text-align:center">
      <div class="kicker">两个版本都给你</div>
      <div class="h" style="font-size:44px; margin-top:10px">米色纸 · 护眼黑</div>
    </div>
    <div class="ipad" style="left:70px; top:196px; width:310px"><img src="${pg('light', 'd-20270206')}"></div>
    <div class="ipad" style="left:420px; top:196px; width:310px"><img src="${pg('dark', 'd-20270206')}"></div>`,

  '06-extras': `
    <div style="position:absolute; top:62px; width:100%; text-align:center">
      <div class="kicker">不止日历</div>
      <div class="h" style="font-size:40px; margin-top:10px">目标 · 习惯打卡 · 记账 · 笔记</div>
    </div>
    ${[['goals', '年度目标'], ['mp-2', '习惯打卡 · 记账'], ['cornell-1', '康奈尔笔记'], ['vocab-1', '单词本'], ['year', '年历'], ['extras', '附录合集']].map(([id, t], i) => {
      const col = i % 3, row = Math.floor(i / 3);
      const x = 96 + col * 210, y = 178 + row * 300;
      return `<div class="thumb" style="left:${x}px; top:${y}px; width:180px"><img src="${pg('light', id)}"></div>
        <div class="h" style="position:absolute; left:${x - 10}px; top:${y + 262}px; width:200px; text-align:center; font-size:17px">${t}</div>`;
    }).join('')}`,

  '07-howto': `
    <div style="position:absolute; top:78px; width:100%; text-align:center">
      <div class="kicker">电子版 · 虚拟商品</div>
      <div class="h" style="font-size:44px; margin-top:10px">三步开始使用</div>
    </div>
    <div style="position:absolute; top:220px; left:60px; right:60px; display:grid; grid-template-columns:repeat(3,1fr); gap:24px; text-align:center">
      ${[['一', '下载', '拍下后自动发送<br>PDF 下载链接'], ['二', '导入', 'GoodNotes · Notability<br>享做笔记 · Noteshelf'], ['三', '点击', '开启只读模式，<br>点日期、标签即可跳转']].map(([n, t, d]) => `<div>
        <div class="serif" style="width:92px; height:92px; margin:0 auto 20px; border-radius:50%; background:#2e2b27; color:#fbf8f2; display:grid; place-items:center; font-size:40px">${n}</div>
        <div class="h" style="font-size:28px; margin-bottom:10px">${t}</div>
        <p style="font-size:16px; line-height:1.7; color:#6d665c">${d}</p></div>`).join('')}
    </div>
    <div style="position:absolute; bottom:70px; left:80px; right:80px; font-size:15px; line-height:2; color:#6d665c; text-align:center; border-top:1px solid #d9d0c1; padding-top:22px">
      2027 年放假调休安排公布后，免费更新新版本<br>数字化商品，发货后不支持无理由退款 · 仅限个人使用
    </div>`,
};

const PORTRAIT = {
  'xhs-1-cover': `
    <div style="position:absolute; top:64px; width:100%; text-align:center">
      <div class="kicker">一个人做的手帐</div>
      <div class="h" style="font-size:50px; margin-top:12px; line-height:1.25">我做了一本<br>2027 农历节气手帐</div>
      <p style="font-size:18px; color:#6d665c; margin-top:12px">每一天，都有它的节气与名字</p>
    </div>
    <div class="ipad" style="left:148px; top:318px; width:304px; transform:rotate(-2deg)"><img src="${pg('light', 'm-2')}"></div>`,
  'xhs-2-colors': `
    <div style="position:absolute; top:64px; width:100%; text-align:center">
      <div class="kicker">每月一色</div>
      <div class="h" style="font-size:44px; margin-top:12px">十二种中国传统色</div>
    </div>
    <div style="position:absolute; top:188px; left:50px; right:50px; display:grid; grid-template-columns:repeat(3,1fr); gap:18px 16px; text-align:center">
      ${MONTHS.map((m) => `<div><div style="width:72px; height:72px; margin:0 auto 8px; border-radius:50%; background:${m.color}; box-shadow:0 10px 22px rgba(60,45,30,.22)"></div><div class="h" style="font-size:21px">${m.colorName}</div><div style="font-size:13px; color:#8a8378; margin-top:2px">${m.zh}</div></div>`).join('')}
    </div>`,
  'xhs-3-daily': `
    <div style="position:absolute; top:56px; width:100%; text-align:center">
      <div class="h" style="font-size:40px">中秋这一页长这样</div>
      <p style="font-size:17px; color:#6d665c; margin-top:8px">农历 · 节气 · 全年进度 · 时间轴</p>
    </div>
    <div class="ipad" style="left:95px; top:180px; width:410px"><img src="${pg('light', 'd-20270915')}"></div>`,
};

const browser = await chromium.launch();
async function render(set, w, h) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
  for (const [name, body] of Object.entries(set)) {
    const file = path.join(previewDir, `mock-${name}.html`);
    fs.writeFileSync(file, `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>${CSS} body{width:${w}px;height:${h}px}</style></head><body>${body}</body></html>`);
    await page.goto(pathToFileURL(file).href);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth));
    await page.screenshot({ path: path.join(outDir, `${name}.jpg`), type: 'jpeg', quality: 90 });
    console.log(`wrote listing-images/${name}.jpg`);
  }
  await page.close();
}
await render(SQUARE, 800, 800);
await render(PORTRAIT, 600, 800);
await browser.close();
