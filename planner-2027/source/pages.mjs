// 2027 电子手帐 · 农历节气版：页面模板。所有页面互相超链接。
import { YEAR, MONTHS, WEEKDAYS, buildCalendar } from './data.mjs';

export const cal = buildCalendar();
const { days, weeks, months } = cal;
const monthOf = (n) => MONTHS[n - 1];
const pad = (n) => String(n).padStart(2, '0');
const WEEKDAY_FULL = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];

// ---------- 导航 ----------
function tabs(current) {
  return `<nav class="tabs">
    <a class="tab tab-y ${current === 'year' ? 'on' : ''}" href="#year">年</a>
    ${MONTHS.map((m) => `<a class="tab ${current === m.n ? 'on' : ''}" href="#m-${m.n}" style="--tc:${m.color}">${m.n}<small>月</small></a>`).join('')}
    <a class="tab tab-x ${current === 'goals' ? 'on' : ''}" href="#goals">目标</a>
    <a class="tab tab-x ${current === 'extras' ? 'on' : ''}" href="#extras">附录</a>
  </nav>`;
}

function crumbs(items, { prev, next } = {}) {
  const parts = items.map(([label, href]) => (href ? `<a href="${href}">${label}</a>` : `<span>${label}</span>`));
  return `<div class="crumbs">
    <div class="trail"><a href="#index">${YEAR}</a>${parts.map((p) => `<i>›</i>${p}`).join('')}</div>
    <div class="pn">${prev ? `<a href="${prev}" aria-label="上一页">‹</a>` : '<span></span>'}${next ? `<a href="${next}" aria-label="下一页">›</a>` : '<span></span>'}</div>
  </div>`;
}

function page(id, body, { month = null, cls = '', current = null } = {}) {
  const mc = month ? monthOf(month).color : '#6b645a';
  return `<section class="page ${cls}" id="${id}" style="--mc:${mc}">
    ${tabs(current ?? month)}
    <div class="content">${body}</div>
  </section>`;
}

// ---------- 小组件 ----------
// 法定节假日当天（调休安排以国务院公布为准）。
const HOLIDAYS = new Set(['元旦', '春节', '清明', '劳动节', '端午', '中秋', '国庆节']);
const tag = (t) => `<span class="tag ${HOLIDAYS.has(t) ? 'hol' : ''}">${t}</span>`;
const tagsOf = (d) => d.tags.map(tag).join('');
const lines = (n) => `<div class="lines">${'<i></i>'.repeat(n)}</div>`;
const fill = () => '<div class="lines fill" data-fill></div>';
const checkLines = (n) => `<ul class="checks">${'<li><b></b><i></i></li>'.repeat(n)}</ul>`;
const numLines = (n) => `<ol class="nums">${Array.from({ length: n }, (_, i) => `<li><b>${i + 1}</b><i></i></li>`).join('')}</ol>`;
const box = (title, inner, cls = '') => `<div class="box ${cls}"><h4>${title}</h4>${inner}</div>`;
const dayLink = (d, inner, cls = '') => (d.inYear ? `<a class="${cls}" href="#${d.id}">${inner}</a>` : `<span class="${cls} out">${inner}</span>`);

const ICONS = {
  sun: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4.5"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.2 5.2l1.8 1.8M17 17l1.8 1.8M5.2 18.8 7 17M17 7l1.8-1.8"/></svg>',
  cloud: '<svg viewBox="0 0 24 24"><path d="M7 18h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 18z"/></svg>',
  rain: '<svg viewBox="0 0 24 24"><path d="M7 14h10.5a4 4 0 0 0 .4-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 14z"/><path d="M8 17l-1 3M12 17l-1 3M16 17l-1 3"/></svg>',
  snow: '<svg viewBox="0 0 24 24"><path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5"/></svg>',
  cup: '<svg viewBox="0 0 24 24"><path d="M6 4h12l-1.6 16H7.6z"/><path d="M6.6 9h10.8"/></svg>',
};

// ---------- 封面与目录 ----------
function cover() {
  return `<section class="page cover" id="cover" style="--mc:#9b3b4a">
    <div class="cover-in">
      <p class="c-top">农历节气版 · 电子手帐</p>
      <div class="c-year">${YEAR}</div>
      <p class="c-gz">丁未羊年</p>
      <div class="c-rule"></div>
      <p class="c-sub">每一天，都有它的节气与名字</p>
      <div class="c-swatches">${MONTHS.map((m) => `<a href="#m-${m.n}" style="background:${m.color}" title="${m.zh} · ${m.colorName}"></a>`).join('')}</div>
      <a class="c-start" href="#index">开始使用 ›</a>
      <p class="c-apps">GoodNotes · Notability · 享做笔记 · Noteshelf</p>
    </div>
  </section>`;
}

function index() {
  const extras = [['cornell-1', '康奈尔笔记'], ['vocab-1', '单词本'], ['reading', '阅读记录'], ['films', '观影记录'], ['budget', '年度记账'], ['notes-lined', '横线笔记'], ['notes-grid', '方格笔记'], ['notes-dot', '点阵笔记'], ['notes-blank', '空白页']];
  const body = `${crumbs([['目录', null]])}
    <header class="ph"><h1>目录</h1><p class="sub">点击任意标题跳转；每一页右侧的标签也可以随时跳转。</p></header>
    <div class="toc">
      <div class="toc-col">
        <h4>全年</h4>
        <a href="#year"><span>2027 年历</span><em>全年一览</em></a>
        <a href="#goals"><span>年度目标</span><em>关键词 · 八大领域 · 愿望清单</em></a>
        <h4>十二个月</h4>
        ${MONTHS.map((m) => `<a href="#m-${m.n}"><span><b class="dot" style="background:${m.color}"></b>${m.zh}</span><em>本月色 · ${m.colorName}</em></a>`).join('')}
      </div>
      <div class="toc-col">
        <h4>附录</h4>
        ${extras.map(([id, t]) => `<a href="#${id}"><span>${t}</span></a>`).join('')}
        <h4>使用小贴士</h4>
        <ul class="tips">
          <li>每个月：月历 → 月计划与复盘 → 每周 → 每天，层层可点。</li>
          <li>日期、周数、月份标签都可以点击跳转。</li>
          <li>GoodNotes 中开启“只读模式”后点击链接最顺手。</li>
          <li>每一天都标注了农历、二十四节气和传统节日。</li>
          <li>2027 年放假调休安排公布后，将免费更新到新版本。</li>
        </ul>
      </div>
    </div>`;
  return page('index', body, { current: 'index' });
}

// ---------- 年历 ----------
function yearPage() {
  const mini = (mo) => {
    const lead = mo.days[0].weekday;
    const cells = [...Array(lead).fill(null), ...mo.days];
    return `<div class="mini">
      <a class="mini-h" href="#m-${mo.n}" style="color:${mo.color}">${mo.zh}<small>${mo.colorName}</small></a>
      <div class="mini-g">${WEEKDAYS.map((w) => `<span class="wd">${w}</span>`).join('')}${cells.map((d) => (d ? `<a href="#${d.id}" class="${d.tags.length ? (d.statutory ? 'hol' : 'tagd') : ''}">${d.d}</a>` : '<span></span>')).join('')}</div>
    </div>`;
  };
  const body = `${crumbs([['年历', null]], { next: '#goals' })}
    <header class="ph"><h1>${YEAR} 年历</h1><p class="sub">丁未羊年 · 圆点为节气与节日，红色为法定节假日当天</p></header>
    <div class="year-grid">${months.map(mini).join('')}</div>`;
  return page('year', body, { current: 'year' });
}

function goalsPage() {
  const areas = ['学习', '工作', '健康', '财务', '关系', '兴趣', '旅行', '成长'];
  const body = `${crumbs([['年度目标', null]], { prev: '#year', next: '#m-1' })}
    <header class="ph"><h1>年度目标</h1><p class="sub">写下这一年想成为的样子。</p></header>
    <div class="kw">${['关键词一', '关键词二', '关键词三'].map((k) => `<div><span>${k}</span></div>`).join('')}</div>
    <div class="areas">${areas.map((a) => box(a, lines(3))).join('')}</div>
    ${box('年度愿望清单', `<div class="wish">${checkLines(10)}${checkLines(10)}</div>`, 'grow')}`;
  return page('goals', body, { current: 'goals' });
}

// ---------- 月 ----------
function monthPage(mo) {
  const rows = mo.weeks.map((w) => `<tr>
      <th><a href="#w-${w.n}">W${pad(w.n)}</a></th>
      ${w.days.map((d) => `<td class="${d.m !== mo.n ? 'other' : ''} ${d.statutory && d.m === mo.n ? 'hol' : ''}">${d.m === mo.n ? dayLink(d, `<span class="n">${d.d}</span><span class="lu">${d.lunarShort}</span><span class="tg">${d.tags.slice(0, 2).map((t) => `<em>${t}</em>`).join('')}</span>`, 'cell') : `<span class="cell out"><span class="n">${d.d}</span></span>`}</td>`).join('')}
    </tr>`).join('');
  const body = `${crumbs([[mo.zh, null]], { prev: mo.n === 1 ? '#goals' : `#mp-${mo.n - 1}`, next: `#mp-${mo.n}` })}
    <header class="mh">
      <div><h1>${mo.zh}</h1><p class="en">${mo.en} ${YEAR}</p></div>
      <div class="mh-r">
        <p class="swatch"><b style="background:${mo.color}"></b>本月色 · ${mo.colorName}</p>
        <p class="jq">${mo.jieqi.map((j) => `${j.name} ${mo.n}月${j.d}日`).join(' · ')}</p>
      </div>
    </header>
    <table class="mcal"><thead><tr><th></th>${WEEKDAYS.map((w, i) => `<th class="${i > 4 ? 'we' : ''}">${w}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>
    <div class="two">${box('本月重点', lines(4))}${box('重要日期', lines(4))}</div>
    <p class="nav-note"><a href="#mp-${mo.n}">月计划与复盘 ›</a>${mo.weeks.map((w) => `<a href="#w-${w.n}">第${w.n}周</a>`).join('')}</p>`;
  return page(`m-${mo.n}`, body, { month: mo.n });
}

function monthPlanPage(mo) {
  const n = mo.days.length;
  const habits = Array.from({ length: 8 }, () => `<tr><td class="hn"></td>${Array.from({ length: n }, () => '<td></td>').join('')}</tr>`).join('');
  const body = `${crumbs([[mo.zh, `#m-${mo.n}`], ['计划与复盘', null]], { prev: `#m-${mo.n}`, next: `#w-${mo.weeks[0].n}` })}
    <header class="ph left"><h1>${mo.zh} · 计划与复盘</h1></header>
    <div class="two">${box('本月目标', numLines(5))}${box('本月想做的事', checkLines(5))}</div>
    ${box('习惯打卡', `<div class="habit-wrap"><table class="habit"><thead><tr><th class="hn">习惯</th>${mo.days.map((d) => `<th><a href="#${d.id}">${d.d}</a></th>`).join('')}</tr></thead><tbody>${habits}</tbody></table></div>`)}
    <div class="two">
      ${box('本月记账', `<div class="budget-top"><span>收入</span><i></i><span>支出</span><i></i><span>结余</span><i></i></div>
        <table class="mini-t">${['餐饮', '交通', '购物', '娱乐', '学习', '其他'].map((c) => `<tr><td>${c}</td><td></td></tr>`).join('')}</table>`)}
      ${box('月度复盘', `<p class="q">做得好的</p>${lines(2)}<p class="q">可以更好的</p>${lines(2)}<p class="q">下个月的重点</p>${lines(2)}`)}
    </div>
    ${box('随手记', fill(), 'grow')}`;
  return page(`mp-${mo.n}`, body, { month: mo.n });
}

// ---------- 周 ----------
function weekPage(w) {
  const first = w.days[0], last = w.days[6];
  const month = (w.days.find((d) => d.inYear) || first).m;
  const range = `${first.m}月${first.d}日 – ${last.m}月${last.d}日`;
  const card = (d) => `<div class="wday ${d.inYear ? '' : 'faded'}">
      <div class="wd-h">${dayLink(d, `<b>${d.d}</b><span>周${WEEKDAYS[d.weekday]}</span>`, 'wd-link')}<span class="wd-lu">${d.lunarFull}</span><span class="wd-tags">${tagsOf(d)}</span></div>
      ${fill()}
    </div>`;
  const tagged = w.days.filter((d) => d.tags.length && d.inYear);
  const body = `${crumbs([[monthOf(month).zh, `#m-${month}`], [`第${w.n}周`, null]], { prev: w.n > 1 ? `#w-${w.n - 1}` : `#mp-1`, next: w.n < weeks.length ? `#w-${w.n + 1}` : '#extras' })}
    <header class="wh"><h1>第 ${w.n} 周</h1><p>${range}${tagged.length ? ` · ${tagged.map((d) => d.tags.join('、')).join(' · ')}` : ''}</p></header>
    <div class="wgrid">${w.days.map(card).join('')}
      <div class="wday focus"><div class="wd-h"><b class="ft">本周重点</b></div>${checkLines(3)}<div class="wd-h sm"><b class="ft">本周待办</b></div>${checkLines(4)}</div>
    </div>`;
  return page(`w-${w.n}`, body, { month });
}

// ---------- 日 ----------
function dayPage(d, i) {
  const prev = i > 0 ? `#${days[i - 1].id}` : null;
  const next = i < days.length - 1 ? `#${days[i + 1].id}` : null;
  const pct = ((d.dayOfYear / days.length) * 100).toFixed(1);
  const hours = Array.from({ length: 18 }, (_, k) => `<li><span>${pad(k + 6)}:00</span><i></i></li>`).join('');
  const body = `${crumbs([[monthOf(d.m).zh, `#m-${d.m}`], [`第${d.week}周`, `#w-${d.week}`], [`${d.m}月${d.d}日`, null]], { prev, next })}
    <header class="dh">
      <div class="dnum">${pad(d.d)}</div>
      <div class="dmeta">
        <p class="d1">${d.m}月${d.d}日 · ${WEEKDAY_FULL[d.weekday]}</p>
        <p class="d2">农历${d.lunarFull} · ${d.ganzhiYear}</p>
        <p class="d3">${tagsOf(d)}</p>
      </div>
      <div class="dprog"><p>第 <b>${d.dayOfYear}</b> 天</p><div class="bar"><i style="width:${pct}%"></i></div><p>还剩 ${d.daysLeft} 天</p></div>
    </header>
    <div class="strip">
      <div><span class="lbl">心情</span>${'<b class="c"></b>'.repeat(5)}</div>
      <div class="wx"><span class="lbl">天气</span>${ICONS.sun}${ICONS.cloud}${ICONS.rain}${ICONS.snow}</div>
      <div class="water"><span class="lbl">喝水</span>${ICONS.cup.repeat(8)}</div>
    </div>
    <div class="dgrid">
      <div class="box tl"><h4>时间轴</h4><ol class="hours">${hours}</ol></div>
      <div class="side">
        ${box('今日三件事', numLines(3))}
        ${box('待办', checkLines(7))}
        ${box('今日小确幸', lines(3), 'grow')}
      </div>
    </div>
    ${box('笔记', fill(), 'grow')}`;
  return page(d.id, body, { month: d.m });
}

// ---------- 附录 ----------
function extras() {
  const tableFill = (heads, widths) => `<div class="tfill"><table class="grid-t"><colgroup>${widths.map((w) => `<col style="width:${w}">`).join('')}</colgroup><thead><tr>${heads.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody data-fill-rows><tr>${heads.map(() => '<td></td>').join('')}</tr></tbody></table></div>`;
  const cornell = (k) => page(`cornell-${k}`, `${crumbs([['附录', '#extras'], ['康奈尔笔记', null]])}
    <header class="ph left"><h1>康奈尔笔记</h1><div class="meta-row"><span>主题</span><i></i><span>日期</span><i></i></div></header>
    <div class="cornell"><div class="cue"><h4>线索 / 问题</h4>${fill()}</div><div class="main"><h4>笔记</h4>${fill()}</div></div>
    ${box('总结', lines(4))}`, { current: 'extras' });
  const vocab = (k) => page(`vocab-${k}`, `${crumbs([['附录', '#extras'], ['单词本', null]])}
    <header class="ph left"><h1>单词本</h1><div class="meta-row"><span>第　　天</span><i></i><span>日期</span><i></i></div></header>
    ${tableFill(['单词', '音标 / 词性', '释义', '例句', '✓'], ['20%', '16%', '24%', '33%', '7%'])}`, { current: 'extras' });
  const hub = page('extras', `${crumbs([['附录', null]])}
    <header class="ph"><h1>附录</h1><p class="sub">在 GoodNotes 中可以复制任意一页，想用多少就复制多少。</p></header>
    <div class="hub">${[['cornell-1', '康奈尔笔记', '上课 · 读书 · 会议'], ['vocab-1', '单词本', '考研 · 四六级 · 雅思'], ['reading', '阅读记录', '书名 · 评分 · 摘抄'], ['films', '观影记录', '电影 · 剧集 · 综艺'], ['budget', '年度记账', '每月收支总览'], ['notes-lined', '横线笔记', ''], ['notes-grid', '方格笔记', ''], ['notes-dot', '点阵笔记', ''], ['notes-blank', '空白页', '']].map(([id, t, s]) => `<a href="#${id}"><b>${t}</b><span>${s}</span></a>`).join('')}</div>`, { current: 'extras' });
  const reading = page('reading', `${crumbs([['附录', '#extras'], ['阅读记录', null]])}
    <header class="ph left"><h1>阅读记录</h1></header>${tableFill(['书名', '作者', '开始', '读完', '评分', '一句话'], ['22%', '14%', '10%', '10%', '12%', '32%'])}`, { current: 'extras' });
  const films = page('films', `${crumbs([['附录', '#extras'], ['观影记录', null]])}
    <header class="ph left"><h1>观影记录</h1></header>${tableFill(['片名', '日期', '类型', '评分', '短评'], ['26%', '12%', '12%', '12%', '38%'])}`, { current: 'extras' });
  const budget = page('budget', `${crumbs([['附录', '#extras'], ['年度记账', null]])}
    <header class="ph left"><h1>年度记账</h1></header>
    <table class="grid-t year-budget"><thead><tr><th>月份</th><th>收入</th><th>支出</th><th>结余</th><th>备注</th></tr></thead><tbody>${MONTHS.map((m) => `<tr><td><a href="#mp-${m.n}">${m.zh}</a></td><td></td><td></td><td></td><td></td></tr>`).join('')}<tr class="sum"><td>合计</td><td></td><td></td><td></td><td></td></tr></tbody></table>
    ${box('年度财务小结', fill(), 'grow')}`, { current: 'extras' });
  const note = (id, t, cls) => page(id, `${crumbs([['附录', '#extras'], [t, null]])}<div class="sheet ${cls}" ${cls === 'lined' ? 'data-fill' : ''} data-${cls}></div>`, { current: 'extras', cls: 'note-page' });
  return [hub, cornell(1), cornell(2), vocab(1), vocab(2), reading, films, budget,
    note('notes-lined', '横线笔记', 'lined'), note('notes-grid', '方格笔记', 'grid'), note('notes-dot', '点阵笔记', 'dot'), note('notes-blank', '空白页', 'blank')];
}

export function renderPages() {
  return [
    cover(), index(), yearPage(), goalsPage(),
    ...months.flatMap((mo) => [monthPage(mo), monthPlanPage(mo)]),
    ...weeks.map(weekPage),
    ...days.map(dayPage),
    ...extras(),
  ];
}
