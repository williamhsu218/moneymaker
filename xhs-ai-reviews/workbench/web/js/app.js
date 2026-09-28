/* 科技试吃员 · 起号工作台 — plain JavaScript, no framework, no CDN. */
(() => {
  "use strict";
  const L = window.XHSLogic;
  const { esc } = L;
  const app = document.getElementById("app");
  const STEPS = [
    ["brief", "测试", "你"], ["evidence", "整理证据", "Claude"], ["score", "确认判定", "你"], ["copy", "文案", "Claude 起草"],
    ["review", "复核", "你"], ["images", "图片", "Claude 生成"], ["publish", "发布与数据", "你"],
  ];
  const METADATA = [["model", "模型"], ["version", "版本"], ["platform", "平台/入口"], ["settings", "设置（深度思考/联网等）"], ["free_tier", "免费额度"], ["tested_at", "测试时间"]];

  const state = {
    config: null,
    route: { view: "overview" },
    detail: null,
    drafts: {},
    dirty: new L.DirtyTracker(),
    lastHash: location.hash || "#/",
    editor: null,
    editorMode: "mask",
  };

  // --------------------------------------------------------------- plumbing
  async function api(path, options = {}) {
    const init = { method: options.method || (options.body ? "POST" : "GET"), headers: {} };
    if (options.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    let response;
    try {
      response = await fetch(path, init);
    } catch (error) {
      setServer(false);
      throw new Error("连不上本机服务：请确认终端里的工作台还在运行");
    }
    setServer(true);
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    if (!response.ok && !(options.allow || []).includes(response.status)) {
      const message = (data && (data.error || data.message)) || `请求失败（${response.status}）`;
      const err = new Error(message);
      err.data = data;
      err.status = response.status;
      throw err;
    }
    return data;
  }

  function setServer(ok) {
    const el = document.getElementById("server-state");
    if (el) el.innerHTML = `<span class="dot${ok ? "" : " off"}"></span>${ok ? "本机服务" : "服务未连接"}`;
  }

  function toast(message, kind) {
    const wrap = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = `toast${kind === "error" ? " error" : ""}`;
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), kind === "error" ? 6000 : 2600);
  }

  async function run(button, task, success) {
    const label = button ? button.innerHTML : "";
    if (button) { button.disabled = true; button.textContent = "处理中…"; }
    try {
      const result = await task();
      if (success) toast(success);
      return result;
    } catch (error) {
      toast(error.message, "error");
      return undefined;
    } finally {
      if (button && button.isConnected) { button.disabled = false; button.innerHTML = label; }
    }
  }

  async function copyText(text, button) {
    const done = () => {
      if (!button) return;
      const old = button.textContent;
      button.textContent = "已复制";
      button.classList.add("done");
      setTimeout(() => { button.textContent = old; button.classList.remove("done"); }, 1400);
    };
    try {
      await navigator.clipboard.writeText(text);
      done();
    } catch (error) {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      area.remove();
      if (ok) done(); else toast("复制失败，请手动选中文字复制", "error");
    }
  }

  function readFileBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
      reader.onerror = () => reject(new Error("读取文件失败"));
      reader.readAsDataURL(file);
    });
  }

  function storage(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (error) { /* private mode */ }
    return null;
  }

  function toolName(id) {
    const tool = (state.config.tools || []).find((item) => item.id === id);
    return tool ? tool.display_name : id;
  }

  function topicById(id) {
    return (state.config.topics || []).find((topic) => topic.id === id);
  }

  function copyBlock(label, text, ref) {
    const id = `cb${Math.random().toString(36).slice(2, 9)}`;
    copyStore[id] = text;
    return `<div class="copy-block"><div class="top"><span class="small muted">${esc(label)}</span><button class="small" data-action="copy" data-copy="${id}">复制</button></div><pre>${esc(text)}</pre>${ref ? `<div class="ref">${safeRef(ref)}</div>` : ""}</div>`;
  }
  const copyStore = {};

  function safeRef(html) {
    return esc(html).replace(/&lt;(\/?)b&gt;/g, "<$1b>").replace(/&lt;br\s*\/?&gt;/g, "<br>");
  }

  function chip(text, kind) {
    return `<span class="chip ${kind || ""}">${esc(text)}</span>`;
  }

  // ------------------------------------------------------------------ dirty
  function refreshDirtyBar() {
    const bar = document.getElementById("dirty-bar");
    const names = state.dirty.dirtyNames();
    bar.hidden = names.length === 0;
    const labels = { scorecard: "评分", copy: "文案", cards: "文字卡", highlights: "截图标注", calendar: "排期", account: "账号盘点" };
    document.getElementById("dirty-text").textContent = `未保存：${names.map((name) => labels[name] || (name.startsWith("ev:") ? "证据原文" : name.startsWith("meta:") ? "工具信息" : name)).filter((v, i, a) => a.indexOf(v) === i).join("、")}`;
  }

  function markDraft(name, value) {
    state.drafts[name] = value;
    state.dirty.update(name, value);
    refreshDirtyBar();
  }

  function loadDraft(name, value) {
    state.drafts[name] = JSON.parse(JSON.stringify(value));
    state.dirty.load(name, value);
  }

  function clearDrafts() {
    state.drafts = {};
    state.dirty.reset();
    refreshDirtyBar();
  }

  window.addEventListener("beforeunload", (event) => {
    if (state.dirty.isDirty()) { event.preventDefault(); event.returnValue = ""; }
  });

  // ----------------------------------------------------------------- router
  function parseRoute(hash) {
    const parts = (hash || "#/").replace(/^#\/?/, "").split("/").filter(Boolean);
    if (!parts.length) return { view: "overview" };
    if (parts[0] === "post" && parts[1]) return { view: "post", id: parts[1], step: parts[2] || null };
    return { view: parts[0] };
  }

  window.addEventListener("hashchange", () => {
    const next = parseRoute(location.hash);
    const current = state.route;
    const leavingPost = current.view === "post" && (next.view !== "post" || next.id !== current.id);
    const leavingCalendar = current.view === "overview" && next.view !== "overview";
    const leavingAccount = current.view === "account" && next.view !== "account";
    if ((leavingPost || leavingCalendar || leavingAccount) && state.dirty.isDirty()) {
      history.replaceState(null, "", state.lastHash);
      toast("有未保存的修改：先点底部的“保存”或“放弃修改”", "error");
      return;
    }
    state.lastHash = location.hash;
    render();
  });

  async function render() {
    state.route = parseRoute(location.hash);
    document.querySelectorAll("[data-nav]").forEach((link) => {
      const view = state.route.view === "post" ? "posts" : state.route.view;
      link.classList.toggle("active", link.dataset.nav === view);
    });
    try {
      if (!state.config) state.config = await api("/api/config");
      document.getElementById("brand-name").textContent = state.config.brand.account_name || "科技试吃员";
      const views = { overview: renderOverview, posts: renderPosts, post: renderPost, account: renderAccount, review: renderReviewPage, leads: renderLeads };
      await (views[state.route.view] || renderOverview)();
    } catch (error) {
      app.innerHTML = `<div class="card"><h2>出错了</h2><p class="muted">${esc(error.message)}</p></div>`;
    }
  }

  // --------------------------------------------------------------- overview
  async function renderOverview() {
    const [calendar, postsData, account] = await Promise.all([api("/api/calendar"), api("/api/posts"), api("/api/account")]);
    const posts = postsData.posts;
    if (!state.dirty.isDirty("calendar")) loadDraft("calendar", calendar);
    const cal = state.drafts.calendar;
    const next = L.nextAction(account, posts, calendar);
    const flat = calendar.weeks.flatMap((week) => week.slots);
    const published = flat.filter((slot) => slot.display_status === "已发布").length;
    const ready = flat.filter((slot) => slot.display_status === "可发布").length;
    const progress = L.followerProgress(account, 1000);
    const editing = state.calendarEditing;
    const topicOptions = (selected) => `<option value="">（空）</option>` + state.config.topics.map((topic) => `<option value="${topic.id}"${topic.id === selected ? " selected" : ""}>${topic.id} ${esc(topic.name)}</option>`).join("");
    const slotHtml = (slot, wi, si) => {
      const topic = slot.topic_id ? topicById(slot.topic_id) : null;
      const status = slot.display_status || slot.status || "备题";
      if (editing) {
        const published = slot.status === "已发布";
        return `<div class="slot ${slot.kind === "flex" ? "flex" : ""}">
          ${published ? `<span class="date">${esc(slot.date)}</span><span>${topic ? `${topic.id} ${esc(topic.name)}` : "已发布篇目"}</span><span class="chip ok">已发布 · ${esc(slot.published_at || "时间未记录")}</span>` : `
          <input type="date" value="${esc(slot.date)}" data-cal="date" data-w="${wi}" data-s="${si}">
          <select data-cal="topic_id" data-w="${wi}" data-s="${si}">${topicOptions(slot.topic_id)}</select>
          <select data-cal="status" data-w="${wi}" data-s="${si}">${["备题", "跳过"].concat(slot.status && !["备题", "跳过"].includes(slot.status) ? [slot.status] : []).map((value) => `<option${value === slot.status ? " selected" : ""}>${value}</option>`).join("")}</select>`}
          <input type="text" value="${esc(slot.note || "")}" placeholder="备注" data-cal="note" data-w="${wi}" data-s="${si}">
        </div>`;
      }
      const summary = slot.post_id ? posts.find((post) => post.post_id === slot.post_id) : null;
      const owner = summary && summary.next && !["已发布", "跳过"].includes(status) ? `<div class="small">${summary.next.owner === "Claude" ? `<span class="chip hl">Claude</span> 说「${esc(summary.next.say)}」` : `<span class="chip ok">你</span> ${esc(summary.next.action.slice(0, 26))}${summary.next.action.length > 26 ? "…" : ""}`}</div>` : "";
      const action = slot.post_id
        ? `${owner}<a class="btn small" href="#/post/${esc(slot.post_id)}">打开</a>`
        : topic ? `<button class="small" data-action="create-post" data-topic="${topic.id}">建工作区</button>` : "";
      return `<div class="slot ${slot.kind === "flex" ? "flex" : ""}">
        <div class="row"><span class="date">${esc(slot.date)}${slot.kind === "flex" ? " · 机动" : ""}</span>${chip(status, L.statusClass(status))}</div>
        <div class="t">${topic ? `${topic.id} ${esc(topic.name)}` : `<span class="muted">${esc(slot.note || "机动位")}</span>`}</div>
        ${topic && slot.note ? `<div class="small muted">${esc(slot.note)}</div>` : ""}
        <div class="row">${action}</div>
      </div>`;
    };
    app.innerHTML = `
      <div class="page-head"><div><h1>总览</h1><p>每周 3 个固定位 + 1 个机动位。状态随证据和复核自动变化；“已发布”只能你手动标记。</p></div></div>
      <div class="grid grid-3">
        <div class="card"><div class="eyebrow">下一步${next.kind === "claude" ? " · Claude" : " · 你"}</div><p style="margin-top:6px;font-weight:700">${esc(next.text)}</p>
          ${next.say ? `<p class="small" style="margin-top:4px">在 Cowork 里说「<b>${esc(next.say)}</b>」</p>` : ""}
          <div class="row" style="margin-top:10px">${next.say ? `<button class="small primary" data-action="copy" data-copy="${stash(next.say)}">复制这句话</button>` : ""}${next.href ? `<a class="btn small${next.say ? "" : " primary"}" href="${next.href}">打开</a>` : next.topic_id ? `<button class="primary small" data-action="create-post" data-topic="${next.topic_id}">建工作区</button>` : ""}</div></div>
        <div class="card"><div class="eyebrow">进度</div>
          <div class="stats" style="margin-top:8px"><span>工作区 <b>${posts.length}</b></span><span>可发布 <b>${ready}</b></span><span>已发布 <b>${published}</b></span></div>
          <p class="small muted" style="margin-top:6px">发布节奏：${esc(calendar.publish_window || "")}</p></div>
        <div class="card"><div class="eyebrow">起号目标（自定 1000 粉）</div>
          <p style="margin-top:6px"><b style="font-size:22px">${progress.count}</b> <span class="muted">/ ${progress.goal}</span></p>
          <div class="progress" style="margin-top:6px"><div style="width:${progress.pct}%"></div></div>
          <p class="small muted" style="margin-top:6px">在“账号”页记录粉丝数；商业合作资格以 App 当前提示为准。</p></div>
      </div>
      <div class="card" style="margin-top:14px">
        <div class="card-head"><h2>排期</h2><div class="row">
          ${editing ? `<button class="primary small" data-action="save-calendar">保存排期</button><button class="small" data-action="cancel-calendar">取消</button>` : `<button class="small" data-action="edit-calendar">编辑排期</button>`}
        </div></div>
        <div class="board">${cal.weeks.map((week, wi) => `<div class="week"><div class="wk">第${week.week}周</div>${week.slots.map((slot, si) => slotHtml(slot, wi, si)).join("")}</div>`).join("")}</div>
      </div>`;
  }

  // ------------------------------------------------------------------ posts
  async function renderPosts() {
    const data = await api("/api/posts");
    const existing = new Set(data.posts.map((post) => post.topic_id));
    app.innerHTML = `
      <div class="page-head"><div><h1>篇目</h1><p>每一期一个工作区（posts/ 下的文件夹）。按步骤走：测试 → 证据 → 评分 → 文案 → 复核 → 图片 → 发布。</p></div></div>
      <div class="card">
        <div class="card-head"><h2>新建工作区</h2></div>
        <div class="row">
          <select id="new-topic" style="max-width:340px">${state.config.topics.map((topic) => `<option value="${topic.id}">${topic.id} ${esc(topic.name)}${existing.has(topic.id) ? "（已有）" : ""}</option>`).join("")}</select>
          <input type="text" id="new-slug" placeholder="可选：目录后缀，如 qwen-omni" style="max-width:240px">
          <button class="primary" data-action="create-post-form">新建</button>
        </div>
        <p class="small muted" style="margin-top:8px">第 11 期（新品）可以用不同后缀建多个工作区，参评工具在“测试说明”里改。</p>
      </div>
      <div class="card">
        <h2>已有工作区</h2>
        ${data.posts.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>篇目</th><th>形式</th><th>工具</th><th>证据</th><th>状态</th><th>还缺</th></tr></thead><tbody>
          ${data.posts.map((post) => `<tr>
            <td><a href="#/post/${esc(post.post_id)}"><b>${esc(post.topic_id)} ${esc(post.name)}</b></a><div class="small muted mono">${esc(post.post_id)}</div></td>
            <td>${esc(L.FORMAT_NAMES[post.format] || post.format)}</td>
            <td class="small">${esc(post.tools.join("、"))}</td>
            <td>${post.evidence_count}/${post.required_evidence_count}</td>
            <td>${post.publishable ? chip("可发布", "ok") : post.content_verified ? chip("待生成终版图", "hl") : post.content_ready_for_review ? chip("待复核", "hl") : chip("进行中", "amber")}</td>
            <td class="small muted">${esc((post.blockers || [])[0] || "")}</td>
          </tr>`).join("")}</tbody></table></div>` : `<div class="empty" style="margin-top:10px">还没有工作区。先建第 01 期。</div>`}
      </div>`;
  }

  async function createPost(topicId, slug, button) {
    const result = await run(button, () => api("/api/posts", { body: { topic_id: topicId, slug: slug || undefined } }), "工作区已建好");
    if (result) location.hash = `#/post/${result.post_id}`;
  }

  // ---------------------------------------------------------------- actions
  const actions = {};
  document.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const handler = actions[target.dataset.action];
    if (handler) {
      event.preventDefault();
      await handler(target, event);
    }
  });

  actions.copy = (button) => copyText(copyStore[button.dataset.copy] || "", button);
  actions["create-post"] = (button) => createPost(button.dataset.topic, "", button);
  actions["create-post-form"] = (button) => createPost(document.getElementById("new-topic").value, document.getElementById("new-slug").value.trim(), button);
  actions["edit-calendar"] = () => { state.calendarEditing = true; renderOverview(); };
  actions["cancel-calendar"] = () => { state.calendarEditing = false; state.dirty.reset("calendar"); refreshDirtyBar(); renderOverview(); };
  actions["save-calendar"] = async (button) => {
    const saved = await run(button, () => api("/api/calendar", { body: { calendar: state.drafts.calendar } }), "排期已保存");
    if (saved) { state.calendarEditing = false; state.dirty.reset("calendar"); refreshDirtyBar(); renderOverview(); }
  };
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (el.dataset && el.dataset.cal) {
      const cal = state.drafts.calendar;
      const slot = cal.weeks[Number(el.dataset.w)].slots[Number(el.dataset.s)];
      slot[el.dataset.cal] = el.value || (el.dataset.cal === "topic_id" ? null : "");
      markDraft("calendar", cal);
    }
  });
  document.addEventListener("change", (event) => {
    const el = event.target;
    if (el.dataset && el.dataset.cal) el.dispatchEvent(new Event("input", { bubbles: true }));
  });

  actions["save-all"] = async (button) => {
    const names = state.dirty.dirtyNames();
    for (const name of names) {
      const saver = savers[name.split(":")[0]];
      if (saver) {
        const ok = await run(button, () => saver(name));
        if (ok === undefined) return;
      }
    }
    toast("已保存");
  };
  actions["discard-all"] = () => {
    clearDrafts();
    state.calendarEditing = false;
    render();
  };
  const savers = {};

  // ================================================================ POST
  async function loadDetail(id, fresh) {
    if (fresh || !state.detail || state.detail.post.post_id !== id) {
      state.detail = await api(`/api/posts/${id}`);
      if (!state.dirty.isDirty()) seedDrafts();
    }
    return state.detail;
  }

  function seedDrafts() {
    const d = state.detail;
    loadDraft("scorecard", d.scorecard.tool_results || {});
    loadDraft("copy", d.copy);
    loadDraft("cards", d.cards || {});
    refreshDirtyBar();
  }

  function applyDetail(detail) {
    state.detail = detail;
    const keep = {};
    state.dirty.dirtyNames().forEach((name) => { keep[name] = state.drafts[name]; });
    seedDrafts();
    Object.keys(keep).forEach((name) => markDraft(name, keep[name]));
    renderPostBody();
  }

  async function renderPost() {
    const { id } = state.route;
    const detail = await loadDetail(id, !state.dirty.isDirty());
    const step = state.route.step || L.firstOpenStep(detail);
    state.step = step;
    const topic = detail.topic;
    app.innerHTML = `
      <div class="post-head">
        <div class="eyebrow">第${esc(topic.id)}期 · ${esc(L.FORMAT_NAMES[topic.format] || "")} · 写给${esc(topic.audience || "")}</div>
        <h1>${esc(topic.name)}</h1>
        <div class="row" id="post-status"></div>
        <div id="next-banner"></div>
      </div>
      <nav class="steps" id="steps"></nav>
      <div id="step-body"></div>`;
    renderPostBody();
  }

  function nextBanner(next) {
    if (!next) return "";
    if (next.owner === "Claude") {
      return `<div class="next-banner claude"><div><span class="who">下一步 · Claude</span>${esc(next.action)}：在 Cowork 里说「<b>${esc(next.say)}</b>」</div><button class="small" data-action="copy" data-copy="${stash(next.say)}">复制这句话</button></div>`;
    }
    const then = next.then ? `，完成后在 Cowork 里说「<b>${esc(next.then)}</b>」` : "";
    const button = next.then ? `<button class="small" data-action="copy" data-copy="${stash(next.then)}">复制这句话</button>` : "";
    return `<div class="next-banner you"><div><span class="who">下一步 · 你</span>${esc(next.action)}${then}</div>${button}</div>`;
  }

  function stash(text) {
    const id = `cb${Math.random().toString(36).slice(2, 9)}`;
    copyStore[id] = text;
    return id;
  }

  function ownerNote(owner, text, say) {
    return `<div class="owner-note ${owner === "你" ? "you" : "claude"}"><span class="who">${esc(owner)}</span><span>${text}</span>${say ? `<button class="small" data-action="copy" data-copy="${stash(say)}">复制「${esc(say)}」</button>` : ""}</div>`;
  }

  function renderPostBody() {
    const d = state.detail;
    if (!d || !document.getElementById("step-body")) return;
    const r = d.readiness;
    const states = L.stepStates(d);
    document.getElementById("post-status").innerHTML = [
      chip(d.post.post_id, "dark"),
      r.publishable ? chip("发布包已放行", "ok") : r.content_verified ? chip("已复核 · 待生成终版图", "hl") : r.content_ready_for_review ? chip("内容齐了 · 待复核", "hl") : chip(`还缺 ${r.blockers.length} 类`, "amber"),
      chip(`证据 ${r.evidence_count}/${r.required_evidence_count}`),
      ...d.tools.map((tool) => chip(tool.display_name)),
    ].join(" ");
    document.getElementById("next-banner").innerHTML = nextBanner(d.next);
    document.getElementById("steps").innerHTML = STEPS.map(([key, label, owner], index) => `<button type="button" data-action="step" data-step="${key}" class="${state.step === key ? "active" : ""}"><span class="n">${index + 1}</span> ${label}<span class="owner">${owner}</span>${states[key] && key !== "brief" ? ' <span class="tick">✓</span>' : ""}</button>`).join("");
    const renderers = { brief: stepBrief, evidence: stepEvidence, score: stepScore, copy: stepCopy, review: stepReview, images: stepImages, publish: stepPublish };
    document.getElementById("step-body").innerHTML = (renderers[state.step] || stepBrief)(d);
    if (state.step === "images") mountEditor();
  }

  actions.step = (button) => {
    location.hash = `#/post/${state.detail.post.post_id}/${button.dataset.step}`;
  };

  // ----------------------------------------------------------------- brief
  function stepBrief(d) {
    const topic = d.topic;
    const allTools = state.config.tools;
    const selected = new Set(d.post.tools);
    const order = d.tools.map((tool) => tool.display_name).join(" → ");
    return `
      ${ownerNote("你", `在手机 App 里按下面的内容测试，每一轮截一张图（长截图更好）。建议按 ${esc(order)} 的顺序测，文件名不用改。截完全部 AirDrop 到 <code>posts/${esc(d.post.post_id)}/inbox/</code>，然后交给 Claude。`, d.phrases.intake)}
      <div class="grid grid-2" style="margin-top:14px">
        <div class="card stack">
          <h2>为什么做这一期</h2><p>${esc(topic.why)}</p>
          <h3>测试条件</h3><p>${esc(topic.setup)}</p>
          ${topic.method_md ? `<h3>方法与底线</h3><div class="md small">${L.mdLite(topic.method_md)}</div>` : ""}
        </div>
        <div class="card stack">
          <h2>参评工具</h2>
          <p class="small muted">测试以手机 App 为主；网页链接只是备用。名称和入口以测试当天 App 内显示为准。</p>
          ${d.tools.map((tool) => `<div class="row"><b>${esc(tool.display_name)}</b><span class="small muted">${esc(tool.app_name || "")}</span>${tool.web_url ? `<a class="small" href="${esc(tool.web_url)}" target="_blank" rel="noopener noreferrer">网页版</a>` : ""}${tool.verified_at ? chip("链接已核对", "ok") : chip("测试当天核对", "amber")}${tool.note ? `<span class="small muted">${esc(tool.note)}</span>` : ""}</div>`).join("")}
          <details><summary class="small"><b>更换参评工具</b>（至少 ${topic.min_tools || 1} 款；更换会让评分回到草稿）</summary>
            <div class="grid grid-3" style="margin-top:8px">${allTools.map((tool) => `<label style="font-weight:600;color:var(--ink)"><input type="checkbox" data-tool-pick value="${tool.id}"${selected.has(tool.id) ? " checked" : ""}> ${esc(tool.display_name)}</label>`).join("")}</div>
            <div class="row" style="margin-top:8px"><button class="small" data-action="save-tools">保存参评工具</button></div>
          </details>
          <p class="small muted">完整说明也在 <code>posts/${esc(d.post.post_id)}/README.md</code>。</p>
        </div>
      </div>
      <div class="card stack">
        <h2>测试内容（原样复制）</h2>
        ${(topic.tests || []).length ? topic.tests.map((test) => copyBlock(test.label, test.text, test.ref)).join("") : `<p class="muted">这一期不需要新测试。</p>`}
      </div>
      <div class="card stack">
        <h2>要拍/截的素材</h2>
        <ul>${(topic.assets || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
        <p class="small muted">截图用 AirDrop 放进 <code>posts/${esc(d.post.post_id)}/inbox/</code>，下一步在“录入证据”里分配。回答原文在 App 里长按复制，粘贴到工作台。</p>
      </div>`;
  }

  actions["save-tools"] = async (button) => {
    const tools = [...document.querySelectorAll("[data-tool-pick]:checked")].map((el) => el.value);
    const detail = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/settings`, { body: { tools } }), "参评工具已更新");
    if (detail) { clearDrafts(); applyDetail(detail); }
  };

  // -------------------------------------------------------------- evidence
  function scopeOptions(d, selected) {
    const scopes = d.post.tools.map((tool) => [tool, toolName(tool)]);
    if ((d.topic.evidence.shared || []).length) scopes.push(["shared", "本期共用"]);
    return scopes.map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${esc(label)}</option>`).join("");
  }

  function keyOptions(d, scope, kind, selected) {
    const specs = scope === "shared" ? d.topic.evidence.shared : d.topic.evidence.per_tool;
    return specs.filter((spec) => !kind || kind === "file" || (kind === "image" || kind === "heic" ? spec.kind === "image" : spec.kind === kind)).map((spec) => `<option value="${spec.key}"${spec.key === selected ? " selected" : ""}>${esc(spec.label)}</option>`).join("");
  }

  function evidenceRow(d, scope, row) {
    const base = `/api/posts/${d.post.post_id}/evidence-file?scope=${scope}&key=${row.key}&v=${row.mtime || 0}`;
    const status = row.ok ? chip("✓ 已录入", "ok") : row.required ? chip(row.reason || "未录入", "warn") : chip(row.path ? row.reason : "可选", row.path ? "warn" : "");
    let body = "";
    if (row.kind === "text") {
      const name = `ev:${scope}:${row.key}`;
      const value = state.drafts[name] !== undefined ? state.drafts[name] : (row.text || "");
      body = `<textarea rows="5" data-ev-text="${name}" data-scope="${scope}" data-key="${row.key}" placeholder="在 App 里长按回答 → 复制，原样粘贴到这里">${esc(value)}</textarea>
        <div class="row" style="margin-top:6px"><button class="small" data-action="save-ev-text" data-scope="${scope}" data-key="${row.key}">保存原文</button><span class="small muted">${L.charCount(value).withSpaces} 字</span></div>`;
    } else {
      const preview = row.path && row.kind === "image" ? `<a href="${base}" target="_blank" rel="noopener"><img class="thumb" src="${base}" alt="${esc(row.label)}"></a>` : row.path ? `<span class="small mono">${esc(row.path.split("/").pop())}</span>` : "";
      body = `<div class="row">${preview}<label class="btn small" style="color:var(--ink)">${row.path ? "替换" : "上传"}<input type="file" hidden data-upload data-scope="${scope}" data-key="${row.key}" ${row.kind === "image" ? 'accept="image/*,.heic,.heif"' : ""}></label></div>`;
    }
    return `<div class="ev-row"><div><div class="ev-label">${esc(row.label)}</div><div class="small muted mono">${esc(row.path || "")}</div></div><div>${status}</div><div class="ev-body">${body}</div></div>`;
  }

  const SOURCE_BADGE = { claude_transcribed: ["Claude 转写", "hl"], pasted: ["你粘贴", "ok"], uploaded: ["上传", "ok"], inbox: ["inbox", "ok"] };

  function evidenceTable(d) {
    const specs = d.topic.evidence.per_tool || [];
    if (!specs.length) return "";
    const rows = d.post.tools.map((tool) => {
      const info = d.evidence.per_tool[tool] || { files: [], missing_metadata: [] };
      const sources = ((d.manifest.tools || {})[tool] || {}).sources || {};
      const cells = specs.map((spec) => {
        const row = info.files.find((item) => item.key === spec.key) || {};
        if (row.ok) {
          const badge = SOURCE_BADGE[sources[spec.key]] || ["已录入", "ok"];
          return `<td>${chip("✓ " + badge[0], badge[1])}</td>`;
        }
        return `<td>${row.required === false ? chip("可选") : chip(row.reason || "未录入", "warn")}</td>`;
      }).join("");
      const meta = info.missing_metadata.length ? chip(`缺${info.missing_metadata.join("、")}`, "warn") : chip("✓", "ok");
      return `<tr><td><b>${esc(toolName(tool))}</b></td>${cells}<td>${meta}</td></tr>`;
    }).join("");
    return `<div class="table-wrap"><table class="data"><thead><tr><th>工具</th>${specs.map((spec) => `<th>${esc(spec.label)}</th>`).join("")}<th>工具信息</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function stepEvidence(d) {
    const ev = d.evidence;
    const photoIndexes = (d.topic.images || []).filter((image) => image.kind === "photo").map((image) => image.index);
    const inbox = d.inbox || [];
    const transcribed = d.post.tools.some((tool) => Object.values((((d.manifest.tools || {})[tool] || {}).sources) || {}).includes("claude_transcribed"));
    const inboxHtml = inbox.length ? `<div class="inbox-list">${inbox.map((item, index) => {
      const sug = item.suggestion || {};
      const scope = sug.scope || d.post.tools[0];
      const src = `/api/posts/${d.post.post_id}/inbox-file?name=${encodeURIComponent(item.name)}`;
      return `<div class="inbox-item">
        ${item.kind === "image" ? `<img src="${src}" alt="">` : `<div class="empty small">${esc(item.kind === "heic" ? "HEIC（归档时自动转 PNG）" : item.kind)}</div>`}
        <div class="small mono">${esc(item.name)}</div>
        <details><summary class="small">手动归档</summary>
          <select data-inbox-scope="${index}">${scopeOptions(d, scope)}</select>
          <select data-inbox-key="${index}">${keyOptions(d, scope, item.kind, sug.key)}</select>
          <button class="small" data-action="assign-inbox" data-index="${index}" data-name="${esc(item.name)}">归档</button>
        </details>
      </div>`;
    }).join("")}</div>` : `<div class="empty small">inbox 是空的。截图 AirDrop 到 <code>posts/${esc(d.post.post_id)}/inbox/</code> 后点“刷新”。</div>`;
    const toolCards = d.post.tools.map((tool) => {
      const info = ev.per_tool[tool] || { files: [], missing_metadata: [] };
      const meta = (d.manifest.tools || {})[tool] || {};
      const metaDraft = state.drafts[`meta:${tool}`] || meta;
      return `<div class="tool-card">
        <div class="card-head"><h3>${esc(toolName(tool))}</h3></div>
        <div class="field-row">${METADATA.map(([field, label]) => field === "tested_at"
          ? `<label>${label}<input type="datetime-local" value="${esc(L.localDateTimeValue(metaDraft[field]))}" data-meta="${tool}" data-field="${field}"></label>`
          : `<label>${label}<input type="text" value="${esc(metaDraft[field] || "")}" data-meta="${tool}" data-field="${field}"></label>`).join("")}</div>
        <div class="row end" style="margin-top:8px"><button class="small" data-action="save-meta" data-tool="${tool}">保存工具信息</button></div>
        <div style="margin-top:6px">${info.files.map((row) => evidenceRow(d, tool, row)).join("")}</div>
      </div>`;
    }).join("");
    const shared = ev.shared.length ? `<div class="tool-card"><h3>本期共用</h3>${ev.shared.map((row) => evidenceRow(d, "shared", row)).join("")}</div>` : "";
    const photos = photoIndexes.length ? `<div class="card"><h2>你拍的照片</h2><p class="small muted">按编号用在图片里；也可以放进 inbox 让 Claude 归档。</p><div class="gallery" style="margin-top:10px">${photoIndexes.map((index) => {
      const name = (d.photos || []).find((file) => file.startsWith(String(index).padStart(2, "0") + "."));
      return `<figure>${name ? `<img src="/assets/posts/${d.post.post_id}/photos/${name}?v=${Date.now()}" alt="">` : `<div class="empty small" style="aspect-ratio:3/4">照片 ${index}</div>`}<figcaption><label class="btn small" style="color:var(--ink)">${name ? "替换" : "上传"}<input type="file" hidden accept="image/*" data-photo="${index}"></label></figcaption></figure>`;
    }).join("")}</div></div>` : "";
    return `
      ${ownerNote("Claude", "读 inbox 里的截图，逐字转写回答原文，归到对应格子，从截图里读出模型名并填好测试时间，然后给出判定建议、标红框、写初稿、生成草稿图。你只要确认截图都放进去了。", d.phrases.intake)}
      <div class="card" style="margin-top:14px">
        <div class="card-head"><h2>证据状态</h2><button class="small" data-action="refresh-post">刷新</button></div>
        ${evidenceTable(d)}
        ${transcribed ? `<p class="small muted" style="margin-top:8px">标“Claude 转写”的原文是从截图读出来的：请在下面的手动区抽查一两段，发现错字直接改了保存。</p>` : ""}
        ${shared}
      </div>
      <div class="card">
        <div class="card-head"><h2>收件箱（inbox）</h2><div class="row"><button class="small" data-action="refresh-post">刷新</button><button class="small ghost" data-action="auto-inbox"${inbox.length ? "" : " disabled"}>按文件名自动归档</button></div></div>
        ${inboxHtml}
      </div>
      ${photos}
      <details class="card"><summary><b>手动录入或修改（备用）</b> <span class="small muted">粘贴原文、上传截图、改工具信息</span></summary>
        <div class="grid grid-2" style="margin-top:14px">${toolCards}</div>
      </details>`;
  }

  document.addEventListener("input", (event) => {
    const el = event.target;
    if (!state.detail || !el.dataset) return;
    if (el.dataset.evText) {
      markDraft(el.dataset.evText, el.value);
      const counter = el.parentElement.querySelector(".small.muted");
      if (counter) counter.textContent = `${L.charCount(el.value).withSpaces} 字`;
    } else if (el.dataset.meta) {
      const tool = el.dataset.meta;
      const current = state.drafts[`meta:${tool}`] || { ...((state.detail.manifest.tools || {})[tool] || {}) };
      current[el.dataset.field] = el.dataset.field === "tested_at" ? L.toIsoWithOffset(el.value) : el.value;
      if (!state.dirty.saved[`meta:${tool}`]) state.dirty.load(`meta:${tool}`, (state.detail.manifest.tools || {})[tool] || {});
      markDraft(`meta:${tool}`, current);
    }
  });

  document.addEventListener("change", async (event) => {
    const el = event.target;
    if (!state.detail || !el.dataset) return;
    if (el.dataset.inboxScope !== undefined) {
      const index = el.dataset.inboxScope;
      const item = state.detail.inbox[Number(index)];
      document.querySelector(`[data-inbox-key="${index}"]`).innerHTML = keyOptions(state.detail, el.value, item.kind);
    }
    if (el.matches("input[type=file][data-upload]") && el.files[0]) {
      const file = el.files[0];
      const result = await run(null, async () => api(`/api/posts/${state.detail.post.post_id}/evidence/file`, { body: { scope: el.dataset.scope, key: el.dataset.key, filename: file.name, data_base64: await readFileBase64(file) } }), "已上传");
      if (result) applyDetail(result);
    }
    if (el.matches("input[type=file][data-photo]") && el.files[0]) {
      const file = el.files[0];
      const result = await run(null, async () => api(`/api/posts/${state.detail.post.post_id}/photo`, { body: { index: Number(el.dataset.photo), filename: file.name, data_base64: await readFileBase64(file) } }), "照片已保存");
      if (result) applyDetail(result);
    }
  });

  savers.ev = async (name) => {
    const [, scope, key] = name.split(":");
    const detail = await api(`/api/posts/${state.detail.post.post_id}/evidence/text`, { body: { scope, key, text: state.drafts[name] } });
    state.dirty.reset(name);
    delete state.drafts[name];
    applyDetail(detail);
    return true;
  };
  savers.meta = async (name) => {
    const tool = name.split(":")[1];
    const detail = await api(`/api/posts/${state.detail.post.post_id}/evidence/meta`, { body: { tool, fields: state.drafts[name] } });
    state.dirty.reset(name);
    delete state.drafts[name];
    applyDetail(detail);
    return true;
  };
  actions["save-ev-text"] = (button) => {
    const name = `ev:${button.dataset.scope}:${button.dataset.key}`;
    if (state.drafts[name] === undefined) return toast("没有改动");
    return run(button, () => savers.ev(name), "原文已保存");
  };
  actions["save-meta"] = (button) => {
    const name = `meta:${button.dataset.tool}`;
    if (!state.drafts[name]) return toast("没有改动");
    return run(button, () => savers.meta(name), "工具信息已保存");
  };
  actions["refresh-post"] = async (button) => {
    const detail = await run(button, () => api(`/api/posts/${state.detail.post.post_id}`));
    if (detail) applyDetail(detail);
  };
  actions["auto-inbox"] = async (button) => {
    const result = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/inbox/auto`, { body: {} }));
    if (result) {
      const ok = result.assigned.filter((item) => !item.error).length;
      toast(ok ? `自动归档 ${ok} 个文件` : "没有能从文件名识别的文件");
      applyDetail(result.detail);
    }
  };
  actions["assign-inbox"] = async (button) => {
    const index = button.dataset.index;
    const scope = document.querySelector(`[data-inbox-scope="${index}"]`).value;
    const key = document.querySelector(`[data-inbox-key="${index}"]`).value;
    if (!key) return toast("这个文件类型没有对应的证据项", "error");
    const detail = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/inbox/assign`, { body: { name: button.dataset.name, scope, key } }), "已归档");
    if (detail) applyDetail(detail);
  };

  // ----------------------------------------------------------------- score
  function checkInput(tool, id, check, value) {
    const attrs = `data-score-tool="${tool}" data-check="${id}"`;
    if ((check.type || "boolean") === "boolean") {
      return `<select ${attrs}>${[["pending", "待评"], ["pass", "通过"], ["fail", "踩坑"]].map(([v, t]) => `<option value="${v}"${(value || "pending") === v ? " selected" : ""}>${t}</option>`).join("")}</select>`;
    }
    if (check.type === "enum") {
      return `<select ${attrs}><option value="">待评</option>${(check.options || []).map((option) => `<option${option === value ? " selected" : ""}>${esc(option)}</option>`).join("")}</select>`;
    }
    if (check.type === "number") {
      return `<input type="number" ${attrs} value="${value === null || value === undefined ? "" : esc(value)}"${check.min !== undefined ? ` min="${check.min}"` : ""}${check.max !== undefined ? ` max="${check.max}"` : ""} step="any">`;
    }
    return `<input type="text" ${attrs} value="${esc(value || "")}">`;
  }

  function suggestionLine(item) {
    if (!item) return "";
    const label = { pass: "通过", fail: "踩坑", unclear: "看不准，请你判断" }[item.value] || item.value;
    return `<div class="sugg"><span class="sugg-tag">Claude 建议</span><b>${esc(label)}</b>${item.reason ? `｜${esc(item.reason)}` : ""}${item.quote ? `｜原文“${esc(item.quote)}”` : ""}</div>`;
  }

  function stepScore(d) {
    const checks = d.scorecard.checks || {};
    const overall = d.scorecard.overall || {};
    const results = state.drafts.scorecard || {};
    const pre = d.prechecks.results || {};
    const sugg = (d.suggestions || {}).tools || {};
    const hasSugg = Object.keys(sugg).length > 0;
    return `
      ${ownerNote("你", hasSugg ? `Claude 已经给出建议判定（${esc((d.suggestions.generated_at || "").slice(0, 16).replace("T", " "))}）。对照截图看一遍：同意就点“采纳”，不同意就直接改；每个工具写一句你自己的感受（这句只能你写）。最后点“保存判定”。` : "Claude 还没给出建议：先在“整理证据”那一步把截图交给 Claude。也可以直接手动判定。", hasSugg ? "" : d.phrases.intake)}
      ${hasSugg ? `<div class="row" style="margin-top:12px"><button class="primary" data-action="accept-all">采纳全部建议</button><span class="small muted">采纳只是填进草稿，保存前都能改。“看不准”的项不会被采纳，需要你来定。</span></div>` : ""}
      <div class="grid" style="margin-top:14px">${d.post.tools.map((tool) => {
        const result = results[tool] || { checks: {}, notes: {} };
        const hints = pre[tool] || [];
        const toolSugg = sugg[tool] || { checks: {} };
        return `<div class="tool-card">
          <div class="card-head"><h3>${esc(toolName(tool))}</h3>${sugg[tool] ? `<button class="small" data-action="accept-tool" data-tool="${tool}">采纳这一家的建议</button>` : ""}</div>
          <label class="gut">你的一句真实感受（必填，Claude 不会替你写）<input type="text" data-score-tool="${tool}" data-field="gut_reaction" value="${esc(result.gut_reaction || "")}" placeholder="随手写，比如：格式最好看，但把客户反馈吹过头了"></label>
          <div>${Object.entries(checks).map(([id, check]) => {
            const value = (result.checks || {})[id];
            const note = (result.notes || {})[id] || "";
            const related = hints.filter((hint) => hint.check === id);
            const item = (toolSugg.checks || {})[id];
            return `<div class="check">
              <div><div class="name">${esc(check.name)}</div><div class="crit">${check.pass_criteria ? `通过：${esc(check.pass_criteria)}` : ""}${check.fail ? `<br>踩坑：${esc(check.fail)}` : ""}${check.options ? esc(check.options.join(" / ")) : ""}</div></div>
              <div>${checkInput(tool, id, check, value)}${item && item.value !== "unclear" ? `<button class="small ghost" style="margin-top:6px" data-action="accept-one" data-tool="${tool}" data-check="${id}">采纳</button>` : ""}</div>
              <div>${(check.type || "boolean") === "boolean" ? `<input type="text" data-note-tool="${tool}" data-check="${id}" value="${esc(note)}" placeholder="依据：引用回答里的原句">` : ""}</div>
              ${item ? `<div class="pre">${suggestionLine(item)}</div>` : ""}
              ${related.length ? `<div class="pre">${related.map((hint) => `<span class="${hint.status === "flag" ? "hit" : "fine"}">${hint.status === "flag" ? "⚠ " : hint.status === "ok" ? "✓ " : "… "}${esc(hint.label)}：${esc(hint.detail)}</span>`).join("")}</div>` : ""}
            </div>`;
          }).join("")}</div>
          <div class="sep"></div>
          ${toolSugg.verdict || toolSugg.summary ? `<div class="pre" style="margin-bottom:8px">${suggestionLine({ value: "", reason: [toolSugg.total_score ? `${toolSugg.total_score} 分` : "", toolSugg.verdict, toolSugg.summary].filter(Boolean).join("｜") })}</div>` : ""}
          <div class="field-row">
            <label>${esc(overall.label || "总评（1–5）")}${overall.required === false ? "（可选）" : ""}<input type="number" min="1" max="5" step="0.5" data-score-tool="${tool}" data-field="total_score" value="${result.total_score === null || result.total_score === undefined ? "" : esc(result.total_score)}"></label>
            <label>结论（上图用，短）<input type="text" data-score-tool="${tool}" data-field="verdict" value="${esc(result.verdict || "")}" placeholder="如：改两处就能交"></label>
          </div>
          <label style="margin-top:8px">一句话结论与依据<input type="text" data-score-tool="${tool}" data-field="summary" value="${esc(result.summary || "")}"></label>
          <label style="margin-top:8px">会不会继续用，为什么（可选）<input type="text" data-score-tool="${tool}" data-field="keep_using" value="${esc(result.keep_using || "")}"></label>
        </div>`;
      }).join("")}</div>
      <div class="row end" style="margin-top:14px"><button class="primary" data-action="save-scorecard">保存判定</button></div>
      <p class="small muted" style="text-align:right;margin-top:6px">保存后在 Cowork 里说「${esc(d.phrases.draft)}」，Claude 会用你的判定和感受写定稿。</p>`;
  }

  function acceptInto(results, tool, ids) {
    const sugg = ((state.detail.suggestions || {}).tools || {})[tool];
    if (!sugg) return results;
    const entry = L.applySuggestions(results[tool] || { checks: {}, notes: {} }, sugg, ids);
    return { ...results, [tool]: entry };
  }
  actions["accept-all"] = () => {
    let results = JSON.parse(JSON.stringify(state.drafts.scorecard || {}));
    state.detail.post.tools.forEach((tool) => { results = acceptInto(results, tool, null); });
    markDraft("scorecard", results);
    renderPostBody();
    toast("已填进草稿，看一遍后点“保存判定”");
  };
  actions["accept-tool"] = (button) => {
    markDraft("scorecard", acceptInto(JSON.parse(JSON.stringify(state.drafts.scorecard || {})), button.dataset.tool, null));
    renderPostBody();
  };
  actions["accept-one"] = (button) => {
    markDraft("scorecard", acceptInto(JSON.parse(JSON.stringify(state.drafts.scorecard || {})), button.dataset.tool, [button.dataset.check]));
    renderPostBody();
  };

  function scoreEvent(el) {
    const tool = el.dataset.scoreTool || el.dataset.noteTool;
    const results = JSON.parse(JSON.stringify(state.drafts.scorecard || {}));
    const entry = results[tool] || { checks: {}, notes: {} };
    entry.checks = entry.checks || {};
    entry.notes = entry.notes || {};
    if (el.dataset.noteTool) {
      entry.notes[el.dataset.check] = el.value;
    } else if (el.dataset.check) {
      const check = state.detail.scorecard.checks[el.dataset.check];
      if (check.type === "number") {
        const parsed = L.parseScore(el.value, check.min, check.max);
        entry.checks[el.dataset.check] = parsed === undefined ? el.value : parsed;
      } else {
        entry.checks[el.dataset.check] = el.value === "pending" ? null : el.value;
      }
    } else if (el.dataset.field === "total_score") {
      const parsed = L.parseScore(el.value, 1, 5);
      entry.total_score = parsed === undefined ? el.value : parsed;
    } else {
      entry[el.dataset.field] = el.value;
    }
    results[tool] = entry;
    markDraft("scorecard", results);
  }
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (el.dataset && (el.dataset.scoreTool || el.dataset.noteTool)) scoreEvent(el);
  });
  document.addEventListener("change", (event) => {
    const el = event.target;
    if (el.tagName === "SELECT" && el.dataset && el.dataset.scoreTool) scoreEvent(el);
  });

  savers.scorecard = async () => {
    const detail = await api(`/api/posts/${state.detail.post.post_id}/scorecard`, { body: { tool_results: state.drafts.scorecard } });
    state.dirty.reset("scorecard");
    applyDetail(detail);
    return true;
  };
  actions["save-scorecard"] = (button) => {
    if (!state.dirty.isDirty("scorecard")) return toast("没有改动");
    return run(button, savers.scorecard, "判定已保存");
  };

  // ------------------------------------------------------------------ copy
  function stepCopy(d) {
    const lint = d.lint;
    const cardsDraft = state.drafts.cards || {};
    const cardIds = Object.keys(cardsDraft).filter((id) => id !== "photo_captions");
    const photoIndexes = (d.topic.images || []).filter((image) => image.kind === "photo").map((image) => image.index);
    return `
      ${ownerNote("Claude 起草", `判定和感受都保存后，Claude 按选题手册的口吻写标题、正文、标签、置顶评论和图片上的文字卡，并把你的原话放进去。你在这里看、直接改。`, d.phrases.draft)}
      <div class="grid grid-2" style="margin-top:14px">
        <div class="card">
          <div class="card-head"><h2>copy.md</h2><button class="primary small" data-action="save-copy">保存文案</button></div>
          <textarea class="code" data-copy-editor>${esc(state.drafts.copy || "")}</textarea>
          <p class="small muted" style="margin-top:6px">第 1 个标题就是要用的标题。【】里填实测结果，填不出来说明还没测。</p>
        </div>
        <div class="stack">
          <div class="card">
            <h2>发布前检查</h2>
            <div class="stats" style="margin:8px 0"><span>标题 <b>${lint.stats.title_length}</b>/20 字</span><span>正文 <b>${lint.stats.body_length}</b> 字</span><span>标签 <b>${lint.stats.tag_count}</b> 个</span></div>
            ${lint.errors.map((item) => `<div class="lint-item err">${esc(item.message)}</div>`).join("") || `<div class="lint-item">✓ 没有必须处理的问题</div>`}
            ${lint.warnings.map((item) => `<div class="lint-item wrn">${esc(item.message)}</div>`).join("")}
            <div class="sep"></div>
            ${lint.reminders.map((item) => `<div class="lint-item rem">${esc(item)}</div>`).join("")}
            <p class="small muted" style="margin-top:8px">检查的是已保存的版本。</p>
          </div>
          <div class="card">
            <div class="card-head"><h2>结果摘要（可选）</h2><button class="small" data-action="handoff">生成 handoff.md</button></div>
            <p class="small muted">把这一期的结果、你的原话和证据路径汇总成一个文件。Claude 起草时会自己读项目文件，一般不需要；想换一个对话或者自己留档时用。</p>
            <div id="handoff-out"></div>
          </div>
        </div>
      </div>
      ${cardIds.length || photoIndexes.length ? `<div class="card">
        <div class="card-head"><h2>图片上的文字卡</h2><button class="primary small" data-action="save-cards">保存文字卡</button></div>
        ${d.card_problems.map((item) => `<div class="lint-item err">${esc(item.message)}</div>`).join("")}
        <div class="grid grid-2" style="margin-top:8px">${cardIds.map((id) => `<div class="tool-card"><label>标题<input type="text" data-card="${id}" data-card-field="title" value="${esc(cardsDraft[id].title || "")}"></label><label style="margin-top:8px">每行一条<textarea rows="6" data-card="${id}" data-card-field="lines">${esc((cardsDraft[id].lines || []).join("\n"))}</textarea></label></div>`).join("")}
        ${photoIndexes.map((index) => `<div class="tool-card"><label>照片 ${index} 的说明<input type="text" data-card="photo_captions" data-card-field="${index}" value="${esc(((cardsDraft.photo_captions || {})[index]) || "")}"></label></div>`).join("")}</div>
      </div>` : ""}`;
  }

  document.addEventListener("input", (event) => {
    const el = event.target;
    if (!el.dataset) return;
    if (el.dataset.copyEditor !== undefined) markDraft("copy", el.value);
    if (el.dataset.card) {
      const cards = JSON.parse(JSON.stringify(state.drafts.cards || {}));
      if (el.dataset.card === "photo_captions") {
        cards.photo_captions = cards.photo_captions || {};
        cards.photo_captions[el.dataset.cardField] = el.value;
      } else {
        cards[el.dataset.card] = cards[el.dataset.card] || { title: "", lines: [] };
        cards[el.dataset.card][el.dataset.cardField] = el.dataset.cardField === "lines" ? el.value.split("\n").filter((line) => line.trim()) : el.value;
      }
      markDraft("cards", cards);
    }
  });

  savers.copy = async () => {
    const detail = await api(`/api/posts/${state.detail.post.post_id}/copy`, { body: { text: state.drafts.copy } });
    state.dirty.reset("copy");
    applyDetail(detail);
    return true;
  };
  savers.cards = async () => {
    const detail = await api(`/api/posts/${state.detail.post.post_id}/cards`, { body: { cards: state.drafts.cards } });
    state.dirty.reset("cards");
    applyDetail(detail);
    return true;
  };
  actions["save-copy"] = (button) => (state.dirty.isDirty("copy") ? run(button, savers.copy, "文案已保存") : toast("没有改动"));
  actions["save-cards"] = (button) => (state.dirty.isDirty("cards") ? run(button, savers.cards, "文字卡已保存") : toast("没有改动"));
  actions.handoff = async (button) => {
    const result = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/handoff`, { body: {} }), "交接包已生成");
    if (result) document.getElementById("handoff-out").innerHTML = `<p class="small" style="margin:8px 0">已写入 <code>${esc(result.path)}</code></p>${copyBlock("handoff.md", result.text)}`;
  };

  // ---------------------------------------------------------------- review
  function stepReview(d) {
    const r = d.readiness;
    const reviewer = storage("xhs-reviewer") || "";
    const blockers = r.blockers.filter((item) => !["assets_stale"].includes(item.code));
    return `
      <div class="grid grid-2">
        <div class="card stack">
          <h2>放行状态</h2>
          ${r.publishable ? `<div class="banner ok">发布包已放行。去“发布与数据”复制文案、下载图片。</div>` : r.content_verified ? `<div class="banner ok">复核已完成。下一步：到“图片”重新生成一次（去掉草稿标识）。</div>` : r.content_ready_for_review ? `<div class="banner amber">内容都齐了，可以复核。</div>` : `<div class="banner warn">还不能复核：先补齐下面这些。</div>`}
          <div class="blockers">${blockers.length ? blockers.map((item) => `<div class="blocker"><details${item.details && item.details.length ? "" : " open"}><summary>${esc(item.message)}</summary>${item.details && item.details.length ? `<ul>${item.details.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>` : ""}</details></div>`).join("") : `<div class="blocker ok">✓ 证据、评分、文案都齐了</div>`}</div>
          ${(r.changed_since_review || []).length ? `<div class="banner amber">复核后改动过的文件：<br>${r.changed_since_review.map((path) => `<code>${esc(path)}</code>`).join("<br>")}</div>` : ""}
        </div>
        <div class="card stack">
          <h2>一键复核</h2>
          <p class="small"><b>这一步只能你来点。</b>Claude 不会替你复核，也不会替你发布。</p>
          <p class="small muted">点下去之前，请逐条对照每个工具的原始回答，确认评分、结论和文案里的每个判断都有依据。复核会：把评分卡设为已核验、记录测试日期和复核人、锁定评分卡/文案/文字卡/红框/篇目设置和全部证据的指纹。之后任何一个文件改动，放行都会自动失效。</p>
          <label>复核人<input type="text" id="reviewer" value="${esc(reviewer)}" placeholder="你的名字"></label>
          <label>测试日期（留空则取各工具测试时间里最晚的一天）<input type="date" id="test-date" value="${esc(d.scorecard.evaluation_date || "")}"></label>
          <label style="color:var(--ink);font-weight:700"><input type="checkbox" id="confirm-review"> 我已逐条对照原文核对</label>
          <div class="row"><button class="primary" data-action="review"${r.content_ready_for_review ? "" : " disabled"}>我已逐条核对，完成复核</button></div>
          ${d.manifest.reviewed_at ? `<p class="small muted">上次复核：${esc(d.manifest.reviewed_by || "")} · ${esc(d.manifest.reviewed_at)}</p>` : ""}
        </div>
      </div>`;
  }

  actions.review = async (button) => {
    if (state.dirty.isDirty()) return toast("先保存或放弃未保存的修改", "error");
    if (!document.getElementById("confirm-review").checked) return toast("请先勾选“我已逐条对照原文核对”", "error");
    const reviewer = document.getElementById("reviewer").value.trim();
    if (!reviewer) return toast("请填写复核人", "error");
    storage("xhs-reviewer", reviewer);
    const testDate = document.getElementById("test-date").value || undefined;
    try {
      button.disabled = true;
      const result = await api(`/api/posts/${state.detail.post.post_id}/review`, { body: { reviewed_by: reviewer, test_date: testDate, confirm: true }, allow: [409] });
      if (result.status === "blocked") toast("还有没补齐的内容，见左侧列表", "error");
      else toast(`复核完成，已锁定 ${result.locked_files.length} 个文件`);
      applyDetail(result.detail);
    } catch (error) {
      toast(error.message, "error");
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  };

  // ---------------------------------------------------------------- images
  function stepImages(d) {
    const images = d.images;
    const cover = d.post.cover || {};
    const palettes = state.config.brand.palettes || {};
    const pairImages = (d.topic.images || []).map((image, position) => ({ ...image, position })).filter((image) => image.kind === "evidence_pair");
    const imageKeys = (d.topic.evidence.per_tool || []).filter((spec) => spec.kind === "image");
    const sharedImageKeys = (d.topic.evidence.shared || []).filter((spec) => spec.kind === "image");
    const selectedScope = state.editor && (d.post.tools.includes(state.editor.tool) || (state.editor.tool === "shared" && sharedImageKeys.length)) ? state.editor.tool : (imageKeys.length ? d.post.tools[0] : "shared");
    const editorKeys = selectedScope === "shared" ? sharedImageKeys : imageKeys;
    const coverFile = images.files.find((file) => file.kind === "cover");
    const verified = d.readiness.content_verified;
    return `
      ${ownerNote("Claude 生成", verified ? "复核已通过：Claude 会生成不带草稿标识的终版图片，你也可以直接点下面的按钮。" : "Claude 起草时会标好红框、生成草稿图。你在这里看封面和每张图，红框不准就拖一个新的。", verified ? d.phrases.final : "")}
      <div class="grid grid-2" style="margin-top:14px">
        <div class="card stack">
          <h2>封面</h2>
          <div class="field-row">
            <label>顶部标签（≤12 字）<input type="text" id="cover-tag" value="${esc(cover.tag || "")}"></label>
            <label>配色<select id="cover-palette">${Object.entries(palettes).map(([key, value]) => `<option value="${key}"${key === cover.palette ? " selected" : ""}>${esc(value.label || key)}</option>`).join("")}</select></label>
          </div>
          <label>大字标题（每行 ≤16 字，1–4 行；用提问，不预设结果）<textarea id="cover-lines" rows="3">${esc((cover.lines || []).join("\n"))}</textarea></label>
          ${pairImages.map((image) => {
            const picks = ((d.post.picks || {})[String(image.position)]) || d.post.tools.slice(0, 2);
            return `<label>${esc(image.label)}：选两家<div class="row" style="margin-top:4px">${[0, 1].map((slot) => `<select data-pick="${image.position}" data-slot="${slot}" style="max-width:180px">${d.post.tools.map((tool) => `<option value="${tool}"${picks[slot] === tool ? " selected" : ""}>${esc(toolName(tool))}</option>`).join("")}</select>`).join("")}</div></label>`;
          }).join("")}
          <div class="row"><button class="small" data-action="save-cover">保存封面设置</button></div>
          <div class="sep"></div>
          <div class="row"><button class="primary" data-action="render">${verified ? "生成终版图片" : "生成草稿图片"}</button><span class="small muted">${verified ? "复核已通过，这次生成不带草稿标识" : "复核前生成的每张图都带“草稿”标识，不能发布"}</span></div>
          ${images.generated_at ? `<p class="small muted">上次生成：${esc(images.generated_at)} · ${images.draft ? "草稿" : "终版"} · 导出引擎 ${esc(images.engine || "")}${images.png_ok === false ? " · <b style='color:var(--warn)'>PNG 导出失败，请安装 Google Chrome</b>" : ""}</p>` : ""}
        </div>
        <div class="card stack">
          <h2>信息流缩略图预览</h2>
          <p class="small muted">小红书双列信息流里封面大约这么大，看大字是不是一眼能读。</p>
          <div class="feed">
            <div class="item">${coverFile ? `<img src="${coverFile.url}?v=${encodeURIComponent(images.generated_at || "")}" alt="封面">` : `<div class="fake"></div>`}<div class="cap">${esc((d.copy_parsed.titles || [])[0] || d.topic.title)}</div></div>
            <div class="item"><div class="fake b"></div><div class="cap">别人的笔记</div></div>
            <div class="item"><div class="fake b"></div><div class="cap">别人的笔记</div></div>
            <div class="item"><div class="fake"></div><div class="cap">别人的笔记</div></div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><h2>整套图片</h2>${images.files.length ? chip(images.draft ? "草稿" : "终版", images.draft ? "warn" : "ok") : ""}</div>
        ${images.files.length ? `<div class="gallery">${images.files.map((file) => `<figure><a href="${file.url}?v=${encodeURIComponent(images.generated_at || "")}" target="_blank" rel="noopener"><img src="${file.url}?v=${encodeURIComponent(images.generated_at || "")}" alt="${esc(file.label)}"></a><figcaption>${String(file.index).padStart(2, "0")} ${esc(file.label)}${file.tool ? ` · ${esc(toolName(file.tool))}` : ""}</figcaption></figure>`).join("")}</div>` : `<div class="empty">还没生成。点上面的“生成草稿图片”。</div>`}
      </div>
      ${imageKeys.length || sharedImageKeys.length ? `<div class="card">
        <div class="card-head"><h2>截图标注与隐私遮挡</h2><div class="row">
          <select id="hl-tool">${d.post.tools.map((tool) => `<option value="${tool}"${selectedScope === tool ? " selected" : ""}>${esc(toolName(tool))}</option>`).join("")}${sharedImageKeys.length ? `<option value="shared"${selectedScope === "shared" ? " selected" : ""}>本期共用</option>` : ""}</select>
          <select id="hl-key">${editorKeys.map((spec) => `<option value="${esc(spec.key)}"${state.editor && state.editor.key === spec.key ? " selected" : ""}>${esc(spec.label)}</option>`).join("")}</select>
        </div></div>
        <p class="small muted">先选“隐私遮挡”并拖动盖住头像、昵称和任何个人信息；遮挡会写入导出图，原始证据文件不会被改动。再选“红框”标记要讲的内容。上下滑块只改变发布图显示范围。</p>
        <div class="grid grid-2" style="margin-top:10px">
          <div id="hl-canvas"></div>
          <div class="stack">
            <label>拖动模式<select id="hl-mode"><option value="mask"${state.editorMode === "mask" ? " selected" : ""}>隐私遮挡（不透明）</option><option value="box"${state.editorMode === "box" ? " selected" : ""}>红框说明</option></select></label>
            <label>显示范围：从 <span id="crop0-v"></span>% 到 <span id="crop1-v"></span>%<input type="range" id="crop0" min="0" max="95" step="1"><input type="range" id="crop1" min="5" max="100" step="1"></label>
            <div id="hl-list"></div>
            <div class="row"><button class="primary small" data-action="save-highlights">保存标注</button><button class="small" data-action="clear-highlights">清空标注</button></div>
          </div>
        </div>
      </div>` : ""}`;
  }

  function currentHighlights(tool, key) {
    const saved = ((state.detail.highlights || {})[tool] || {})[key] || {};
    return { boxes: (saved.boxes || []).map((box) => ({ ...box })), masks: (saved.masks || []).map((mask) => ({ ...mask })), crop: { y0: (saved.crop || {}).y0 || 0, y1: (saved.crop || {}).y1 || 1 } };
  }

  function mountEditor() {
    const canvas = document.getElementById("hl-canvas");
    if (!canvas) return;
    const tool = document.getElementById("hl-tool").value;
    const key = document.getElementById("hl-key").value;
    if (!state.editor || state.editor.tool !== tool || state.editor.key !== key || !state.dirty.isDirty("highlights")) {
      state.editor = { tool, key, ...currentHighlights(tool, key) };
      state.dirty.load("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
    }
    const fileRows = tool === "shared" ? state.detail.evidence.shared : ((state.detail.evidence.per_tool[tool] || {}).files || []);
    const row = (fileRows || []).find((item) => item.key === key);
    if (!row || !row.path) {
      canvas.innerHTML = `<div class="empty">这张截图还没录入</div>`;
      drawEditor();
      return;
    }
    canvas.innerHTML = `<div class="editor-wrap" id="hl-wrap"><img id="hl-img" src="/api/posts/${state.detail.post.post_id}/evidence-file?scope=${tool}&key=${key}&v=${row.mtime || 0}" draggable="false" alt=""></div>`;
    const img = document.getElementById("hl-img");
    img.onload = drawEditor;
    const wrap = document.getElementById("hl-wrap");
    let start = null;
    let ghost = null;
    wrap.addEventListener("pointerdown", (event) => {
      const rect = img.getBoundingClientRect();
      start = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      ghost = document.createElement("div");
      ghost.className = state.editorMode === "mask" ? "privacy-box" : "box";
      wrap.appendChild(ghost);
      wrap.setPointerCapture(event.pointerId);
    });
    wrap.addEventListener("pointermove", (event) => {
      if (!start) return;
      const rect = img.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      Object.assign(ghost.style, { left: `${Math.min(start.x, x)}px`, top: `${Math.min(start.y, y)}px`, width: `${Math.abs(x - start.x)}px`, height: `${Math.abs(y - start.y)}px` });
    });
    wrap.addEventListener("pointerup", (event) => {
      if (!start) return;
      const rect = img.getBoundingClientRect();
      const box = L.boxFromDrag(start.x, start.y, event.clientX - rect.left, event.clientY - rect.top, rect.width, rect.height);
      start = null;
      if (ghost) ghost.remove();
      if (box) {
        if (state.editorMode === "mask") state.editor.masks.push({ x: box.x, y: box.y, w: box.w, h: box.h });
        else state.editor.boxes.push(box);
        markDraft("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
        drawEditor();
      }
    });
  }

  function drawEditor() {
    const ed = state.editor;
    const img = document.getElementById("hl-img");
    const wrap = document.getElementById("hl-wrap");
    const c0 = document.getElementById("crop0");
    const c1 = document.getElementById("crop1");
    if (c0) { c0.value = Math.round(ed.crop.y0 * 100); c1.value = Math.round(ed.crop.y1 * 100); }
    const v0 = document.getElementById("crop0-v");
    if (v0) { v0.textContent = Math.round(ed.crop.y0 * 100); document.getElementById("crop1-v").textContent = Math.round(ed.crop.y1 * 100); }
    if (img && wrap) {
      wrap.querySelectorAll(".box, .privacy-box, .shade").forEach((el) => el.remove());
      const h = img.clientHeight;
      const w = img.clientWidth;
      ed.boxes.forEach((box, index) => {
        const el = document.createElement("div");
        el.className = "box";
        Object.assign(el.style, { left: `${box.x * w}px`, top: `${box.y * h}px`, width: `${box.w * w}px`, height: `${box.h * h}px` });
        el.innerHTML = `<span>${index + 1}</span>`;
        wrap.appendChild(el);
      });
      ed.masks.forEach((mask) => {
        const el = document.createElement("div");
        el.className = "privacy-box";
        Object.assign(el.style, { left: `${mask.x * w}px`, top: `${mask.y * h}px`, width: `${mask.w * w}px`, height: `${mask.h * h}px` });
        wrap.appendChild(el);
      });
      const top = document.createElement("div");
      top.className = "shade";
      Object.assign(top.style, { top: "0", height: `${ed.crop.y0 * h}px` });
      const bottom = document.createElement("div");
      bottom.className = "shade";
      Object.assign(bottom.style, { top: `${ed.crop.y1 * h}px`, height: `${(1 - ed.crop.y1) * h}px` });
      wrap.append(top, bottom);
    }
    const list = document.getElementById("hl-list");
    if (list) {
      const masks = ed.masks.length ? ed.masks.map((mask, index) => `<div class="row" style="margin-bottom:6px"><span class="chip dark">遮挡 ${index + 1}</span><span class="small muted">${Math.round(mask.x * 100)}%, ${Math.round(mask.y * 100)}%</span><button class="small danger" data-action="remove-mask" data-index="${index}">删除</button></div>`).join("") : `<p class="small muted">还没有隐私遮挡区。</p>`;
      const boxes = ed.boxes.length ? ed.boxes.map((box, index) => `<div class="row" style="margin-bottom:6px"><span class="chip warn">红框 ${index + 1}</span><input type="text" value="${esc(box.note || "")}" data-hl-note="${index}" placeholder="一句说明，如：编数据：点击率提升20%" maxlength="30" style="flex:1"><button class="small danger" data-action="remove-box" data-index="${index}">删除</button></div>`).join("") : `<p class="small muted">还没有红框。</p>`;
      list.innerHTML = `<b class="small">隐私遮挡</b>${masks}<b class="small">红框说明</b>${boxes}`;
    }
  }

  document.addEventListener("input", (event) => {
    const el = event.target;
    if (!state.editor) return;
    if (el.id === "crop0" || el.id === "crop1") {
      let y0 = Number(document.getElementById("crop0").value) / 100;
      let y1 = Number(document.getElementById("crop1").value) / 100;
      if (y1 <= y0 + 0.05) { if (el.id === "crop0") y0 = Math.max(0, y1 - 0.05); else y1 = Math.min(1, y0 + 0.05); }
      state.editor.crop = { y0, y1 };
      markDraft("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
      drawEditor();
    }
    if (el.dataset && el.dataset.hlNote !== undefined) {
      state.editor.boxes[Number(el.dataset.hlNote)].note = el.value;
      markDraft("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
    }
  });
  document.addEventListener("change", (event) => {
    const el = event.target;
    if (el.id === "hl-mode") {
      state.editorMode = el.value;
      return;
    }
    if (el.id === "hl-tool" || el.id === "hl-key") {
      if (state.dirty.isDirty("highlights")) {
        toast("先保存当前截图的标注", "error");
        document.getElementById("hl-tool").value = state.editor.tool;
        document.getElementById("hl-key").value = state.editor.key;
        return;
      }
      if (el.id === "hl-tool") {
        const specs = el.value === "shared" ? (state.detail.topic.evidence.shared || []) : (state.detail.topic.evidence.per_tool || []);
        document.getElementById("hl-key").innerHTML = specs.filter((spec) => spec.kind === "image").map((spec) => `<option value="${esc(spec.key)}">${esc(spec.label)}</option>`).join("");
      }
      mountEditor();
    }
  });
  window.addEventListener("resize", () => { if (state.editor && document.getElementById("hl-img")) drawEditor(); });

  actions["remove-box"] = (button) => {
    state.editor.boxes.splice(Number(button.dataset.index), 1);
    markDraft("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
    drawEditor();
  };
  actions["remove-mask"] = (button) => {
    state.editor.masks.splice(Number(button.dataset.index), 1);
    markDraft("highlights", { boxes: state.editor.boxes, masks: state.editor.masks, crop: state.editor.crop });
    drawEditor();
  };
  actions["clear-highlights"] = () => {
    state.editor.boxes = [];
    state.editor.masks = [];
    state.editor.crop = { y0: 0, y1: 1 };
    markDraft("highlights", { boxes: [], masks: [], crop: state.editor.crop });
    drawEditor();
  };
  savers.highlights = async () => {
    const ed = state.editor;
    const detail = await api(`/api/posts/${state.detail.post.post_id}/highlights`, { body: { tool: ed.tool, key: ed.key, boxes: ed.boxes, masks: ed.masks, crop: ed.crop } });
    state.dirty.reset("highlights");
    applyDetail(detail);
    return true;
  };
  actions["save-highlights"] = (button) => (state.dirty.isDirty("highlights") ? run(button, savers.highlights, "截图标注已保存") : toast("没有改动"));
  actions["save-cover"] = async (button) => {
    const picks = {};
    document.querySelectorAll("[data-pick]").forEach((el) => {
      picks[el.dataset.pick] = picks[el.dataset.pick] || [];
      picks[el.dataset.pick][Number(el.dataset.slot)] = el.value;
    });
    const body = {
      cover: { tag: document.getElementById("cover-tag").value.trim(), palette: document.getElementById("cover-palette").value, lines: document.getElementById("cover-lines").value.split("\n").map((line) => line.trim()).filter(Boolean) },
      picks,
    };
    const detail = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/settings`, { body }), "封面设置已保存");
    if (detail) applyDetail(detail);
  };
  actions.render = async (button) => {
    if (state.dirty.isDirty()) return toast("先保存或放弃未保存的修改", "error");
    const result = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/render`, { body: {}, allow: [500] }));
    if (result) {
      toast(result.status === "rendered" ? (result.draft ? "草稿图片已生成" : "终版图片已生成") : "PNG 导出失败：请安装 Google Chrome", result.status === "rendered" ? "" : "error");
      applyDetail(result.detail);
    }
  };

  // --------------------------------------------------------------- publish
  function stepPublish(d) {
    const r = d.readiness;
    const parsed = d.copy_parsed;
    const metrics = Object.fromEntries((d.metrics || []).map((row) => [row.checkpoint, row]));
    const fields = [["views", "浏览"], ["likes", "赞"], ["saves", "藏"], ["comments", "评"], ["shares", "分享"], ["new_followers", "新增关注"], ["production_minutes", "制作分钟"]];
    const legacy = d.post.post_id === "post-01-weekly-report" ? storage("xhs-post-01-review-draft-v1") : null;
    const pkg = r.publishable ? `
      <div class="card stack">
        <div class="card-head"><h2>发布包</h2>${chip("已放行", "ok")}</div>
        ${copyBlock("标题", parsed.titles[0] || "")}
        ${copyBlock("正文", parsed.body)}
        ${copyBlock("标签", parsed.tags)}
        ${copyBlock("置顶评论（发布后发在评论区）", parsed.pin)}
        <div class="gallery">${d.images.files.map((file) => `<figure><img src="${file.url}" alt=""><figcaption><a href="${file.url}?download=1">下载 ${String(file.index).padStart(2, "0")}</a></figcaption></figure>`).join("")}</div>
        <div class="stack">${d.lint.reminders.map((item) => `<label style="color:var(--ink);font-weight:600"><input type="checkbox"> ${esc(item)}</label>`).join("")}</div>
        <div class="row"><label>实际发布时间<input type="datetime-local" id="published-at"></label><button class="primary" data-action="mark-published">标记为已发布</button></div>
        ${d.slot && d.slot.status === "已发布" ? `<p class="small muted">已标记发布：${esc(d.slot.published_at || "")}</p>` : ""}
      </div>` : `
      <div class="card"><h2>发布包</h2><div class="banner warn" style="margin-top:8px">还没放行：${esc((r.blockers[0] || {}).message || "")}</div><p class="small muted" style="margin-top:8px">放行后这里会出现可复制的标题、正文、标签、置顶评论和图片下载。</p></div>`;
    return `${pkg}
      <div class="card">
        <div class="card-head"><h2>发布后数据</h2><span class="small muted">在创作者中心看每篇的数据，按 24 小时 / 72 小时 / 7 天回填</span></div>
        ${legacy ? `<div class="banner amber" style="margin-bottom:10px">浏览器里有旧版工作台存的首篇复盘草稿。<button class="small" data-action="import-legacy-review">导入到数据表</button></div>` : ""}
        <div class="table-wrap"><table class="data"><thead><tr><th>时间点</th>${fields.map(([, label]) => `<th>${label}</th>`).join("")}<th>备注</th><th></th></tr></thead><tbody>
          ${["24h", "72h", "7d"].map((cp) => `<tr>${[`<td><b>${cp}</b></td>`].concat(fields.map(([key]) => `<td><input type="number" min="0" data-metric="${cp}" data-field="${key}" value="${esc((metrics[cp] || {})[key] || "")}" style="width:84px"></td>`)).join("")}<td><input type="text" data-metric="${cp}" data-field="notes" value="${esc((metrics[cp] || {}).notes || "")}"></td><td><button class="small" data-action="save-metric" data-cp="${cp}">保存</button></td></tr>`).join("")}
        </tbody></table></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>评论点菜</h2></div>
        <div class="row"><input type="text" id="request-text" placeholder="评论里点的菜，如：测一下AI写小红书文案" style="max-width:420px"><button class="small" data-action="add-request">记一笔</button><a class="small" href="#/review">查看点菜清单</a></div>
      </div>`;
  }

  actions["save-metric"] = async (button) => {
    const cp = button.dataset.cp;
    const row = { post_id: state.detail.post.post_id, checkpoint: cp, published_at: (state.detail.slot || {}).published_at || "" };
    document.querySelectorAll(`[data-metric="${cp}"]`).forEach((el) => { row[el.dataset.field] = el.value; });
    await run(button, () => api("/api/metrics", { body: { row } }), `${cp} 数据已保存`);
  };
  actions["add-request"] = async (button) => {
    const text = document.getElementById("request-text").value.trim();
    if (!text) return toast("先写下点的菜", "error");
    const ok = await run(button, () => api("/api/requests", { body: { request: text, post_id: state.detail.post.post_id } }), "已记下");
    if (ok) document.getElementById("request-text").value = "";
  };
  actions["mark-published"] = async (button) => {
    const value = document.getElementById("published-at").value;
    if (!value) return toast("请填写实际发布时间", "error");
    const ok = await run(button, () => api(`/api/posts/${state.detail.post.post_id}/published`, { body: { published_at: L.toIsoWithOffset(value) } }), "已标记为已发布");
    if (ok) { const detail = await api(`/api/posts/${state.detail.post.post_id}`); applyDetail(detail); }
  };
  actions["import-legacy-review"] = async (button) => {
    let legacy = null;
    try { legacy = JSON.parse(storage("xhs-post-01-review-draft-v1") || "null"); } catch (error) { legacy = null; }
    if (!legacy) return;
    const map = { views: "views", likes: "likes", saves: "saves", comments: "comments", followers: "new_followers" };
    for (const cp of ["24", "72"]) {
      const row = { post_id: state.detail.post.post_id, checkpoint: `${cp}h`, published_at: legacy.publishedAt ? L.toIsoWithOffset(legacy.publishedAt) : "", notes: cp === "72" ? [legacy.learning, legacy.nextTopic].filter(Boolean).join("；") : "" };
      let any = false;
      Object.entries(map).forEach(([from, to]) => { if (legacy[from + cp]) { row[to] = legacy[from + cp]; any = true; } });
      if (any) await run(button, () => api("/api/metrics", { body: { row } }));
    }
    storage("xhs-post-01-review-draft-v1", "");
    toast("已导入");
    const detail = await api(`/api/posts/${state.detail.post.post_id}`);
    applyDetail(detail);
  };

  // ============================================================== ACCOUNT
  async function renderAccount() {
    const [account, benchmarks] = await Promise.all([api("/api/account"), api("/api/benchmarks")]);
    if (!state.dirty.isDirty("account")) loadDraft("account", account);
    const draft = state.drafts.account;
    const audit = draft.audit;
    const brand = state.config.brand;
    let legacy = null;
    try { legacy = JSON.parse(storage("xhs-account-audit-draft-v1") || "null"); } catch (error) { legacy = null; }
    const serverEmpty = !audit.nickname && !audit.bio && !audit.recent_ten;
    const followers = draft.followers || [];
    app.innerHTML = `
      <div class="page-head"><div><h1>账号</h1><p>先盘点现有账号，再改名、改简介、处理旧帖。这里的内容存在 <code>ops/account_audit.json</code>，换浏览器也在，Claude 也能直接读。</p></div>
        <div class="row"><button class="primary" data-action="save-account">保存</button></div></div>
      ${legacy && serverEmpty ? `<div class="banner amber">浏览器里有旧版工作台存的账号盘点草稿。<button class="small" data-action="import-legacy-audit">导入</button></div>` : ""}
      <div class="grid grid-2" style="margin-top:14px">
        <div class="card stack">
          <h2>盘点现有账号</h2>
          <div class="field-row">
            <label>现有昵称<input type="text" data-acc="nickname" value="${esc(audit.nickname)}"></label>
            <label>当前粉丝数<input type="text" data-acc="follower_count" value="${esc(audit.follower_count)}" inputmode="numeric"></label>
          </div>
          <label>现有简介与内容方向<textarea rows="2" data-acc="bio">${esc(audit.bio)}</textarea></label>
          <label>粉丝画像与常见互动<textarea rows="2" data-acc="audience">${esc(audit.audience)}</textarea></label>
          <label>最近 10 篇笔记表现（每行：标题｜浏览｜赞｜藏｜评）<textarea rows="6" data-acc="recent_ten">${esc(audit.recent_ten)}</textarea></label>
          <div class="field-row">
            <label>旧帖处理<select data-acc="old_posts_decision">${[["undecided", "待盘点后决定"], ["keep", "保留现状"], ["review", "逐篇复核后处理"]].map(([v, t]) => `<option value="${v}"${audit.old_posts_decision === v ? " selected" : ""}>${t}</option>`).join("")}</select></label>
            <label>判断依据<input type="text" data-acc="decision_reason" value="${esc(audit.decision_reason)}"></label>
          </div>
          <p class="small muted">填好后在 Cowork 里说“帮我看看账号盘点”，Claude 会读这个文件给出保留/隐藏建议。</p>
        </div>
        <div class="card stack">
          <h2>改造清单</h2>
          ${draft.checklist.map((item, index) => `<div class="row" style="align-items:flex-start"><input type="checkbox" data-check-item="${index}"${item.done ? " checked" : ""}><div style="flex:1"><div style="font-weight:600">${esc(item.label)}</div><input type="text" data-check-note="${index}" value="${esc(item.note || "")}" placeholder="备注" style="margin-top:4px"></div>${item.date ? `<span class="small muted">${esc(item.date)}</span>` : ""}</div>`).join("")}
        </div>
      </div>
      <div class="grid grid-2" style="margin-top:14px">
        <div class="card stack">
          <h2>名称与简介</h2>
          <p><b>建议昵称：</b>${esc(brand.account_name)}</p>
          <p class="small muted">${esc(brand.account_name_note || "")}</p>
          ${copyBlock("简介（三行）", (brand.bio || []).join("\n"))}
          <p class="small muted">合集：${esc((brand.collections || []).join("、"))}</p>
        </div>
        <div class="card stack">
          <h2>粉丝记录</h2>
          <div class="row"><input type="date" id="f-date" value="${new Date().toISOString().slice(0, 10)}" style="max-width:170px"><input type="number" id="f-count" placeholder="粉丝数" min="0" style="max-width:140px"><button class="small" data-action="add-follower">记一笔</button></div>
          ${followers.length ? `<table class="data"><thead><tr><th>日期</th><th>粉丝数</th><th></th></tr></thead><tbody>${followers.slice().reverse().map((point) => `<tr><td>${esc(point.date)}</td><td>${esc(point.count)}</td><td><button class="small ghost" data-action="remove-follower" data-date="${esc(point.date)}">删</button></td></tr>`).join("")}</tbody></table>` : `<p class="small muted">还没有记录。每周记一次就够。</p>`}
        </div>
      </div>
      <div class="card">
        <div class="card-head"><h2>对标笔记（ops/benchmarks/）</h2></div>
        <div class="field-row">
          <label>标题<input type="text" id="bm-title"></label>
          <label>博主<input type="text" id="bm-author"></label>
          <label>封面结构<input type="text" id="bm-cover" placeholder="类型标签 + 大字问题 + 工具名"></label>
          <label>图片张数<input type="number" id="bm-images" min="1"></label>
          <label>收藏<input type="number" id="bm-saves" min="0"></label>
          <label>截图文件名<input type="text" id="bm-shot" placeholder="放进 ops/benchmarks/"></label>
        </div>
        <label style="margin-top:8px">值得借鉴的一点<input type="text" id="bm-takeaway"></label>
        <div class="row" style="margin-top:8px"><button class="small" data-action="add-benchmark">添加</button></div>
        ${benchmarks.rows.length ? `<div class="table-wrap" style="margin-top:10px"><table class="data"><thead><tr><th>标题</th><th>博主</th><th>封面结构</th><th>图</th><th>藏</th><th>借鉴</th></tr></thead><tbody>${benchmarks.rows.map((row) => `<tr><td>${esc(row.title)}</td><td>${esc(row.author)}</td><td>${esc(row.cover_structure)}</td><td>${esc(row.image_count)}</td><td>${esc(row.saves)}</td><td>${esc(row.takeaway)}</td></tr>`).join("")}</tbody></table></div>` : ""}
      </div>`;
  }

  function accountDraft() { return JSON.parse(JSON.stringify(state.drafts.account)); }
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (state.route.view !== "account" || !el.dataset) return;
    const draft = state.drafts.account ? accountDraft() : null;
    if (!draft) return;
    if (el.dataset.acc) draft.audit[el.dataset.acc] = el.value;
    else if (el.dataset.checkNote !== undefined) draft.checklist[Number(el.dataset.checkNote)].note = el.value;
    else if (el.dataset.checkItem !== undefined) draft.checklist[Number(el.dataset.checkItem)].done = el.checked;
    else return;
    markDraft("account", draft);
  });
  document.addEventListener("change", (event) => {
    const el = event.target;
    if (state.route.view === "account" && el.dataset && (el.dataset.checkItem !== undefined || el.tagName === "SELECT")) el.dispatchEvent(new Event("input", { bubbles: true }));
  });
  savers.account = async () => {
    const saved = await api("/api/account", { body: state.drafts.account });
    loadDraft("account", saved);
    refreshDirtyBar();
    await renderAccount();
    return true;
  };
  actions["save-account"] = (button) => run(button, savers.account, "已保存");
  actions["add-follower"] = () => {
    const date = document.getElementById("f-date").value;
    const count = Number(document.getElementById("f-count").value);
    if (!date || !Number.isInteger(count) || count < 0) return toast("请填日期和粉丝数", "error");
    const draft = accountDraft();
    draft.followers = (draft.followers || []).filter((point) => point.date !== date).concat([{ date, count }]).sort((a, b) => a.date.localeCompare(b.date));
    markDraft("account", draft);
    renderAccount();
  };
  actions["remove-follower"] = (button) => {
    const draft = accountDraft();
    draft.followers = (draft.followers || []).filter((point) => point.date !== button.dataset.date);
    markDraft("account", draft);
    renderAccount();
  };
  actions["import-legacy-audit"] = () => {
    let legacy = null;
    try { legacy = JSON.parse(storage("xhs-account-audit-draft-v1") || "null"); } catch (error) { legacy = null; }
    if (!legacy) return;
    const draft = accountDraft();
    draft.audit = { ...draft.audit, nickname: legacy.nickname || "", follower_count: legacy.followerCount || "", bio: legacy.bio || "", audience: legacy.audience || "", recent_ten: legacy.recentTen || "", old_posts_decision: legacy.oldPostsDecision || "undecided", decision_reason: legacy.decisionReason || "" };
    markDraft("account", draft);
    storage("xhs-account-audit-draft-v1", "");
    renderAccount();
    toast("已导入到表单，记得点“保存”");
  };
  actions["add-benchmark"] = async (button) => {
    const body = { title: document.getElementById("bm-title").value, author: document.getElementById("bm-author").value, cover_structure: document.getElementById("bm-cover").value, image_count: document.getElementById("bm-images").value, saves: document.getElementById("bm-saves").value, screenshot: document.getElementById("bm-shot").value, takeaway: document.getElementById("bm-takeaway").value };
    if (state.dirty.isDirty("account")) return toast("先保存上面的账号盘点", "error");
    const ok = await run(button, () => api("/api/benchmarks", { body }), "已添加");
    if (ok) renderAccount();
  };

  // =============================================================== REVIEW
  async function renderReviewPage() {
    const [metrics, requests, calendar, postsData] = await Promise.all([api("/api/metrics"), api("/api/requests"), api("/api/calendar"), api("/api/posts")]);
    const names = Object.fromEntries(postsData.posts.map((post) => [post.post_id, `${post.topic_id} ${post.name}`]));
    const ratio = (a, b) => (Number(b) > 0 && a !== "" ? `${((Number(a) / Number(b)) * 100).toFixed(1)}%` : "—");
    app.innerHTML = `
      <div class="page-head"><div><h1>数据复盘</h1><p>数据来自 <code>ops/metrics.csv</code>。收藏率 = 收藏 ÷ 浏览，涨粉率 = 新增关注 ÷ 浏览；少于 3 篇的分组只作观察。</p></div></div>
      <div class="card">
        <div class="card-head"><h2>周复盘</h2><div class="row"><select id="review-week" style="max-width:160px"><option value="">累计</option>${calendar.weeks.map((week) => `<option value="${week.week}">第 ${week.week} 周</option>`).join("")}</select><button class="primary small" data-action="weekly-review">生成</button></div></div>
        <div id="review-out"><p class="small muted">生成的复盘会写进 <code>ops/reviews/</code>。第 4 周的复盘会多一节“下月配比”。</p></div>
      </div>
      <div class="card">
        <h2>每篇数据</h2>
        ${metrics.rows.length ? `<div class="table-wrap" style="margin-top:8px"><table class="data"><thead><tr><th>篇目</th><th>时间点</th><th>浏览</th><th>赞</th><th>藏</th><th>评</th><th>新增关注</th><th>收藏率</th><th>涨粉率</th><th>备注</th></tr></thead><tbody>${metrics.rows.map((row) => `<tr><td><a href="#/post/${esc(row.post_id)}/publish">${esc(names[row.post_id] || row.post_id)}</a></td><td>${esc(row.checkpoint)}</td><td>${esc(row.views)}</td><td>${esc(row.likes)}</td><td>${esc(row.saves)}</td><td>${esc(row.comments)}</td><td>${esc(row.new_followers)}</td><td>${ratio(row.saves, row.views)}</td><td>${ratio(row.new_followers, row.views)}</td><td class="small">${esc(row.notes)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty" style="margin-top:8px">还没有数据。每篇发布后在它的“发布与数据”里回填。</div>`}
      </div>
      <div class="card">
        <h2>评论点菜清单</h2>
        <div class="row" style="margin-top:8px"><input type="text" id="req-new" placeholder="评论里点的菜" style="max-width:420px"><button class="small" data-action="add-request-page">记一笔</button></div>
        ${requests.rows.length ? `<div class="table-wrap" style="margin-top:10px"><table class="data"><thead><tr><th>点的菜</th><th>次数</th><th>来自</th><th>状态</th></tr></thead><tbody>${requests.rows.slice().sort((a, b) => Number(b.count) - Number(a.count)).map((row) => `<tr><td>${esc(row.request)}</td><td>${esc(row.count)}</td><td class="small">${esc(names[row.post_id] || row.post_id || "")}</td><td><select data-request-status="${esc(row.request)}">${["新", "已排期", "已做", "不做"].map((status) => `<option${status === row.status ? " selected" : ""}>${status}</option>`).join("")}</select></td></tr>`).join("")}</tbody></table></div>` : ""}
      </div>`;
  }

  actions["weekly-review"] = async (button) => {
    const value = document.getElementById("review-week").value;
    const result = await run(button, () => api("/api/reviews/weekly", { body: { week: value ? Number(value) : null } }), "复盘已生成");
    if (result) document.getElementById("review-out").innerHTML = `<p class="small" style="margin-bottom:8px">已写入 <code>${esc(result.path)}</code></p><pre class="box">${esc(result.text)}</pre>`;
  };
  actions["add-request-page"] = async (button) => {
    const text = document.getElementById("req-new").value.trim();
    if (!text) return toast("先写下点的菜", "error");
    const ok = await run(button, () => api("/api/requests", { body: { request: text } }), "已记下");
    if (ok) renderReviewPage();
  };
  document.addEventListener("change", async (event) => {
    const el = event.target;
    if (el.dataset && el.dataset.requestStatus !== undefined) {
      await run(null, () => api("/api/requests/status", { body: { request: el.dataset.requestStatus, status: el.value } }), "状态已更新");
    }
  });

  // ================================================================ LEADS
  async function renderLeads() {
    const data = await api("/api/leads");
    const tools = state.config.tools;
    const apps = (data.appstore || {}).apps || {};
    const candidates = (data.appstore || {}).candidates || {};
    app.innerHTML = `
      <div class="page-head"><div><h1>线索</h1><p>新品线索只是线索：进入测试前，保存官方来源，并在自己的 App 里确认能用。确认能用后，一键建一个第 11 期（新品）工作区。</p></div></div>
      <div class="card">
        <h2>手动录入</h2>
        <div class="field-row" style="margin-top:8px">
          <label>一句话<input type="text" id="lead-title" placeholder="如：千问 App 上线视频理解"></label>
          <label>链接（官方来源优先）<input type="text" id="lead-url" placeholder="https://"></label>
          <label>相关工具<select id="lead-tool"><option value="">—</option>${tools.map((tool) => `<option value="${tool.id}">${esc(tool.display_name)}</option>`).join("")}</select></label>
          <label>我的 App 里能用吗<select id="lead-available"><option>未确认</option><option>是</option><option>否</option></select></label>
        </div>
        <label style="margin-top:8px">补充说明<input type="text" id="lead-desc"></label>
        <div class="row" style="margin-top:8px"><button class="primary small" data-action="add-lead">添加线索</button></div>
      </div>
      <div class="card">
        <h2>线索列表（ops/leads.csv）</h2>
        ${data.rows.length ? `<div class="table-wrap" style="margin-top:8px"><table class="data"><thead><tr><th>线索</th><th>来源</th><th>发现时间</th><th>能用吗</th><th>状态</th><th></th></tr></thead><tbody>${data.rows.slice().reverse().map((row) => `<tr>
          <td><b>${esc(row.title)}</b>${row.url ? `<div class="small"><a href="${esc(row.url)}" target="_blank" rel="noopener noreferrer">原始链接</a></div>` : `<div class="small muted">缺原始链接</div>`}${row.description ? `<div class="small muted">${esc(row.description.slice(0, 160))}</div>` : ""}</td>
          <td class="small">${esc({ manual: "手动", appstore: "App Store", official: "官方页" }[row.source] || row.source)}</td>
          <td class="small mono">${esc((row.found_at || "").slice(0, 16).replace("T", " "))}</td>
          <td><select data-lead="${row.id}" data-lead-field="available_in_my_app">${["未确认", "是", "否"].map((value) => `<option${value === row.available_in_my_app ? " selected" : ""}>${value}</option>`).join("")}</select></td>
          <td><select data-lead="${row.id}" data-lead-field="status">${["待核实", "已核实可测", "暂不可测", "已建篇", "忽略"].map((value) => `<option${value === row.status ? " selected" : ""}>${value}</option>`).join("")}</select></td>
          <td>${row.available_in_my_app === "是" && row.status !== "已建篇" ? `<button class="small primary" data-action="lead-to-post" data-lead="${row.id}" data-tool="${esc(row.tool)}">建第11期工作区</button>` : ""}</td>
        </tr>`).join("")}</tbody></table></div>` : `<div class="empty" style="margin-top:8px">还没有线索。</div>`}
      </div>
      <div class="grid grid-2">
        <div class="card stack">
          <h2>App Store 版本监测</h2>
          <p class="small muted">用苹果公开的 App Store（中国区）接口读各 App 的版本号和更新说明；版本变了就自动加一条“待核实”线索。第一次先查找并确认每个 App 的编号。需要本机网络能访问 itunes.apple.com。</p>
          <div class="row"><button class="small" data-action="appstore-resolve">查找 App 编号</button><button class="small primary" data-action="appstore-check"${Object.keys(apps).length ? "" : " disabled"}>检查更新</button></div>
          ${Object.keys(apps).length ? `<table class="data"><thead><tr><th>工具</th><th>App</th><th>版本</th><th>检查时间</th></tr></thead><tbody>${Object.entries(apps).map(([tool, info]) => `<tr><td>${esc(toolName(tool))}</td><td class="small">${esc(info.name || "")}</td><td>${esc(info.version || "（首次检查后记录）")}</td><td class="small mono">${esc((info.checked_at || "").slice(0, 16))}</td></tr>`).join("")}</tbody></table>` : ""}
          ${Object.entries(candidates).filter(([tool]) => !apps[tool]).map(([tool, list]) => `<div class="tool-card"><b>${esc(toolName(tool))}</b>：选择正确的 App<div class="stack" style="margin-top:6px">${list.length ? list.map((item) => `<div class="row"><span class="small">${esc(item.name)} · ${esc(item.seller || "")} · ${esc(item.version || "")}</span><button class="small" data-action="appstore-confirm" data-tool="${tool}" data-track="${item.track_id}">是这个</button></div>`).join("") : `<span class="small muted">没找到，检查 tools.json 里的 appstore_term</span>`}</div></div>`).join("")}
        </div>
        <div class="card stack">
          <h2>官方更新页</h2>
          <p class="small muted">页面列表在 <code>scripts/radar_sources.json</code>。第一次检查只记录基线，之后内容有变化才会生成线索。</p>
          <div class="row"><button class="small primary" data-action="official-check">检查官方更新页</button></div>
          ${Object.entries(data.official || {}).map(([key, value]) => `<p class="small muted">${esc(key)}：上次检查 ${esc((value.checked_at || "").slice(0, 16))}</p>`).join("")}
          <div class="sep"></div>
          <p class="small muted">想先熟悉流程？<button class="small ghost" data-action="demo-scan">生成演示线索工单</button>（写到 logs/radar_actions/demo/，明确标记为演示，不进线索表）</p>
        </div>
      </div>`;
  }

  actions["add-lead"] = async (button) => {
    const body = { title: document.getElementById("lead-title").value, url: document.getElementById("lead-url").value.trim(), tool: document.getElementById("lead-tool").value, available_in_my_app: document.getElementById("lead-available").value, description: document.getElementById("lead-desc").value };
    const ok = await run(button, () => api("/api/leads", { body }), "线索已添加");
    if (ok) renderLeads();
  };
  document.addEventListener("change", async (event) => {
    const el = event.target;
    if (el.dataset && el.dataset.lead && el.dataset.leadField) {
      const ok = await run(null, () => api(`/api/leads/${el.dataset.lead}`, { body: { [el.dataset.leadField]: el.value } }), "已更新");
      if (ok) renderLeads();
    }
  });
  actions["lead-to-post"] = async (button) => {
    const tools = button.dataset.tool ? [button.dataset.tool] : undefined;
    const slug = `new-release-${button.dataset.lead.toLowerCase()}`;
    const result = await run(button, () => api("/api/posts", { body: { topic_id: "11", slug, tools } }), "工作区已建好");
    if (result) {
      await api(`/api/leads/${button.dataset.lead}`, { body: { status: "已建篇", topic_id: "11" } });
      location.hash = `#/post/${result.post_id}/brief`;
    }
  };
  actions["appstore-resolve"] = async (button) => {
    const result = await run(button, () => api("/api/leads/appstore-resolve", { body: {} }));
    if (result) {
      const errors = Object.keys(result.errors || {});
      toast(errors.length ? `有 ${errors.length} 个没查到：${Object.values(result.errors)[0]}` : "候选已列出，请逐个确认", errors.length ? "error" : "");
      renderLeads();
    }
  };
  actions["appstore-confirm"] = async (button) => {
    const ok = await run(button, () => api("/api/leads/appstore-confirm", { body: { tool: button.dataset.tool, track_id: Number(button.dataset.track) } }), "已确认");
    if (ok) renderLeads();
  };
  actions["appstore-check"] = async (button) => {
    const result = await run(button, () => api("/api/leads/appstore-check", { body: {} }));
    if (result) { toast(result.changes.length ? `发现 ${result.changes.length} 个更新，已加进线索` : result.baseline.length ? "已记录当前版本，下次检查开始对比" : "没有新版本"); renderLeads(); }
  };
  actions["official-check"] = async (button) => {
    const result = await run(button, () => api("/api/leads/official-check", { body: {} }));
    if (result) {
      const errors = Object.values(result.errors || {});
      toast(errors.length ? errors[0] : result.changes.length ? `发现 ${result.changes.length} 处更新` : result.baseline.length ? "已记录基线" : "没有变化", errors.length ? "error" : "");
      renderLeads();
    }
  };
  actions["demo-scan"] = (button) => run(button, () => api("/api/radar/scan", { body: { mock: true } }), "演示工单已生成（仅供熟悉流程）");

  render();
})();
