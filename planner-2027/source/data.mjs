// 2027 日历数据：公历、农历、节气、节日、周次。农历与节气来自 lunar-javascript。
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { Solar } = require('lunar-javascript');

export const YEAR = 2027;

// 每月一个中国传统色（名称 + 用于强调的中间调）。
export const MONTHS = [
  { n: 1, zh: '一月', en: 'JANUARY', color: '#3d4f6b', colorName: '黛蓝' },
  { n: 2, zh: '二月', en: 'FEBRUARY', color: '#c0505e', colorName: '海棠红' },
  { n: 3, zh: '三月', en: 'MARCH', color: '#6e8b5f', colorName: '竹青' },
  { n: 4, zh: '四月', en: 'APRIL', color: '#8a76a8', colorName: '丁香紫' },
  { n: 5, zh: '五月', en: 'MAY', color: '#c4523f', colorName: '石榴红' },
  { n: 6, zh: '六月', en: 'JUNE', color: '#3f8f8f', colorName: '天水碧' },
  { n: 7, zh: '七月', en: 'JULY', color: '#5f8f4e', colorName: '荷叶绿' },
  { n: 8, zh: '八月', en: 'AUGUST', color: '#a88338', colorName: '秋香' },
  { n: 9, zh: '九月', en: 'SEPTEMBER', color: '#b0703a', colorName: '琥珀' },
  { n: 10, zh: '十月', en: 'OCTOBER', color: '#a8452e', colorName: '枫红' },
  { n: 11, zh: '十一月', en: 'NOVEMBER', color: '#5a6f7c', colorName: '苍青' },
  { n: 12, zh: '十二月', en: 'DECEMBER', color: '#9b3b4a', colorName: '胭脂' },
];

export const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

const SOLAR_FESTIVALS = {
  '1-1': '元旦', '2-14': '情人节', '3-8': '妇女节', '3-12': '植树节', '5-1': '劳动节', '5-4': '青年节',
  '6-1': '儿童节', '7-1': '建党节', '8-1': '建军节', '9-10': '教师节', '10-1': '国庆节',
  '12-24': '平安夜', '12-25': '圣诞节',
};
const LUNAR_FESTIVAL_NAMES = {
  春节: '春节', 元宵节: '元宵', 龙头节: '龙抬头', 端午节: '端午', 七夕节: '七夕', 中元节: '中元',
  中秋节: '中秋', 重阳节: '重阳', 腊八节: '腊八', 除夕: '除夕',
};
// 法定节假日当天（调休安排以国务院公布为准）。
const STATUTORY = new Set(['元旦', '春节', '清明', '劳动节', '端午', '中秋', '国庆节']);

const pad = (n) => String(n).padStart(2, '0');
export const dayId = (y, m, d) => `d-${y}${pad(m)}${pad(d)}`;

function nthWeekday(y, m, weekday, nth) {
  // weekday: 0=Sunday；返回该月第 nth 个星期几的日期
  const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
  return 1 + ((weekday - first + 7) % 7) + (nth - 1) * 7;
}

function describe(date) {
  const y = date.getUTCFullYear(), m = date.getUTCMonth() + 1, d = date.getUTCDate();
  const solar = Solar.fromYmd(y, m, d);
  const lunar = solar.getLunar();
  const festivals = [];
  const jieqi = lunar.getJieQi() || '';

  for (const f of lunar.getFestivals()) if (LUNAR_FESTIVAL_NAMES[f]) festivals.push(LUNAR_FESTIVAL_NAMES[f]);
  if (lunar.getMonth() === 12 && lunar.getDay() === 23) festivals.push('小年');
  if (SOLAR_FESTIVALS[`${m}-${d}`]) festivals.push(SOLAR_FESTIVALS[`${m}-${d}`]);
  if (m === 5 && d === nthWeekday(y, 5, 0, 2)) festivals.push('母亲节');
  if (m === 6 && d === nthWeekday(y, 6, 0, 3)) festivals.push('父亲节');

  const lunarDay = lunar.getDayInChinese();
  const lunarMonth = `${lunar.getMonthInChinese()}月`;
  const tags = [...festivals, ...(jieqi ? [jieqi] : [])];
  return {
    y, m, d,
    id: dayId(y, m, d),
    inYear: y === YEAR,
    weekday: (date.getUTCDay() + 6) % 7, // 0 = 周一
    lunarMonth,
    lunarDay,
    lunarShort: lunarDay === '初一' ? lunarMonth : lunarDay,
    lunarFull: `${lunarMonth}${lunarDay}`,
    ganzhiYear: `${lunar.getYearInGanZhi()}${lunar.getYearShengXiao()}年`,
    jieqi,
    festivals,
    tags,
    statutory: tags.some((t) => STATUTORY.has(t)),
  };
}

export function buildCalendar() {
  const start = new Date(Date.UTC(YEAR - 1, 11, 28)); // 2026-12-28 周一
  const end = new Date(Date.UTC(YEAR + 1, 0, 2)); // 2028-01-02 周日
  const all = [];
  for (let t = start.getTime(); t <= end.getTime(); t += 86400000) all.push(describe(new Date(t)));

  const weeks = [];
  for (let i = 0; i < all.length; i += 7) weeks.push({ n: weeks.length + 1, days: all.slice(i, i + 7) });
  for (const w of weeks) for (const day of w.days) day.week = w.n;

  const days = all.filter((d) => d.inYear);
  days.forEach((d, i) => { d.dayOfYear = i + 1; d.daysLeft = days.length - i - 1; });

  const months = MONTHS.map((mo) => {
    const mdays = days.filter((d) => d.m === mo.n);
    const firstWeek = mdays[0].week, lastWeek = mdays[mdays.length - 1].week;
    return {
      ...mo,
      days: mdays,
      weeks: weeks.filter((w) => w.n >= firstWeek && w.n <= lastWeek),
      jieqi: mdays.filter((d) => d.jieqi).map((d) => ({ name: d.jieqi, d: d.d })),
    };
  });
  return { days, weeks, months, byId: new Map(all.map((d) => [d.id, d])) };
}
