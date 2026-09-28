/* Pure helpers shared by the workbench UI and tests (no DOM access). */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.XHSLogic = api;
})(typeof self !== "undefined" ? self : this, function () {
  const FORMAT_NAMES = { cmp: "横评", how: "教程", new: "新品", recap: "复盘" };
  const STATUS_CLASS = { 备题: "", 测试中: "amber", 待复核: "hl", 可发布: "ok", 已发布: "dark", 跳过: "" };
  const BOOLEAN_LABELS = { pass: "通过", fail: "踩坑", pending: "待评" };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /** Very small Markdown subset: paragraphs, **bold**, `code`, - lists, 1. lists. */
  function mdLite(text) {
    const lines = String(text || "").split("\n");
    const out = [];
    let list = null;
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
    const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
    for (const raw of lines) {
      const line = raw.trimEnd();
      const bullet = line.match(/^\s*[-*]\s+(.*)$/);
      const numbered = line.match(/^\s*\d+[.、]\s+(.*)$/);
      if (bullet || numbered) {
        const kind = bullet ? "ul" : "ol";
        if (list !== kind) { close(); out.push(`<${kind}>`); list = kind; }
        out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
      } else if (!line.trim()) {
        close();
      } else {
        close();
        out.push(`<p>${inline(line)}</p>`);
      }
    }
    close();
    return out.join("");
  }

  function charCount(text) {
    const stripped = String(text || "").trim();
    return { withSpaces: [...stripped].length, withoutSpaces: [...stripped.replace(/\s/g, "")].length };
  }

  function tagCount(tags) {
    return (String(tags || "").match(/#[^\s#]+/g) || []).length;
  }

  function checkValueLabel(check, value) {
    const type = (check && check.type) || "boolean";
    if (value === undefined || value === null || value === "" || value === "pending") return "待评";
    if (type === "boolean") return BOOLEAN_LABELS[value] || String(value);
    return String(value);
  }

  /** Parse a number input: "" -> null, invalid -> undefined. */
  function parseScore(raw, min, max) {
    if (raw === "" || raw === null || raw === undefined) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) return undefined;
    if (min !== undefined && value < min) return undefined;
    if (max !== undefined && value > max) return undefined;
    return value;
  }

  /** Convert a drag inside a displayed image into 0–1 fractions of the full image. */
  function boxFromDrag(x0, y0, x1, y1, width, height) {
    const clamp = (v) => Math.min(1, Math.max(0, v));
    const left = clamp(Math.min(x0, x1) / width);
    const top = clamp(Math.min(y0, y1) / height);
    const right = clamp(Math.max(x0, x1) / width);
    const bottom = clamp(Math.max(y0, y1) / height);
    const w = right - left;
    const h = bottom - top;
    if (w < 0.01 || h < 0.005) return null;
    const round = (v) => Math.round(v * 10000) / 10000;
    return { x: round(left), y: round(top), w: round(w), h: round(h), note: "" };
  }

  function statusClass(status) {
    return STATUS_CLASS[status] || "";
  }

  /** Stable JSON used to tell whether an edited object differs from the saved one. */
  function stable(value) {
    if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
    if (value && typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(",")}}`;
    }
    return JSON.stringify(value === undefined ? null : value);
  }

  class DirtyTracker {
    constructor() { this.saved = {}; this.current = {}; }
    load(name, value) { this.saved[name] = stable(value); this.current[name] = this.saved[name]; }
    update(name, value) { this.current[name] = stable(value); }
    isDirty(name) { return name ? this.current[name] !== this.saved[name] : Object.keys(this.current).some((key) => this.current[key] !== this.saved[key]); }
    dirtyNames() { return Object.keys(this.current).filter((key) => this.current[key] !== this.saved[key]); }
    reset(name) { if (name) { delete this.saved[name]; delete this.current[name]; } else { this.saved = {}; this.current = {}; } }
  }

  /** Which step of a post needs attention first. */
  function firstOpenStep(detail) {
    if (!detail) return "brief";
    const codes = new Set(((detail.readiness || {}).blockers || []).map((item) => item.code));
    if (codes.has("evidence_incomplete")) return "evidence";
    if (codes.has("scoring_incomplete")) return "score";
    if (codes.has("copy_blocked") || codes.has("cards_placeholder")) return "copy";
    if (codes.has("scorecard_draft") || codes.has("review_pending") || codes.has("review_stale")) return "review";
    if (codes.has("assets_stale")) return "images";
    if ((detail.readiness || {}).publishable) return "publish";
    return "brief";
  }

  function stepStates(detail) {
    const r = (detail && detail.readiness) || {};
    const c = r.checks || {};
    return {
      brief: true,
      evidence: !!c.evidence_complete,
      score: !!c.scoring_complete,
      copy: !!c.copy_ok && c.cards_ok !== false,
      review: !!r.content_verified,
      images: !!(r.assets && r.assets.fresh_final),
      publish: !!r.publishable,
    };
  }

  /** Next account-level action shown on the overview. */
  function nextAction(account, posts, calendar) {
    const checklist = (account && account.checklist) || [];
    const audit = checklist.find((item) => item.id === "audit");
    if (audit && !audit.done) return { kind: "account", text: "先盘点现有账号：主页、最近 10 篇数据、粉丝互动", href: "#/account" };
    const flat = [];
    ((calendar && calendar.weeks) || []).forEach((week) => week.slots.forEach((slot) => flat.push(slot)));
    const open = flat.find((slot) => slot.topic_id && !["已发布", "跳过"].includes(slot.display_status || slot.status));
    if (open && !open.post_id) return { kind: "create", text: `为第${open.topic_id}期建工作区，开始测试`, topic_id: open.topic_id };
    if (open && open.post_id) {
      const summary = (posts || []).find((post) => post.post_id === open.post_id);
      const next = summary && summary.next;
      if (next && next.owner === "Claude") return { kind: "claude", text: `第${open.topic_id}期交给 Claude：${next.action}`, say: next.say, href: `#/post/${open.post_id}` };
      if (next) return { kind: "post", text: `第${open.topic_id}期：${next.action}`, href: `#/post/${open.post_id}` };
      const blocker = summary && summary.blockers && summary.blockers[0];
      return { kind: "post", text: blocker ? `${open.post_id}：${blocker}` : `${open.post_id}：可以发布了`, href: `#/post/${open.post_id}` };
    }
    return { kind: "none", text: "排期里的题都完成了：去“数据复盘”看看下一步", href: "#/review" };
  }

  function followerProgress(account, goal) {
    const points = (account && account.followers) || [];
    const last = points.length ? points[points.length - 1].count : 0;
    return { count: last, goal: goal || 1000, pct: Math.max(0, Math.min(100, Math.round((last / (goal || 1000)) * 100))) };
  }

  function localDateTimeValue(iso) {
    if (!iso) return "";
    return String(iso).slice(0, 16);
  }

  function toIsoWithOffset(localValue) {
    if (!localValue) return "";
    const date = new Date(localValue);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (n) => String(Math.abs(n)).padStart(2, "0");
    const offset = -date.getTimezoneOffset();
    const sign = offset >= 0 ? "+" : "-";
    return `${localValue.length === 16 ? localValue + ":00" : localValue}${sign}${pad(Math.trunc(offset / 60))}:${pad(offset % 60)}`;
  }

  /** Scorecard note written when a Claude suggestion is accepted (mirrors scripts/suggestions.py). */
  function noteFor(item) {
    const prefix = { pass: "通过", fail: "踩坑" }[item && item.value] || "待定";
    const reason = (item && item.reason) || "";
    const parts = [reason ? `${prefix}：${reason}` : prefix];
    if (item && item.quote) parts.push(`原文“${item.quote}”`);
    return parts.join("｜");
  }

  /**
   * Copy accepted suggestions into one tool's scorecard draft.
   * ids = null accepts every check; “unclear” is never accepted; the user's own
   * gut reaction is never touched; score/verdict/summary only fill empty fields.
   */
  function applySuggestions(result, suggestion, ids) {
    const next = JSON.parse(JSON.stringify(result || {}));
    next.checks = next.checks || {};
    next.notes = next.notes || {};
    const checks = (suggestion && suggestion.checks) || {};
    Object.keys(checks).forEach((id) => {
      if (ids && !ids.includes(id)) return;
      const item = checks[id];
      if (!item || item.value === "unclear" || item.value === undefined) return;
      next.checks[id] = item.value;
      if (item.value === "pass" || item.value === "fail") next.notes[id] = noteFor(item);
    });
    if (!ids) {
      if ((next.total_score === null || next.total_score === undefined || next.total_score === "") && suggestion.total_score !== undefined) next.total_score = suggestion.total_score;
      if (!next.verdict && suggestion.verdict) next.verdict = suggestion.verdict;
      if (!next.summary && suggestion.summary) next.summary = suggestion.summary;
    }
    return next;
  }

  return { noteFor, applySuggestions, FORMAT_NAMES, BOOLEAN_LABELS, esc, mdLite, charCount, tagCount, checkValueLabel, parseScore, boxFromDrag, statusClass, stable, DirtyTracker, firstOpenStep, stepStates, nextAction, followerProgress, localDateTimeValue, toIsoWithOffset };
});
