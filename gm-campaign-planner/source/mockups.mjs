// Renders the Etsy listing photos (4:3, 2667x2000) from the page previews
// that build.mjs produces.
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
@font-face { font-family: 'Cinzel'; src: url('${font('Cinzel-700.ttf')}'); font-weight: 700; }
@font-face { font-family: 'Cinzel'; src: url('${font('Cinzel-800.ttf')}'); font-weight: 800; }
@font-face { font-family: 'Cinzel'; src: url('${font('Cinzel-400.ttf')}'); font-weight: 400; }
@font-face { font-family: 'EB Garamond'; src: url('${font('EBGaramond-400.ttf')}'); font-weight: 400; }
@font-face { font-family: 'EB Garamond'; src: url('${font('EBGaramond-Italic-400.ttf')}'); font-style: italic; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 1333px; height: 1000px; overflow: hidden; font-family: 'EB Garamond', serif; color: #f4ead7;
  background: radial-gradient(ellipse at 30% 20%, #5a1a17 0%, #2c0c0b 55%, #160606 100%); position: relative; }
body::after { content: ''; position: absolute; inset: 22px; border: 1.5px solid rgba(217,183,106,.55); pointer-events: none; }
.gold { color: #e1c07a; }
h1, h2, .cinzel { font-family: 'Cinzel', serif; letter-spacing: .03em; }
.pg { position: absolute; background: #fff; box-shadow: 0 30px 60px rgba(0,0,0,.55), 0 6px 14px rgba(0,0,0,.4); }
.pg img { width: 100%; display: block; }
.badge { display: inline-flex; align-items: center; gap: 10px; border: 1.5px solid #e1c07a; color: #f4ead7; border-radius: 999px;
  padding: 10px 22px; font-family: 'Cinzel', serif; font-weight: 700; font-size: 19px; letter-spacing: .06em; }
.kicker { font-family: 'Cinzel', serif; font-weight: 700; font-size: 20px; letter-spacing: .28em; text-transform: uppercase; color: #e1c07a; }
.lede { font-size: 30px; line-height: 1.3; font-style: italic; }
ul.ticks { list-style: none; }
ul.ticks li { position: relative; padding-left: 40px; font-size: 30px; line-height: 1.3; margin-bottom: 22px; }
ul.ticks li::before { content: '◆'; position: absolute; left: 0; top: 2px; color: #e1c07a; font-size: 22px; }
ul.ticks b { font-family: 'Cinzel', serif; font-weight: 700; font-size: 25px; color: #e1c07a; letter-spacing: .03em; display: block; }
.label { position: absolute; font-family: 'Cinzel', serif; font-weight: 700; font-size: 15px; letter-spacing: .08em; color: #f4ead7; text-align: center; }
`;

const IMAGES = {
  '01-cover': `
    <div style="position:absolute; left:92px; top:200px; width:600px;">
      <div class="kicker">Printable · Any fantasy TTRPG</div>
      <h1 style="font-size:40px; font-weight:400; font-family:'EB Garamond'; font-style:italic; margin-top:30px; color:#f4ead7">The Game Master's</h1>
      <h1 class="gold" style="font-size:86px; font-weight:800; line-height:1.02; margin-top:6px">Campaign<br>Planner</h1>
      <p class="lede" style="margin-top:28px; width:520px">35 pages to plan your world, run your sessions and remember everything.</p>
      <div style="display:flex; flex-wrap:wrap; gap:14px; margin-top:40px; width:560px">
        <span class="badge">35 pages</span><span class="badge">236 roll-table entries</span><span class="badge">US Letter + A4</span><span class="badge">Instant download</span>
      </div>
    </div>
    <div class="pg" style="left:860px; top:205px; width:420px; transform:rotate(9deg)"><img src="${pg(29)}"></div>
    <div class="pg" style="left:790px; top:165px; width:450px; transform:rotate(4deg)"><img src="${pg(21)}"></div>
    <div class="pg" style="left:650px; top:118px; width:505px; transform:rotate(-3deg)"><img src="${pg(1)}"></div>`,

  '02-whats-inside': `
    <div style="position:absolute; top:62px; width:100%; text-align:center">
      <div class="kicker">35 printable pages</div>
      <h2 class="gold" style="font-size:58px; margin-top:8px">What's Inside</h2>
    </div>
    ${[
      [3, 'Campaign Overview'], [4, 'Session Zero'], [9, 'World Map'], [11, 'Locations'], [15, 'Factions'], [16, 'Faction Clocks'],
      [18, 'NPC Cards'], [19, 'Villain Dossier'], [21, 'Session Prep'], [22, 'Session Log'], [24, 'Combat Tracker'], [29, 'NPC Quirks d100'],
    ].map(([n, label], i) => {
      const col = i % 6, r = Math.floor(i / 6);
      const x = 88 + col * 196, y = 225 + r * 370;
      return `<div class="pg" style="left:${x}px; top:${y}px; width:172px"><img src="${pg(n)}"></div><div class="label" style="left:${x - 10}px; top:${y + 236}px; width:192px">${label}</div>`;
    }).join('')}
    <div style="position:absolute; bottom:52px; width:100%; text-align:center; font-size:27px; font-style:italic">+ Campaign Arc, Regions, Settlements, Taverns, Encounters, Loot, Quests, Rumors, Roll Tables & Notes</div>`,

  '03-session-prep': `
    <div class="pg" style="left:95px; top:70px; width:640px; transform:rotate(-2deg)"><img src="${pg(21)}"></div>
    <div style="position:absolute; left:810px; top:150px; width:440px">
      <div class="kicker">Session Prep</div>
      <h2 class="gold" style="font-size:52px; line-height:1.08; margin:14px 0 36px">Prep a session in 20 minutes</h2>
      <ul class="ticks">
        <li><b>Strong opening</b>Start every session with momentum.</li>
        <li><b>10 secrets &amp; clues</b>Reveal them in any order the players find them.</li>
        <li><b>Scenes, NPCs &amp; loot</b>Everything you need on one page.</li>
        <li><b>Session log</b>Never forget what happened last time.</li>
      </ul>
    </div>`,

  '04-world': `
    <div style="position:absolute; top:62px; width:100%; text-align:center">
      <div class="kicker">World Building</div>
      <h2 class="gold" style="font-size:58px; margin-top:8px">Build a world that moves</h2>
    </div>
    <div class="pg" style="left:120px; top:240px; width:360px; transform:rotate(-5deg)"><img src="${pg(9)}"></div>
    <div class="pg" style="left:487px; top:215px; width:360px; transform:rotate(0deg); z-index:2"><img src="${pg(16)}"></div>
    <div class="pg" style="left:855px; top:240px; width:360px; transform:rotate(5deg)"><img src="${pg(11)}"></div>
    <div style="position:absolute; bottom:56px; width:100%; text-align:center; font-size:29px; font-style:italic">Hex world map · Regions · Locations · Settlements · Taverns · Factions with progress clocks</div>`,

  '05-npcs': `
    <div style="position:absolute; left:92px; top:170px; width:470px">
      <div class="kicker">The Cast</div>
      <h2 class="gold" style="font-size:54px; line-height:1.08; margin:14px 0 36px">NPCs &amp; villains your players will remember</h2>
      <ul class="ticks">
        <li><b>NPC cards</b>Look, voice, wants and secrets, 4 per page.</li>
        <li><b>Villain dossier</b>A 5-step plan and what happens if the heroes do nothing.</li>
        <li><b>Custom creatures</b>Homebrew monsters for any system.</li>
      </ul>
    </div>
    <div class="pg" style="left:590px; top:150px; width:390px; transform:rotate(-4deg)"><img src="${pg(18)}"></div>
    <div class="pg" style="left:860px; top:185px; width:410px; transform:rotate(4deg)"><img src="${pg(19)}"></div>`,

  '06-roll-tables': `
    <div class="pg" style="left:75px; top:175px; width:405px; transform:rotate(-5deg)"><img src="${pg(30)}"></div>
    <div class="pg" style="left:345px; top:130px; width:425px; transform:rotate(2deg)"><img src="${pg(32)}"></div>
    <div style="position:absolute; left:830px; top:180px; width:430px">
      <div class="kicker">Bonus: Instant Inspiration</div>
      <h2 class="gold" style="font-size:54px; line-height:1.08; margin:14px 0 30px">236 ready-to-roll entries</h2>
      <p style="font-size:28px; line-height:1.35">d100 NPC quirks, tavern names, rumors, house specials, villain motives, plot twists, calling cards, strange treasures, session openers and omens.</p>
      <div style="margin-top:34px; border-left:3px solid #e1c07a; padding-left:22px; font-size:30px; font-style:italic; line-height:1.35">"Has an unexplained fear of ducks."<br>"The dungeon is inside something alive."</div>
    </div>`,

  '07-how-it-works': `
    <div style="position:absolute; top:80px; width:100%; text-align:center">
      <div class="kicker">Instant Digital Download</div>
      <h2 class="gold" style="font-size:58px; margin-top:8px">How it works</h2>
    </div>
    <div style="position:absolute; top:330px; left:110px; right:110px; display:grid; grid-template-columns:repeat(3,1fr); gap:60px; text-align:center">
      ${[
        ['1', 'Download', 'Get your PDFs instantly after purchase: US Letter and A4 included.'],
        ['2', 'Print', 'Print at home or at any print shop. Black &amp; white friendly.'],
        ['3', 'Play', 'Use it at your table. Reprint any page as often as you need.'],
      ].map(([n, t, d]) => `<div>
        <div class="cinzel gold" style="width:120px; height:120px; margin:0 auto 26px; border:2px solid #e1c07a; transform:rotate(45deg); display:grid; place-items:center"><span style="transform:rotate(-45deg); font-size:48px; font-weight:800">${n}</span></div>
        <h2 class="gold" style="font-size:38px; margin-bottom:14px">${t}</h2>
        <p style="font-size:28px; line-height:1.35">${d}</p></div>`).join('')}
    </div>
    <div style="position:absolute; bottom:80px; width:100%; text-align:center; font-family:'Cinzel'; font-weight:700; font-size:22px; letter-spacing:.14em; color:#e1c07a">ANY FANTASY TTRPG · DIGITAL FILE, NOTHING IS SHIPPED</div>`,
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1333, height: 1000 }, deviceScaleFactor: 2 });
for (const [name, body] of Object.entries(IMAGES)) {
  const file = path.join(previewDir, `mock-${name}.html`);
  fs.writeFileSync(file, `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${body}</body></html>`);
  await page.goto(pathToFileURL(file).href);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth));
  await page.screenshot({ path: path.join(outDir, `${name}.jpg`), type: 'jpeg', quality: 90 });
  console.log(`wrote listing-images/${name}.jpg`);
}
await browser.close();
