// Run with: node tests/test_frontend_logic.js
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const L = require(path.join(__dirname, "..", "web", "js", "logic.js"));

// Escaping and the tiny Markdown renderer never let HTML through.
assert.equal(L.esc('<img src=x onerror="a">'), "&lt;img src=x onerror=&quot;a&quot;&gt;");
assert.equal(L.mdLite("**粗体** 和 `代码`\n\n- 一\n- 二"), "<p><b>粗体</b> 和 <code>代码</code></p><ul><li>一</li><li>二</li></ul>");
assert.ok(!L.mdLite("<script>alert(1)</script>").includes("<script>"));

// Counting matches the server's “with spaces” rule for trimmed text.
assert.deepEqual(L.charCount("  周报 150字 "), { withSpaces: 7, withoutSpaces: 6 });
assert.equal(L.tagCount("#AI工具 #AI测评 #周报"), 3);

// Scores: blank is null, out-of-range is undefined (kept as raw so the server rejects it).
assert.equal(L.parseScore("", 1, 5), null);
assert.equal(L.parseScore("4.5", 1, 5), 4.5);
assert.equal(L.parseScore("6", 1, 5), undefined);

// Drag to box: fractions of the displayed image, tiny drags ignored.
assert.deepEqual(L.boxFromDrag(10, 20, 110, 70, 200, 400), { x: 0.05, y: 0.05, w: 0.5, h: 0.125, note: "" });
assert.equal(L.boxFromDrag(10, 10, 11, 11, 200, 400), null);
assert.deepEqual(L.boxFromDrag(300, 500, 100, 100, 200, 400), { x: 0.5, y: 0.25, w: 0.5, h: 0.75, note: "" });

// Dirty tracking compares content, not identity or key order.
const dirty = new L.DirtyTracker();
dirty.load("scorecard", { a: { checks: { t1: "pass" } } });
dirty.update("scorecard", { a: { checks: { t1: "pass" } } });
assert.equal(dirty.isDirty(), false);
dirty.update("scorecard", { a: { checks: { t1: "fail" } } });
assert.deepEqual(dirty.dirtyNames(), ["scorecard"]);
dirty.reset("scorecard");
assert.equal(dirty.isDirty(), false);
assert.equal(L.stable({ b: 1, a: [2, { d: 3, c: 4 }] }), L.stable({ a: [2, { c: 4, d: 3 }], b: 1 }));

// The workspace opens on the first step that still blocks release.
const detail = (codes, extra = {}) => ({ readiness: { blockers: codes.map((code) => ({ code })), checks: {}, ...extra } });
assert.equal(L.firstOpenStep(detail(["evidence_incomplete", "scoring_incomplete"])), "evidence");
assert.equal(L.firstOpenStep(detail(["scoring_incomplete"])), "score");
assert.equal(L.firstOpenStep(detail(["copy_blocked"])), "copy");
assert.equal(L.firstOpenStep(detail(["review_stale"])), "review");
assert.equal(L.firstOpenStep(detail(["assets_stale"])), "images");
assert.equal(L.firstOpenStep(detail([], { publishable: true })), "publish");

// Overview: audit first, then create the next topic, then the post's first blocker.
const account = { checklist: [{ id: "audit", done: false }] };
const calendar = { weeks: [{ slots: [{ topic_id: "01", post_id: null, status: "备题" }] }] };
assert.equal(L.nextAction(account, [], calendar).kind, "account");
account.checklist[0].done = true;
assert.deepEqual(L.nextAction(account, [], calendar).topic_id, "01");
calendar.weeks[0].slots[0].post_id = "post-01-weekly-report";
const next = L.nextAction(account, [{ post_id: "post-01-weekly-report", blockers: ["证据还缺 20 项"] }], calendar);
assert.equal(next.kind, "post");
assert.match(next.text, /证据还缺/);
const claudeNext = L.nextAction(account, [{ post_id: "post-01-weekly-report", next: { owner: "Claude", action: "整理 inbox 里的 10 个文件", say: "第01期截图放好了" } }], calendar);
assert.equal(claudeNext.kind, "claude");
assert.equal(claudeNext.say, "第01期截图放好了");

// Accepting Claude's suggestions fills the draft but never the user's own words.
const suggestion = { checks: { trap_1: { value: "fail", quote: "点击率提升20%", reason: "数据还没出来" }, trap_2: { value: "unclear", reason: "" }, trap_3: { value: "pass", reason: "写了还没修完", quote: "" } }, total_score: 3, verdict: "改两处能交", summary: "编了数据" };
const accepted = L.applySuggestions({ checks: {}, notes: {}, gut_reaction: "格式好看但会吹", verdict: "我自己写的结论" }, suggestion, null);
assert.deepEqual(accepted.checks, { trap_1: "fail", trap_3: "pass" }, "unclear is left for the user");
assert.equal(accepted.notes.trap_1, "踩坑：数据还没出来｜原文“点击率提升20%”");
assert.equal(accepted.notes.trap_3, "通过：写了还没修完");
assert.equal(accepted.gut_reaction, "格式好看但会吹");
assert.equal(accepted.verdict, "我自己写的结论", "existing human text is not overwritten");
assert.equal(accepted.total_score, 3);
const one = L.applySuggestions({ checks: {}, notes: {} }, suggestion, ["trap_3"]);
assert.deepEqual(one.checks, { trap_3: "pass" });
assert.equal(one.total_score, undefined, "single-check accept leaves the score alone");
assert.equal(L.followerProgress({ followers: [{ date: "2026-10-01", count: 250 }] }, 1000).pct, 25);

// Local datetime input → ISO with offset.
assert.match(L.toIsoWithOffset("2026-09-28T20:30"), /^2026-09-28T20:30:00[+-]\d\d:\d\d$/);

// The page loads only local scripts and styles.
const html = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
assert.ok(!/src="https?:|href="https?:/.test(html), "index.html must not load remote resources");

console.log("Frontend logic tests passed");
