// 守秘人手札：页面模板。每页是一个返回 HTML 的函数，由 build.mjs 组装并打印。
import {
  NPC_QUIRKS, OPENERS, LEGENDS, ITEMS, OMENS, TRUTHS, ATMOSPHERE, PLACES, CLUE_FORMS,
} from './content.mjs';

export const TITLE = '守秘人手札';

// ---------- 小组件 ----------
export const EYE = (cls = 'eye') => `<svg class="${cls}" viewBox="0 0 100 100" aria-hidden="true">
  <circle cx="50" cy="50" r="46"/>
  <circle cx="50" cy="50" r="39" class="thin"/>
  <path d="M12 50 Q50 14 88 50 Q50 86 12 50 Z"/>
  <circle cx="50" cy="50" r="15"/>
  <ellipse cx="50" cy="50" rx="4" ry="11" class="fillk"/>
  ${Array.from({ length: 24 }, (_, i) => {
    const a = (i / 24) * Math.PI * 2;
    const r1 = 39, r2 = i % 2 ? 42.5 : 45;
    return `<path d="M${(50 + r1 * Math.cos(a)).toFixed(2)} ${(50 + r1 * Math.sin(a)).toFixed(2)} L${(50 + r2 * Math.cos(a)).toFixed(2)} ${(50 + r2 * Math.sin(a)).toFixed(2)}" class="thin"/>`;
  }).join('')}
</svg>`;

const divider = `<svg class="divider" viewBox="0 0 240 12" aria-hidden="true"><path d="M0 6 H100 M140 6 H240"/><circle cx="120" cy="6" r="4.2"/><circle cx="120" cy="6" r="1.6" class="fillk"/><circle cx="106" cy="6" r="1.4" class="fillk"/><circle cx="134" cy="6" r="1.4" class="fillk"/></svg>`;

const f = (label, cls = '') => `<div class="f ${cls}"><span class="fl">${label}</span><span class="fu"></span></div>`;
const row = (...items) => `<div class="row">${items.join('')}</div>`;
const lines = (n) => `<div class="lines">${'<div class="ln"></div>'.repeat(n)}</div>`;
const fillLines = () => '<div class="lines fill" data-fill="lines"></div>';
const box = (title, inner, cls = '') =>
  `<div class="box ${cls}"><div class="bt">${title}</div><div class="bi">${inner}</div></div>`;
const cols = (n, ...items) => `<div class="cols c${n}">${items.map((i) => `<div class="col">${i}</div>`).join('')}</div>`;
const colsGrow = (n, ...items) => `<div class="cols c${n} grow">${items.map((i) => `<div class="col">${i}</div>`).join('')}</div>`;
const checks = (items, cls = '') =>
  `<ul class="checks ${cls}">${items.map((i) => `<li><span class="cb"></span><span>${i}</span></li>`).join('')}</ul>`;
const checkLines = (n) =>
  `<ul class="checklines">${Array.from({ length: n }, () => '<li><span class="cb"></span><span class="fu"></span></li>').join('')}</ul>`;
const numLines = (n) =>
  `<ol class="numlines">${Array.from({ length: n }, (_, i) => `<li><span class="num">${i + 1}.</span><span class="fu"></span></li>`).join('')}</ol>`;
const scale = (left, right, n = 5) =>
  `<div class="scale"><span>${left}</span>${'<span class="dot"></span>'.repeat(n)}<span>${right}</span></div>`;

function table(headers, { rows = 0, fill = false, widths = [], cls = '', first = null } = {}) {
  const colgroup = widths.length ? `<colgroup>${widths.map((w) => `<col style="width:${w}">`).join('')}</colgroup>` : '';
  const tr = (i) => `<tr>${headers.map((_, c) => `<td>${c === 0 && first ? first(i) : ''}</td>`).join('')}</tr>`;
  const body = Array.from({ length: rows }, (_, i) => tr(i)).join('');
  return `<div class="tw ${fill ? 'fill' : ''} ${cls}"><table>${colgroup}<thead><tr>${headers.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody ${fill ? 'data-fill="rows"' : ''}>${body || (fill ? tr(0) : '')}</tbody></table></div>`;
}

function page({ section, title, sub, body, cls = '' }, n) {
  return `<section class="page ${cls}">
  <div class="frame">
    <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
    <header class="ph">
      <div class="kicker">${section}</div>
      <h1>${title}</h1>
      ${sub ? `<p class="sub">${sub}</p>` : ''}
      ${divider}
    </header>
    <div class="pb">${body}</div>
    <footer class="pf"><span>${TITLE} · KP 跑团主持规划本</span>${EYE('eye tiny')}<span>${n}</span></footer>
  </div>
</section>`;
}

function rollTable(die, title, entries, { split = 1, start = 1 } = {}) {
  const per = Math.ceil(entries.length / split);
  const parts = Array.from({ length: split }, (_, s) => entries.slice(s * per, (s + 1) * per).map((e, i) => ({ n: start + s * per + i, e })));
  const pad = die === 'd100' ? 2 : String(entries.length).length;
  const label = (n) => (die === 'd100' && n === 100 ? '00' : String(n).padStart(pad, '0'));
  return `<div class="roll" style="flex-grow:${per}">
    <div class="roll-head"><span class="seal">${die.toUpperCase()}</span><h2>${title}</h2></div>
    <div class="cols c${split}">${parts.map((part) => `<table class="rt"><tbody>${part.map(({ n, e }) => `<tr><td class="rn">${label(n)}</td><td>${e}</td></tr>`).join('')}</tbody></table>`).join('')}</div>
  </div>`;
}

function clueWeb() {
  // 中心“真相”+ 8 个结论/线索节点，其余空间留给玩家自己连线。
  const nodes = Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
    return { x: 50 + 36 * Math.cos(a), y: 50 + 38 * Math.sin(a) };
  });
  return `<div class="web">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      ${nodes.map((p) => `<line x1="50" y1="50" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" class="spoke"/>`).join('')}
    </svg>
    <div class="node core" style="left:50%;top:50%"><span>核心真相</span></div>
    ${nodes.map((p, i) => `<div class="node" style="left:${p.x.toFixed(1)}%;top:${p.y.toFixed(1)}%"><span>结论 ${i + 1}</span></div>`).join('')}
  </div>`;
}

// ---------- 各页 ----------
const S1 = '壹 · 团务';
const S2 = '贰 · 模组设计';
const S3 = '叁 · 跑团记录';
const S4 = '肆 · 灵感库';
const S5 = '笔记';

const cover = () => `<section class="page cover">
  <div class="frame">
    <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
    <div class="cover-inner">
      <p class="kicker">调查 · 恐怖题材跑团通用</p>
      <div class="cover-center">
        ${EYE('eye cover-eye')}
        <h1 class="cover-title">守秘人手札</h1>
        <p class="cover-sub">KP 跑团主持规划本</p>
        ${divider}
        <p class="tagline">真相藏在线索里，线索藏在这本手札里。</p>
      </div>
      <div class="cover-fields">
        ${f('模组 / 团名')}
        ${row(f('守秘人'), f('开团日期'))}
      </div>
    </div>
  </div>
</section>`;

const PAGES = [
  // 2
  {
    section: '开始之前',
    title: '使用说明',
    sub: '需要哪页打哪页，常用页可以反复打印。',
    body: `<p class="lead">这本手札把一场跑团需要的东西收在一起：团设、调查员、模组的真相与线索、每一次开团的准备和记录。它不绑定任何规则，适用于各类克苏鲁风格的调查、恐怖跑团。</p>
      ${cols(2,
        box('备团五步', `<ol class="steps">
          <li><b>回顾：</b>翻一翻上次的团务日志和线索清单。</li>
          <li><b>开场：</b>设计一个能立刻抓住玩家的开场。</li>
          <li><b>线索：</b>列出本次可能揭露的线索，不限顺序。</li>
          <li><b>人和地点：</b>准备人物和场景，而不是写死剧情。</li>
          <li><b>记录：</b>结团后马上写日志，趁记忆还新鲜。</li>
        </ol>`),
        box('使用建议', `<ul class="tips">
          <li>A4 打印后打孔，放进活页夹，按章节贴上索引。</li>
          <li>备团单、团务日志、理智记录可以多打几份。</li>
          <li>用铅笔写：玩家一上桌，剧情随时会变。</li>
          <li>线上团也可以打印出来放在手边。</li>
          <li>卡住的时候，去灵感库掷一次骰。</li>
        </ul>`),
      )}
      ${box('目录', '<div class="toc" data-toc></div>', 'grow')}`,
  },
  // 3
  {
    section: S1,
    title: '团设总览',
    body: `${row(f('团名 / 模组', 'w2'), f('规则 / 版本'))}
      ${row(f('时代背景'), f('主要地点'), f('预计时长'))}
      ${box('基调', checks(['正统恐怖', '调查推理', '都市怪谈', '民俗恐怖', '心理惊悚', '动作冒险', '日常克系', '密室解谜'], 'grid4'))}
      ${box('一句话简介', lines(2))}
      ${cols(2, box('核心谜团', lines(4)), box('幕后真相', lines(4)))}
      ${box('三件一定会发生的事', numLines(3))}
      ${cols(2, box('主题与灵感', lines(3)), box('调查员的切入点', lines(3)))}
      ${box('可能的结局', fillLines(), 'grow')}`,
  },
  // 4
  {
    section: S1,
    title: '开团前沟通',
    sub: '开团之前先对齐预期，跑起来才顺。',
    body: `${box('开团前确认', checks([
        '介绍模组题材和基调',
        '确认开团时间和频率',
        '说明规则版本和房规',
        '讨论雷点和安全措施',
        '确认调查员之间的关系',
        '约定角色死亡（撕卡）规则',
        '约定缺席怎么处理',
        '建群，准备骰子或骰娘',
      ], 'grid2'))}
      ${row(f('线上 / 线下'), f('开团时间'), f('单次时长'))}
      ${row(f('群号 / 地点', 'w2'), f('骰子 / 工具'))}
      ${cols(2,
        box('红线：绝不出现', table([''], { rows: 5, cls: 'plain' })),
        box('淡化：一笔带过', table([''], { rows: 5, cls: 'plain' })),
      )}
      ${box('安全工具', checks(['随时可以暂停', 'X 卡', '中场询问感受', '私聊反馈', '其他：＿＿＿＿'], 'grid3'))}
      ${box('房规', fillLines(), 'grow')}`,
  },
  // 5
  {
    section: S1,
    title: '调查员名册',
    body: `<div class="grid g2x3">${Array.from({ length: 6 }, () => `<div class="card">
        ${f('玩家')}${f('调查员')}${row(f('职业'), f('年龄'))}${f('背景关联')}${f('秘密 / 羁绊')}${f('联系方式')}
      </div>`).join('')}</div>
      ${row(f('调查小队名称'), f('集合地点'))}`,
  },
  // 6
  {
    section: S1,
    title: '调查员状态追踪',
    sub: '每次开团前后各填一行，状态变化一目了然。',
    body: table(['场次', '调查员', '理智 始 / 现', '生命', '幸运', '伤势 / 症状', '重要物品'], { fill: true, widths: ['8%', '16%', '14%', '9%', '9%', '22%', '22%'] }),
  },
  // 7
  {
    section: S2,
    title: '模组构思',
    body: `${row(f('模组名', 'w2'), f('类型'))}
      ${row(f('人数'), f('时长'), f('适合'))}
      ${box('难度', checks(['新手友好', '普通', '困难', '致命'], 'grid4'))}
      ${box('开场钩子：调查员为什么会卷进来', lines(2))}
      ${box('幕后真相：到底发生了什么', lines(4))}
      ${cols(2, box('幕后黑手想要什么', lines(3)), box('如果调查员什么都不做', lines(3)))}
      ${box('结局条件', `${f('好结局')}${f('坏结局')}${f('真结局')}`)}
      ${box('灵感来源与备注', fillLines(), 'grow')}`,
  },
  // 8
  {
    section: S2,
    title: '真相时间线',
    sub: '先写下真正发生了什么，线索就知道该放在哪里。',
    body: table(['时间', '真正发生了什么', '谁知道', '留下的痕迹'], { fill: true, widths: ['14%', '40%', '16%', '30%'] }),
  },
  // 9
  {
    section: S2,
    title: '线索网',
    sub: '每一个关键结论，至少准备三条能通往它的线索。',
    body: `${clueWeb()}
      ${row(f('核心真相', 'w3'))}`,
  },
  // 10
  {
    section: S2,
    title: '线索清单',
    body: table(['编号', '线索', '地点 / 来源', '指向结论', '获取方式', '已得'], { fill: true, widths: ['8%', '28%', '18%', '14%', '22%', '10%'], cls: 'with-check' }),
  },
  // 11
  {
    section: S2,
    title: '场景档案',
    body: `${row(f('地点', 'w2'), f('类型'))}
      ${row(f('所属区域'), f('主人 / 控制者'))}
      ${box('第一印象（可直接念给玩家）', lines(3))}
      ${cols(3, box('看到', lines(2)), box('听到', lines(2)), box('闻到', lines(2)))}
      ${cols(2, box('可调查之处', lines(4)), box('隐藏线索与检定', lines(4)))}
      ${box('危险与遭遇', lines(2))}
      ${box('草图', '<div class="dots fill" data-dots></div>', 'grow')}`,
  },
  // 12
  {
    section: S2,
    title: '平面图',
    body: `<div class="mapbox fill" data-squares></div>
      ${row(f('地点'), f('比例：一格 ='))}
      ${row(f('图例', 'w3'))}`,
  },
  // 13
  {
    section: S2,
    title: 'NPC 档案',
    body: `<div class="grid g2x2">${Array.from({ length: 4 }, () => `<div class="card">
        <div class="npc-top"><div class="portrait"></div><div class="npc-id">${f('姓名')}${f('身份')}${f('常在')}</div></div>
        ${f('外貌')}${f('说话方式')}${f('知道什么')}${f('隐瞒什么')}${f('与调查员的关系')}
        ${scale('敌对', '友善')}
      </div>`).join('')}</div>`,
  },
  // 14
  {
    section: S2,
    title: '神话存在档案',
    sub: '怪物、神祇或说不清的东西。',
    body: `<div class="stack2">${Array.from({ length: 2 }, () => `<div class="card grow">
        ${row(f('名称', 'w2'), f('类型'))}
        ${row(f('生命'), f('护甲'), f('移动'), f('目击理智损失'))}
        ${f('出现的征兆')}${f('外观描述')}
        ${colsGrow(2, `<div class="mini">能力</div>${fillLines()}`, `<div class="mini">弱点 / 对抗方式</div>${fillLines()}`)}
        ${row(f('行为与目的'), f('相关线索'))}
      </div>`).join('')}</div>`,
  },
  // 15
  {
    section: S2,
    title: '手记与道具',
    sub: '信件、日记、剪报：先在这里写好，再誊抄给玩家。',
    body: `<div class="stack2">${Array.from({ length: 2 }, () => `<div class="card grow handout">
        ${row(f('道具名称', 'w2'), f('类型：信件 / 日记 / 剪报'))}
        ${row(f('何时交给玩家'), f('揭示的线索'))}
        <div class="paper">${fillLines()}</div>
      </div>`).join('')}</div>`,
  },
  // 16
  {
    section: S3,
    title: '备团单',
    body: `${row(f('第　　次'), f('日期'), f('参与玩家', 'w2'))}
      ${box('上次回顾', lines(2))}
      ${box('开场', lines(2))}
      ${box('本次场景', checkLines(3))}
      ${box('本次可能揭露的线索', `<div class="cols c2">${checkLines(4)}${checkLines(4)}</div>`)}
      ${cols(2, box('关键 NPC', lines(3)), box('可能的检定', lines(3)))}
      ${cols(2, box('惊吓点设计', lines(3)), box('奖励与收获', lines(3)))}
      ${box('结尾钩子', fillLines(), 'grow')}`,
  },
  // 17
  {
    section: S3,
    title: '团务日志',
    body: `${row(f('第　　次'), f('日期'), f('游戏内时间'))}
      ${box('发生了什么', lines(7))}
      ${cols(2, box('获得的线索', lines(3)), box('遇到的人', lines(3)))}
      ${cols(2, box('理智与伤势变化', lines(3)), box('获得的物品', lines(3)))}
      ${box('名场面与语录', lines(2))}
      ${box('下次要准备的', fillLines(), 'grow')}`,
  },
  // 18
  {
    section: S3,
    title: '追逐与战斗',
    body: `<div class="chase"><span class="mini">追逐进度</span>${Array.from({ length: 10 }, (_, i) => `<span class="cbox">${i + 1}</span>`).join('<span class="arrow">›</span>')}</div>
      ${row(f('追逐者'), f('被追者'), f('地形 / 障碍'))}
      <div class="rounds"><span class="mini">回合</span>${Array.from({ length: 12 }, (_, i) => `<span class="rbox">${i + 1}</span>`).join('')}</div>
      ${table(['顺序', '名称', '生命', '护甲', '状态', '备注'], { fill: true, widths: ['9%', '23%', '20%', '10%', '18%', '20%'] })}`,
  },
  // 19
  {
    section: S3,
    title: '理智记录',
    sub: '每一次理智检定都值得记下来，它就是这场团的恐怖程度。',
    body: table(['场次', '调查员', '看到了什么', '损失', '剩余', '症状 / 后遗症'], { fill: true, widths: ['8%', '15%', '33%', '9%', '9%', '26%'] }),
  },
  // 20
  {
    section: S3,
    title: '结团复盘',
    body: `${row(f('模组 / 团名', 'w2'), f('结团日期'))}
      ${box('达成的结局', checks(['好结局', '普通结局', '坏结局', '真结局', '全灭'], 'grid5'))}
      ${box('调查员结局', table(['调查员', '生还', '疯狂', '死亡', '失踪', '备注'], { rows: 6, widths: ['24%', '9%', '9%', '9%', '9%', '40%'], cls: 'with-checks' }))}
      ${cols(2, box('高光时刻', lines(4)), box('玩家反馈', lines(4)))}
      ${box('下次可以改进的', fillLines(), 'grow')}`,
  },
  // 21
  { section: S4, title: 'NPC 特征与怪癖', sub: '掷 d100，让任何一个路人都让人过目不忘。', body: rollTable('d100', '01–50', NPC_QUIRKS.slice(0, 50), { split: 2 }), cls: 'inspo' },
  // 22
  { section: S4, title: 'NPC 特征与怪癖', sub: '续。', body: rollTable('d100', '51–100', NPC_QUIRKS.slice(50), { split: 2, start: 51 }), cls: 'inspo' },
  // 23
  { section: S4, title: '开场与传闻', body: `${rollTable('d20', '诡异开场', OPENERS, { split: 2 })}${rollTable('d20', '怪谈传闻', LEGENDS, { split: 2 })}`, cls: 'inspo' },
  // 24
  { section: S4, title: '物品与征兆', body: `${rollTable('d20', '神秘物品', ITEMS, { split: 2 })}${rollTable('d12', '不祥征兆', OMENS, { split: 2 })}`, cls: 'inspo' },
  // 25
  { section: S4, title: '真相与氛围', body: `${rollTable('d20', '幕后真相', TRUTHS, { split: 2 })}${rollTable('d12', '场景氛围', ATMOSPHERE, { split: 2 })}`, cls: 'inspo' },
  // 26
  { section: S4, title: '地点与线索', body: `${rollTable('d20', '调查地点', PLACES, { split: 2 })}${rollTable('d20', '线索形式', CLUE_FORMS, { split: 2 })}`, cls: 'inspo' },
  // 27
  { section: S5, title: '笔记', body: fillLines() },
  // 28
  { section: S5, title: '笔记', body: '<div class="dots fill" data-dots></div>' },
];

export function renderPages() {
  return [cover(), ...PAGES.map((p, i) => page(p, i + 2))];
}

export function contents() {
  const seen = new Map();
  PAGES.forEach((p, i) => {
    if (i === 0 || seen.has(p.title)) return;
    seen.set(p.title, { title: p.title, n: i + 2, section: p.section });
  });
  return [...seen.values()];
}

export const PAGE_COUNT = PAGES.length + 1;
// 备团单在 PAGES 中的位置（封面为第 1 页），用于生成免费试用页。
export const SAMPLE_PAGE = PAGES.findIndex((p) => p.title === '备团单') + 1;
