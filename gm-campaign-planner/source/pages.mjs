// Page templates for the Game Master's Campaign Planner.
// Every page is a function returning HTML; build.mjs assembles and prints them.
import {
  NPC_QUIRKS, TAVERN_NAMES, RUMORS, VILLAIN_MOTIVES, PLOT_TWISTS, TREASURES, OPENERS,
  HOUSE_SPECIALS, CALLING_CARDS, OMENS,
} from './content.mjs';

export const TITLE = "Game Master's Campaign Planner";

// ---------- small building blocks ----------
export const D20 = (cls = 'd20', label = '') => `<svg class="${cls}" viewBox="0 0 100 100" aria-hidden="true">
  <polygon points="50,3 91,26.5 91,73.5 50,97 9,73.5 9,26.5" class="d20-outer"/>
  <polygon points="50,25 75,67 25,67" class="d20-face"/>
  <path d="M50 3 L50 25 M91 26.5 L75 67 M9 26.5 L25 67 M50 97 L25 67 M50 97 L75 67 M91 73.5 L75 67 M9 73.5 L25 67 M9 26.5 L50 25 M91 26.5 L50 25"/>
  ${label ? `<text x="50" y="57" text-anchor="middle">${label}</text>` : ''}
</svg>`;

const divider = `<svg class="divider" viewBox="0 0 240 12" aria-hidden="true"><path d="M0 6 H104 M136 6 H240"/><path d="M120 1 L126 6 L120 11 L114 6 Z" class="fillk"/><circle cx="108" cy="6" r="1.6" class="fillk"/><circle cx="132" cy="6" r="1.6" class="fillk"/></svg>`;

const SHIELD = '<svg class="shield" viewBox="0 0 100 120" aria-hidden="true"><path d="M50 4 L94 16 V58 C94 88 72 106 50 116 C28 106 6 88 6 58 V16 Z"/><path d="M50 12 L86 22 V58 C86 83 68 98 50 107 C32 98 14 83 14 58 V22 Z" class="inner"/></svg>';

const f = (label, cls = '') => `<div class="f ${cls}"><span class="fl">${label}</span><span class="fu"></span></div>`;
const row = (...items) => `<div class="row">${items.join('')}</div>`;
const lines = (n) => `<div class="lines">${'<div class="ln"></div>'.repeat(n)}</div>`;
const fillLines = () => '<div class="lines fill" data-fill="lines"></div>';
const box = (title, inner, cls = '') =>
  `<div class="box ${cls}"><div class="bt">${title}</div><div class="bi">${inner}</div></div>`;
const colsGrow = (n, ...items) => `<div class="cols c${n} grow">${items.map((i) => `<div class="col">${i}</div>`).join('')}</div>`;
const cols = (n, ...items) => `<div class="cols c${n}">${items.map((i) => `<div class="col">${i}</div>`).join('')}</div>`;
const checks = (items, cls = '') =>
  `<ul class="checks ${cls}">${items.map((i) => `<li><span class="cb"></span><span>${i}</span></li>`).join('')}</ul>`;
const checkLines = (n, numbered = false) =>
  `<ul class="checklines">${Array.from({ length: n }, (_, i) => `<li><span class="cb"></span>${numbered ? `<span class="num">${i + 1}</span>` : ''}<span class="fu"></span></li>`).join('')}</ul>`;
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

function clock(segments, size = 64) {
  const r = 30;
  const spokes = Array.from({ length: segments }, (_, i) => {
    const a = (i / segments) * Math.PI * 2 - Math.PI / 2;
    return `M50 50 L${(50 + r * Math.cos(a)).toFixed(2)} ${(50 + r * Math.sin(a)).toFixed(2)}`;
  }).join(' ');
  return `<svg class="clock" width="${size}" height="${size}" viewBox="18 18 64 64" aria-hidden="true"><circle cx="50" cy="50" r="${r}"/><path d="${spokes}"/></svg>`;
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
    <footer class="pf"><span>${TITLE}</span>${D20('d20 tiny')}<span>${n}</span></footer>
  </div>
</section>`;
}

function rollTable(die, title, entries, { split = 1, start = 1 } = {}) {
  const per = Math.ceil(entries.length / split);
  const parts = Array.from({ length: split }, (_, s) => entries.slice(s * per, (s + 1) * per).map((e, i) => ({ n: start + s * per + i, e })));
  const pad = die === 'd100' ? 2 : String(entries.length).length;
  const label = (n) => (die === 'd100' && n === 100 ? '00' : String(n).padStart(pad, '0'));
  return `<div class="roll" style="flex-grow:${per}">
    <div class="roll-head">${D20('d20 small', die.replace('d', ''))}<div><div class="roll-die">${die}</div><h2>${title}</h2></div></div>
    <div class="cols c${split}">${parts.map((part) => `<table class="rt"><tbody>${part.map(({ n, e }) => `<tr><td class="rn">${label(n)}</td><td>${e}</td></tr>`).join('')}</tbody></table>`).join('')}</div>
  </div>`;
}

// ---------- the pages ----------
const S1 = 'I · The Campaign';
const S2 = 'II · The World';
const S3 = 'III · The Cast';
const S4 = 'IV · The Sessions';
const S5 = 'V · Instant Inspiration';
const S6 = 'Notes';

const cover = () => `<section class="page cover">
  <div class="frame">
    <i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
    <div class="cover-inner">
      <p class="kicker">A printable planner for tabletop roleplaying games</p>
      <div class="cover-center">
        <p class="cover-pre">The Game Master's</p>
        <h1 class="cover-title">Campaign<br>Planner</h1>
        ${divider}
        ${D20('d20 cover-d20', '20')}
        <p class="tagline">Plan the world. Run the table. Remember everything.</p>
      </div>
      <div class="cover-fields">
        ${f('Campaign')}
        ${row(f('Game Master'), f('Began'))}
      </div>
    </div>
  </div>
</section>`;

const PAGES = [
  // 2
  {
    section: 'Welcome',
    title: 'How to Use This Planner',
    sub: 'Print what you need, as often as you need it.',
    body: `<p class="lead">This planner holds your whole campaign in one binder: the pitch, the world, the people in it, and every session you run. Nothing here is tied to one rule system, so it works with any fantasy tabletop RPG.</p>
      ${cols(2,
        box('A prep routine that works', `<ol class="steps">
          <li><b>Review</b> last session's log and your plot threads.</li>
          <li><b>Pick a strong opening</b> that drops the players into action.</li>
          <li><b>List secrets and clues</b> the players could discover, in any order.</li>
          <li><b>Prep people and places,</b> not plots. Let the players choose the path.</li>
          <li><b>Plan one or two encounters</b> and the rewards they earn.</li>
          <li><b>Log the session</b> right after you play, while it's fresh.</li>
        </ol>`),
        box('Binder tips', `<ul class="tips">
          <li>Use tabs for Campaign, World, Cast, Sessions and Inspiration.</li>
          <li>Print Session Prep, Session Log and Combat Tracker pages in batches.</li>
          <li>Write in pencil. Plans change the moment players arrive.</li>
          <li>Faction clocks show the world moving even when the heroes don't.</li>
          <li>Stuck? Roll on the Instant Inspiration tables.</li>
        </ul>`),
      )}
      ${box('Contents', `<div class="toc" data-toc></div>`, 'grow')}`,
  },
  // 3
  {
    section: S1,
    title: 'Campaign Overview',
    body: `${row(f('Campaign name', 'w2'), f('Game system'))}
      ${row(f('Setting'), f('Starting location'), f('Starting level'))}
      ${box('Tone', checks(['Heroic', 'Grim', 'Comedic', 'Horror', 'Intrigue', 'Exploration', 'Mystery', 'Epic', 'Swashbuckling', 'Survival', 'Political', 'Whimsical'], 'grid4'))}
      ${box('The pitch, in one sentence', lines(2))}
      ${cols(2, box('Core conflict', lines(4)), box('The main villain', lines(4)))}
      ${box('Three things that will happen', numLines(3))}
      ${cols(2, box('Themes & inspirations', lines(3)), box('Player-facing hooks', lines(3)))}
      ${box('Possible endings', fillLines(), 'grow')}`,
  },
  // 4
  {
    section: S1,
    title: 'Session Zero',
    sub: 'Agree on the game before you play it.',
    body: `${box('Before the first session', checks([
        'Pitch the campaign and its tone',
        'Agree on schedule and campaign length',
        'Explain house rules and optional rules',
        'Discuss content boundaries and safety tools',
        'Connect the characters to each other',
        'Decide how absences are handled',
        'Balance of combat, roleplay and exploration',
        'Set up group chat, maps and shared notes',
      ], 'grid2'))}
      ${row(f('We play on'), f('Time'), f('Session length'))}
      ${row(f('Where / online link', 'w2'), f('Absence rule'))}
      ${cols(2,
        box('Lines: never in our game', table([''], { rows: 5, cls: 'plain' })),
        box('Veils: happens off-screen', table([''], { rows: 5, cls: 'plain' })),
      )}
      ${box('Safety tools we use', checks(['Open door (leave anytime)', 'X-card', 'Check-ins', 'Script change', 'Stars & wishes', 'Other: __________'], 'grid3'))}
      ${box('House rules', fillLines(), 'grow')}`,
  },
  // 5
  {
    section: S1,
    title: 'The Party',
    body: `<div class="grid g2x3">${Array.from({ length: 6 }, () => `<div class="card">
        ${f('Player')}${f('Character')}${row(f('Class / role'), f('Origin'))}${f('Goal')}${f('Plot hook')}${f('Contact')}
      </div>`).join('')}</div>
      ${row(f('Party name'), f('Party base'))}`,
  },
  // 6
  {
    section: S1,
    title: 'Character Spotlight',
    sub: 'Give every hero a moment to shine.',
    body: `<div class="stack3">${Array.from({ length: 3 }, () => `<div class="card grow">
        ${row(f('Character', 'w2'), f('Player'))}
        ${cols(2, `${f('Wants')}${f('Fears')}${f('Secret')}`, `${f('Bond / ties')}${f('Unfinished business')}${f('Big moment so far')}`)}
        <div class="mini">Spotlight ideas</div>${fillLines()}
      </div>`).join('')}</div>`,
  },
  // 7
  {
    section: S1,
    title: 'Campaign Arc',
    sub: 'A shape for the story, not a script.',
    body: `${['Act I · The Beginning', 'Act II · Rising Stakes', 'Act III · The Climax'].map((act) => box(act, `${row(f('Goal', 'w2'), f('Levels / milestone'))}<div class="mini">Key events</div>${lines(4)}${f('How it ends')}`)).join('')}
      ${box('The final confrontation', fillLines(), 'grow')}`,
  },
  // 8
  {
    section: S1,
    title: 'Timeline & Calendar',
    body: `${row(f('Current year / era'), f('Calendar name'))}
      ${row(f('Months / seasons', 'w2'), f('Holidays'))}
      ${table(['Date', 'Event', 'Consequence'], { fill: true, widths: ['18%', '46%', '36%'] })}`,
  },
  // 9
  {
    section: S2,
    title: 'World Map',
    body: `<div class="mapbox fill" data-hex></div>
      ${row(f('Map of'), f('Scale: 1 hex ='), f('Date drawn'))}`,
  },
  // 10
  {
    section: S2,
    title: 'Region Overview',
    body: `${row(f('Region', 'w2'), f('Climate / terrain'))}
      ${row(f('Who rules here'), f('Capital / largest town'))}
      ${cols(2, box('Notable locations', lines(6)), box('Factions present', lines(6)))}
      ${cols(2, box('Dangers', lines(4)), box('Trade & resources', lines(4)))}
      ${box('Local legends & rumors', lines(3))}
      ${box('If the heroes fail here…', fillLines(), 'grow')}`,
  },
  // 11
  {
    section: S2,
    title: 'Location',
    body: `${row(f('Name', 'w2'), f('Type'))}
      ${row(f('Region'), f('Controlled by'))}
      ${box('First impression (read aloud)', lines(3))}
      ${cols(3, box('Sights', lines(2)), box('Sounds', lines(2)), box('Smells', lines(2)))}
      ${cols(2, box("Who's here", lines(4)), box('Secrets', lines(4)))}
      ${box('Encounters & hazards', lines(2))}
      ${box('Sketch', '<div class="dots fill" data-dots></div>', 'grow')}`,
  },
  // 12
  {
    section: S2,
    title: 'Dungeon & Battle Map',
    body: `<div class="mapbox fill" data-squares></div>
      ${row(f('Map name'), f('1 square ='))}
      ${row(f('Key', 'w3'))}`,
  },
  // 13
  {
    section: S2,
    title: 'Settlement Builder',
    body: `${row(f('Name', 'w2'), f('Population'))}
      ${box('Size', checks(['Hamlet', 'Village', 'Town', 'City', 'Capital'], 'grid5'))}
      ${row(f('Government'), f('Known for'))}
      ${cols(2,
        box('Notable people', table(['Name', 'Role'], { rows: 5, widths: ['55%', '45%'] })),
        box('Shops, inns & services', lines(6)),
      )}
      ${cols(2, box('Trouble brewing', lines(3)), box('What it looks, sounds & smells like', lines(3)))}
      ${box('Map', '<div class="dots fill" data-dots></div>', 'grow')}`,
  },
  // 14
  {
    section: S2,
    title: 'Taverns & Shops',
    body: `<div class="stack2">${Array.from({ length: 2 }, () => `<div class="card grow">
        ${row(f('Name', 'w2'), f('Owner'))}
        ${row(f('Vibe'), f('Known for'))}
        ${colsGrow(2, table(['Item / service', 'Price'], { fill: true, widths: ['70%', '30%'] }), `<div class="mini">Staff & regulars</div>${lines(3)}<div class="mini">Rumor heard here</div>${fillLines()}`)}
      </div>`).join('')}</div>`,
  },
  // 15
  {
    section: S2,
    title: 'Factions',
    body: `<div class="stack3">${Array.from({ length: 3 }, () => `<div class="card grow faction">
        <div class="sigil">${SHIELD}<span>Symbol</span></div>
        <div class="faction-main">
          ${row(f('Faction', 'w2'), f('Leader'))}
          ${f('Goal')}${f('Methods')}${row(f('Resources'), f('Base'))}
          <div class="mini">Secrets & notes</div>${fillLines()}
          <div class="faction-bottom">${scale('Hostile', 'Allied')}<div class="clock-label">${clock(6, 46)}<span>Progress</span></div></div>
        </div>
      </div>`).join('')}</div>`,
  },
  // 16
  {
    section: S2,
    title: 'Faction Clocks',
    sub: 'Fill a segment each time a faction advances its plan. When a clock is full, it happens.',
    body: `<div class="clocks">${[4, 6, 8, 4, 6, 8, 4, 6, 8, 6, 8, 12].map((s) => `<div class="clock-cell">${clock(s, 92)}${f('Clock')}${f('When full')}</div>`).join('')}</div>`,
  },
  // 17
  {
    section: S3,
    title: 'NPC Index',
    body: table(['Name', 'Role', 'Where', 'Attitude', 'Notes'], { fill: true, widths: ['22%', '17%', '17%', '12%', '32%'] }),
  },
  // 18
  {
    section: S3,
    title: 'NPC Cards',
    body: `<div class="grid g2x2">${Array.from({ length: 4 }, () => `<div class="card">
        <div class="npc-top"><div class="portrait"></div><div class="npc-id">${f('Name')}${f('Role')}${f('Found at')}</div></div>
        ${f('Look')}${f('Voice & manner')}${f('Wants')}${f('Secret')}${f('Ties to party')}
        ${scale('Hostile', 'Friendly')}
      </div>`).join('')}</div>`,
  },
  // 19
  {
    section: S3,
    title: 'Villain Dossier',
    body: `<div class="npc-top big"><div class="portrait"></div><div class="npc-id">${f('Name')}${f('Title / alias')}${f('Motive')}${f('Weakness')}${f('Lair')}</div></div>
      ${box('The plan', checkLines(5, true))}
      ${cols(2, box('Lieutenants & minions', lines(4)), box('Resources & allies', lines(4)))}
      ${box('If the heroes do nothing…', lines(3))}
      ${box('The final confrontation', fillLines(), 'grow')}`,
  },
  // 20
  {
    section: S3,
    title: 'Custom Creatures',
    sub: 'Homebrew monsters in any system.',
    body: `<div class="stack2">${Array.from({ length: 2 }, () => `<div class="card grow">
        ${row(f('Creature', 'w2'), f('Type'))}
        ${row(f('Defense'), f('Hit points'), f('Speed'), f('Threat level'))}
        ${colsGrow(2, `<div class="mini">Attacks</div>${fillLines()}`, `<div class="mini">Special abilities</div>${fillLines()}`)}
        ${cols(2, `<div class="mini">Tactics</div>${lines(2)}`, `<div class="mini">Weakness</div>${lines(2)}`)}
        ${row(f('Habitat'), f('Loot'))}
      </div>`).join('')}</div>`,
  },
  // 21
  {
    section: S4,
    title: 'Session Prep',
    body: `${row(f('Session #'), f('Date'), f('Players', 'w2'))}
      ${box('Last time…', lines(2))}
      ${box('Strong opening', lines(2))}
      ${box('Possible scenes', checkLines(3))}
      ${box('Secrets & clues to reveal', `<div class="cols c2">${checkLines(5)}${checkLines(5)}</div>`)}
      ${cols(2, box('NPCs in play', lines(3)), box('Locations', lines(3)))}
      ${cols(2, box('Encounters', lines(3)), box('Rewards & loot', lines(3)))}
      ${box('Cliffhanger / ending', fillLines(), 'grow')}`,
  },
  // 22
  {
    section: S4,
    title: 'Session Log',
    body: `${row(f('Session #'), f('Date'), f('In-game date'))}
      ${box('What happened', lines(7))}
      ${cols(2, box('People met', lines(3)), box('Places visited', lines(3)))}
      ${cols(2, box('Loot & rewards', lines(3)), box('XP / milestones', lines(3)))}
      ${cols(2, box('Threads opened', lines(3)), box('Threads resolved', lines(3)))}
      ${box('Best moment or quote', lines(2))}
      ${box('Notes for next time', fillLines(), 'grow')}`,
  },
  // 23
  {
    section: S4,
    title: 'Encounter Planner',
    body: `<div class="stack2">${Array.from({ length: 2 }, () => `<div class="card grow">
        ${row(f('Encounter', 'w2'), f('Location'))}
        ${checks(['Easy', 'Medium', 'Hard', 'Deadly', 'Social', 'Puzzle'], 'grid6')}
        ${f('Stakes: if they win')}${f('Stakes: if they lose')}
        ${table(['Opponent', '#', 'HP', 'Notes'], { fill: true, widths: ['38%', '8%', '14%', '40%'] })}
        ${cols(2, `<div class="mini">Terrain & hazards</div>${lines(2)}`, `<div class="mini">Twist</div>${lines(2)}`)}
        ${f('Reward')}
      </div>`).join('')}</div>`,
  },
  // 24
  {
    section: S4,
    title: 'Combat Tracker',
    body: `<div class="rounds"><span class="mini">Round</span>${Array.from({ length: 12 }, (_, i) => `<span class="rbox">${i + 1}</span>`).join('')}</div>
      ${table(['Init', 'Name', 'Def', 'Hit points', 'Conditions', 'Notes'], { fill: true, widths: ['8%', '22%', '8%', '24%', '18%', '20%'] })}`,
  },
  // 25
  {
    section: S4,
    title: 'Quests & Plot Threads',
    body: table(['Thread', 'From', 'Clues found', 'Next step', 'Done'], { fill: true, widths: ['24%', '14%', '28%', '26%', '8%'], cls: 'with-check' }),
  },
  // 26
  {
    section: S4,
    title: 'Loot & Treasure Log',
    body: `${row(f('Party treasury'), f('Shared items'))}
      ${table(['Item', 'Found at', 'Carried by', 'Value', 'Notes'], { fill: true, widths: ['26%', '18%', '16%', '12%', '28%'] })}`,
  },
  // 27
  {
    section: S4,
    title: 'Rumors & Hooks',
    sub: 'Write your own, then roll a d20 when the players ask around.',
    body: table(['d20', 'Rumor or hook', 'True?'], { rows: 20, widths: ['9%', '79%', '12%'], cls: 'd20table', first: (i) => i + 1 }),
  },
  // 28
  {
    section: S4,
    title: 'Custom Roll Tables',
    sub: 'Build tables for your own world, then roll when inspiration runs dry.',
    body: `<div class="cols c2 grow">
        <div class="stack-fill">${box('d12 table', `${f('Title')}${table(['d12', 'Result'], { rows: 12, widths: ['16%', '84%'], first: (i) => i + 1, cls: 'stretch' })}`, 'grow')}</div>
        <div class="stack-fill">${box('d6 table', `${f('Title')}${table(['d6', 'Result'], { rows: 6, widths: ['16%', '84%'], first: (i) => i + 1, cls: 'stretch' })}`, 'grow')}${box('d6 table', `${f('Title')}${table(['d6', 'Result'], { rows: 6, widths: ['16%', '84%'], first: (i) => i + 1, cls: 'stretch' })}`, 'grow')}</div>
      </div>`,
  },
  // 29
  { section: S5, title: 'NPC Quirks', sub: 'Roll d100 to give anyone a memorable personality.', body: rollTable('d100', '01–50', NPC_QUIRKS.slice(0, 50), { split: 2 }), cls: 'inspo' },
  // 30
  {
    section: S5,
    title: 'NPC Quirks',
    sub: 'Continued.',
    body: rollTable('d100', '51–100', NPC_QUIRKS.slice(50), { split: 2, start: 51 }),
    cls: 'inspo',
  },
  // 31
  { section: S5, title: 'Taverns & Rumors', body: `<div class="cols c2 roll-pair" style="flex-grow:20">${rollTable('d20', 'Tavern Names', TAVERN_NAMES)}${rollTable('d20', 'Tavern Rumors', RUMORS)}</div>${rollTable('d12', 'House Specials', HOUSE_SPECIALS, { split: 2 })}`, cls: 'inspo' },
  // 32
  { section: S5, title: 'Villains & Twists', body: `${rollTable('d20', 'Villain Motives', VILLAIN_MOTIVES, { split: 2 })}${rollTable('d12', 'Plot Twists', PLOT_TWISTS, { split: 2 })}${rollTable('d10', 'Villain Calling Cards', CALLING_CARDS, { split: 2 })}`, cls: 'inspo' },
  // 33
  { section: S5, title: 'Treasures & Openers', body: `${rollTable('d20', 'Strange Treasures', TREASURES, { split: 2 })}${rollTable('d12', 'Session Openers', OPENERS, { split: 2 })}${rollTable('d10', 'Omens & Weather', OMENS, { split: 2 })}`, cls: 'inspo' },
  // 34
  { section: S6, title: 'Notes', body: fillLines() },
  // 35
  { section: S6, title: 'Notes', body: '<div class="dots fill" data-dots></div>' },
];

export function renderPages() {
  return [cover(), ...PAGES.map((p, i) => page(p, i + 2))];
}

// Contents for the "How to use" page: title -> page number (first occurrence).
export function contents() {
  const seen = new Map();
  PAGES.forEach((p, i) => {
    if (i === 0) return;
    const key = p.title;
    if (!seen.has(key)) seen.set(key, { title: p.title, n: i + 2, section: p.section });
  });
  return [...seen.values()];
}

export const PAGE_COUNT = PAGES.length + 1;
