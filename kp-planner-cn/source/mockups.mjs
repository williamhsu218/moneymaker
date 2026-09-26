// 生成闲鱼商品图（正方形 1600x1600），素材来自 build.mjs 输出的页面预览。
//
//   node source/mockups.mjs [previewDir]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const previewDir = path.resolve(process.argv[2] || path.join(root, 'build'));
const outDir = path.join(root, 'listing-images');
fs.mkdirSync(outDir, { recursive: true });
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const pg = (n) => pathToFileURL(path.join(previewDir, 'pages', `page-${String(n).padStart(2, '0')}.png`)).href;
const font = (f) => pathToFileURL(path.join(here, 'fonts', f)).href;

const CSS = `
@font-face { font-family: 'Brush'; src: url('${font('MaShanZheng-Regular.ttf')}'); }
@font-face { font-family: 'Serif'; src: url('${font('NotoSerifSC-400.ttf')}'); font-weight: 400; }
@font-face { font-family: 'Serif'; src: url('${font('NotoSerifSC-900.ttf')}'); font-weight: 900; }
@font-face { font-family: 'Sans'; src: url('${font('NotoSansSC-700.ttf')}'); font-weight: 700; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 800px; height: 800px; overflow: hidden; font-family: 'Serif', serif; color: #eee5cf;
  background: radial-gradient(ellipse at 60% 35%, #1d4740 0%, #0d221e 55%, #050d0b 100%); position: relative; }
body::after { content: ''; position: absolute; inset: 16px; border: 1.2px solid rgba(201,164,92,.5); pointer-events: none; }
.gold { color: #d4b06a; }
.pg { position: absolute; background: #fff; box-shadow: 0 24px 50px rgba(0,0,0,.6), 0 5px 12px rgba(0,0,0,.45); }
.pg img { width: 100%; display: block; }
.kicker { font-family: 'Sans'; font-weight: 700; font-size: 15px; letter-spacing: .3em; color: #d4b06a; }
.h { font-family: 'Serif'; font-weight: 900; font-size: 42px; line-height: 1.25; letter-spacing: .06em; color: #eee5cf; }
.badge { display: inline-block; border: 1.2px solid #d4b06a; border-radius: 999px; padding: 7px 16px; font-family: 'Sans'; font-weight: 700; font-size: 16px; letter-spacing: .06em; }
ul.ticks { list-style: none; }
ul.ticks li { position: relative; padding-left: 26px; font-size: 19px; line-height: 1.45; margin-bottom: 18px; }
ul.ticks li::before { content: '◈'; position: absolute; left: 0; top: 1px; color: #d4b06a; font-size: 15px; }
ul.ticks b { display: block; font-family: 'Sans'; font-weight: 700; font-size: 19px; color: #d4b06a; letter-spacing: .06em; }
.label { position: absolute; font-family: 'Sans'; font-weight: 700; font-size: 14px; letter-spacing: .12em; text-align: center; color: #eee5cf; }
`;

const IMAGES = {
  '01-main': `
    <div style="position:absolute; left:64px; top:74px; writing-mode:vertical-rl; font-family:'Brush'; font-size:112px; line-height:1; letter-spacing:.04em">守秘人手札</div>
    <div class="gold" style="position:absolute; left:190px; top:84px; writing-mode:vertical-rl; font-family:'Sans'; font-weight:700; font-size:21px; letter-spacing:.32em">KP跑团主持规划本</div>
    <div class="pg" style="left:452px; top:128px; width:292px; transform:rotate(9deg)"><img src="${pg(16)}"></div>
    <div class="pg" style="left:392px; top:104px; width:310px; transform:rotate(4deg)"><img src="${pg(9)}"></div>
    <div class="pg" style="left:268px; top:70px; width:348px; transform:rotate(-3deg)"><img src="${pg(1)}"></div>
    <div style="position:absolute; left:56px; right:56px; bottom:52px">
      <div class="kicker" style="margin-bottom:14px">克苏鲁调查 · 恐怖跑团通用</div>
      <div style="display:flex; flex-wrap:wrap; gap:10px">
        <span class="badge">28页 A4 PDF</span><span class="badge">244条原创随机表</span><span class="badge">黑白打印省墨</span><span class="badge">可反复打印</span>
      </div>
    </div>`,

  '02-inside': `
    <div style="position:absolute; top:54px; width:100%; text-align:center">
      <div class="kicker">28 页 · 四个章节</div>
      <div class="h" style="margin-top:6px">内页一览</div>
    </div>
    ${[
      [3, '团设总览'], [4, '开团前沟通'], [5, '调查员名册'], [7, '模组构思'],
      [9, '线索网'], [11, '场景档案'], [13, 'NPC档案'], [16, '备团单'],
    ].map(([n, label], i) => {
      const col = i % 4, r = Math.floor(i / 4);
      const x = 62 + col * 173, y = 172 + r * 272;
      return `<div class="pg" style="left:${x}px; top:${y}px; width:152px"><img src="${pg(n)}"></div><div class="label" style="left:${x - 8}px; top:${y + 224}px; width:168px">${label}</div>`;
    }).join('')}
    <div style="position:absolute; bottom:48px; width:100%; text-align:center; font-size:17px; color:#cfc6b2">另有：状态追踪 · 真相时间线 · 线索清单 · 平面图 · 神话存在档案 · 手记道具<br>团务日志 · 追逐与战斗 · 理智记录 · 结团复盘 · 灵感库 · 笔记页</div>`,

  '03-scenario': `
    <div style="position:absolute; left:58px; top:96px; width:300px">
      <div class="kicker">模组设计</div>
      <div class="h" style="margin:12px 0 30px">真相与线索<br>一张图理清</div>
      <ul class="ticks">
        <li><b>真相时间线</b>先写下真正发生了什么</li>
        <li><b>线索网</b>每个结论至少三条线索</li>
        <li><b>线索清单</b>放在哪、怎么拿、拿没拿到</li>
      </ul>
    </div>
    <div class="pg" style="left:468px; top:210px; width:290px; transform:rotate(7deg)"><img src="${pg(10)}"></div>
    <div class="pg" style="left:362px; top:150px; width:345px; transform:rotate(-2deg)"><img src="${pg(9)}"></div>`,

  '04-sessions': `
    <div class="pg" style="left:52px; top:190px; width:290px; transform:rotate(-6deg)"><img src="${pg(19)}"></div>
    <div class="pg" style="left:140px; top:140px; width:335px; transform:rotate(2deg)"><img src="${pg(16)}"></div>
    <div style="position:absolute; left:510px; top:170px; width:240px">
      <div class="kicker">带团记录</div>
      <div class="h" style="margin:12px 0 30px">开团不慌<br>结团有据</div>
      <ul class="ticks">
        <li><b>备团单</b>二十分钟备好一次团</li>
        <li><b>理智记录</b>每次检定都记下来</li>
        <li><b>追逐与战斗</b>回合与顺序一目了然</li>
      </ul>
    </div>`,

  '05-tables': `
    <div class="pg" style="left:50px; top:200px; width:295px; transform:rotate(-5deg)"><img src="${pg(21)}"></div>
    <div class="pg" style="left:160px; top:150px; width:330px; transform:rotate(3deg)"><img src="${pg(25)}"></div>
    <div style="position:absolute; left:520px; top:150px; width:235px">
      <div class="kicker">灵感库</div>
      <div class="h" style="margin:12px 0 18px">244 条<br>原创随机表</div>
      <p style="font-size:18px; line-height:1.6; color:#cfc6b2">NPC 怪癖、诡异开场、怪谈传闻、神秘物品、不祥征兆、幕后真相、场景氛围、调查地点、线索形式。卡住的时候，掷个骰子。</p>
      <div style="margin-top:22px; border-left:2px solid #d4b06a; padding-left:14px; font-size:18px; line-height:1.7">“对猫有莫名的敬畏”<br>“一切都是某人的梦，<br>　而他快醒了”</div>
    </div>`,

  '06-howto': `
    <div style="position:absolute; top:70px; width:100%; text-align:center">
      <div class="kicker">电子版 · 虚拟商品</div>
      <div class="h" style="margin-top:8px">使用方式</div>
    </div>
    <div style="position:absolute; top:220px; left:60px; right:60px; display:grid; grid-template-columns:repeat(3,1fr); gap:30px; text-align:center">
      ${[
        ['一', '拍下', '发送下载链接，<br>PDF 马上到手'],
        ['二', '打印', 'A4 黑白打印，<br>家里或打印店都行'],
        ['三', '开团', '打孔放进活页夹，<br>常用页随时再打'],
      ].map(([n, t, d]) => `<div>
        <div style="width:96px; height:96px; margin:0 auto 22px; border:1.6px solid #d4b06a; border-radius:50%; display:grid; place-items:center; font-family:'Brush'; font-size:52px; color:#d4b06a">${n}</div>
        <div class="h" style="font-size:30px; margin-bottom:10px">${t}</div>
        <p style="font-size:17px; line-height:1.6; color:#cfc6b2">${d}</p></div>`).join('')}
    </div>
    <div style="position:absolute; bottom:70px; left:80px; right:80px; font-size:16px; line-height:1.9; color:#cfc6b2; text-align:center; border-top:1px solid rgba(201,164,92,.4); padding-top:22px">
      虚拟商品，发货后不支持无理由退款<br>仅限个人使用，请勿转卖或二次分享 · 原创设计，与任何规则出版商无关
    </div>`,
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 800, height: 800 }, deviceScaleFactor: 2 });
for (const [name, body] of Object.entries(IMAGES)) {
  const file = path.join(previewDir, `mock-${name}.html`);
  fs.writeFileSync(file, `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${body}</body></html>`);
  await page.goto(pathToFileURL(file).href);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth));
  await page.screenshot({ path: path.join(outDir, `${name}.jpg`), type: 'jpeg', quality: 90 });
  console.log(`wrote listing-images/${name}.jpg`);
}
await browser.close();
