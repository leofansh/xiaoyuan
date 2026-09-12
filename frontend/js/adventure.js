/* V3.0 P2 · 模块 D 闯关冒险地图前端 (adventure.js) —— 规格 6.4
 * - AdventureMapView：大陆切换条（ContinentSelector）+ 关卡节点流（LevelNode）+ 每大陆进度条
 * - LevelIntroModal：点击 available/completed 关卡弹出介绍（名称/目标/奖励预览/开始挑战）
 * - LevelCompleteModal：全局通关弹窗（#adventure-complete-modal），由 SSE level_complete 触发
 * 依赖 app.js 的 api()/$()/toast()/celebrate() 全局函数（缺省时自动降级，不抛错）。
 * 由 app.js 调用入口：window.AdventureView.init / load / showLevelIntro / enterLevel / closeModals / showComplete
 */

/* ---------------- 常量与内部状态 ---------------- */
const ADV_RARITY_LABEL = { common: "普通", rare: "稀有", epic: "史诗", legendary: "传说" };
const ADV_STATUS_META = {
  locked:    { icon: "🔒", label: "未解锁" },
  available: { icon: "⭐", label: "可挑战" },
  completed: { icon: "✅", label: "已通关" },
};

let advApiBase = "";              // 后端路径前缀（init 传入，默认相对）
let advCache = null;              // 最近一次地图数据 {continents,current_continent,total_stars}
let advActiveContinent = "";      // 当前展示的大陆
let advPendingLevelId = null;     // 介绍弹窗中待挑战的关卡 id
let advInited = false;            // init 是否已执行（幂等保护）

/* ---------------- 工具（自包含，避免依赖脚本加载顺序） ---------------- */
function advEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function advToast(text, ms) {
  if (typeof toast === "function") toast(text, ms);
  else if (typeof console !== "undefined") console.log(text);
}

function advCelebrate() {
  if (typeof celebrate === "function") celebrate();
}

/* student_id 读取：优先 window.currentStudentId → 全局 studentId（app.js）→ localStorage（与 cards.js 同源） */
function advGetSid() {
  if (typeof window !== "undefined" && window.currentStudentId) return window.currentStudentId;
  if (typeof studentId !== "undefined" && studentId) return studentId;
  try { return localStorage.getItem("xy_student_id") || null; } catch (_) { return null; }
}

/* 统一请求：复用 app.js 的 api()，缺省时降级为原生 fetch */
function advRequest(path, body, method) {
  method = method || "POST";
  if (typeof api === "function") return api(advApiBase + path, body, method);
  return fetch(advApiBase + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  }).then(r => {
    if (!r.ok) throw new Error("请求失败 (" + r.status + ")");
    return r.json();
  });
}

function advStarsHtml(stars, max) {
  const s = Math.max(0, stars || 0);
  const m = Math.max(s, max || 3);
  return "★".repeat(s) + "☆".repeat(m - s);
}

/* ---------------- 容器：自动创建并插入到 #cards-section 之前 ---------------- */
function advEnsureSection() {
  let sec = document.getElementById("adventure-section");
  if (!sec) {
    sec = document.createElement("div");
    sec.id = "adventure-section";
    sec.className = "adventure-section";
    const cards = document.getElementById("cards-section");
    const badges = document.getElementById("view-badges");
    if (cards && badges && cards.parentNode === badges) {
      badges.insertBefore(sec, cards);
    } else if (badges) {
      badges.appendChild(sec);
    } else {
      document.body.appendChild(sec);
    }
  }
  return sec;
}

function advEmptyHint() {
  return '<div class="adv-empty">🗺️ 冒险地图正在准备中…<span class="adv-empty-sub">小圆正在铺路，很快就能来闯关啦</span></div>';
}

/* ---------------- 渲染：大陆切换条 + 关卡节点 + 进度条 ---------------- */
function advRenderMap(data) {
  const section = advEnsureSection();
  const continents = (data && data.continents) || [];
  if (!continents.length) { section.innerHTML = advEmptyHint(); return; }

  const current = data.current_continent || continents[0].name;
  if (!continents.some(c => c.name === advActiveContinent)) advActiveContinent = current;
  const active = continents.find(c => c.name === advActiveContinent) || continents[0];

  section.innerHTML = `
    <h3 class="section-title">🗺️ 闯关冒险地图</h3>
    <div class="adv-summary">
      <span class="adv-total-stars">⭐ 已收集 <b>${data.total_stars || 0}</b> 颗星</span>
      <span class="adv-summary-hint">通关收集星星，解锁新大陆</span>
    </div>
    <div class="adv-continent-tabs" role="tablist">
      ${continents.map(c => `
        <button class="adv-tab ${c.name === active.name ? "active" : ""}"
                data-continent="${advEsc(c.name)}" role="tab"
                aria-selected="${c.name === active.name}">${advEsc(c.name)}</button>`).join("")}
    </div>
    ${advRenderContinent(active)}
  `;
}

function advRenderContinent(c) {
  const p = c.progress || {};
  const total = p.total || 0;
  const pct = total ? Math.round(((p.completed || 0) / total) * 100) : 0;
  const levels = (c.levels || []).slice().sort((a, b) => (a.order || 0) - (b.order || 0));
  return `
    <div class="adv-continent">
      <div class="adv-progress">
        <div class="adv-progress-bar"><div class="adv-progress-fill" style="width:${pct}%"></div></div>
        <div class="adv-progress-text">通关 <b>${p.completed || 0}/${total}</b> · ⭐ <b>${p.stars || 0}/${p.stars_max || 0}</b></div>
      </div>
      <div class="adv-levels">
        ${levels.map(l => advRenderLevel(l)).join("")}
      </div>
    </div>`;
}

function advRenderLevel(l) {
  const status = l.status || "locked";
  const meta = ADV_STATUS_META[status] || ADV_STATUS_META.locked;
  const boss = l.type === "boss" ? '<span class="adv-node-boss">BOSS</span>' : "";
  const stars = advStarsHtml(l.stars, l.stars_max);
  return `
    <div class="adv-level adv-status-${status} ${boss ? "is-boss" : ""}" data-level-id="${advEsc(l.id)}">
      <button class="adv-node" ${status === "locked" ? "disabled" : ""}
              title="${advEsc(l.name)} · ${meta.label}">
        <span class="adv-node-icon">${meta.icon}</span>
        <span class="adv-node-name">${advEsc(l.name)}</span>
        ${boss}
        <span class="adv-node-stars" aria-label="${l.stars || 0}/${l.stars_max || 3} 星">${stars}</span>
      </button>
    </div>`;
}

/* ---------------- 大陆切换 ---------------- */
function advSelectContinent(name) {
  advActiveContinent = name;
  if (advCache) advRenderMap(advCache);
}

function advFindLevel(levelId) {
  if (!advCache) return null;
  for (const c of (advCache.continents || [])) {
    const found = (c.levels || []).find(l => l.id === levelId);
    if (found) return found;
  }
  return null;
}

function advLevelNameById(levelId) {
  const l = advFindLevel(levelId);
  return l ? l.name : levelId;
}

/* ---------------- 关卡介绍弹窗（LevelIntroModal） ---------------- */
function advEnsureIntroModal() {
  let overlay = document.getElementById("adventure-intro-modal");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "adventure-intro-modal";
  overlay.className = "adv-overlay hidden";
  overlay.innerHTML = `
    <div class="adv-modal-card" role="dialog" aria-modal="true">
      <button class="adv-modal-close" aria-label="关闭">×</button>
      <div class="adv-modal-title"></div>
      <div class="adv-modal-cond"></div>
      <div class="adv-modal-rewards"></div>
      <button class="adv-start-btn">开始挑战 ⚔️</button>
    </div>`;
  overlay.addEventListener("click", e => {
    if (e.target === e.currentTarget || e.target.closest(".adv-modal-close")) closeModals();
  });
  overlay.querySelector(".adv-start-btn").addEventListener("click", () => {
    if (advPendingLevelId) enterLevel(advPendingLevelId);
  });
  document.body.appendChild(overlay);
  return overlay;
}

function advConditionText(level) {
  const c = level.completion_condition;
  if (!c) return "完成对应知识点的学习挑战";
  if (typeof c === "string") return c;
  if (typeof c === "object") {
    const parts = [];
    if (c.mastery_threshold != null) parts.push(`掌握度达到 ${Math.round(c.mastery_threshold * 100)}%`);
    if (c.min_correct_answers != null) parts.push(`答对 ${c.min_correct_answers} 题`);
    if (parts.length) return parts.join(" · ");
  }
  return "完成对应知识点的学习挑战";
}

function advRewardChips(rp) {
  rp = rp || {};
  const chips = [];
  if (rp.xp != null) chips.push(`<span class="adv-reward adv-reward-xp">+${rp.xp} XP</span>`);
  const rarity = rp.card_rarity;
  if (rarity) chips.push(`<span class="adv-reward adv-reward-card">🎴 ${advEsc(ADV_RARITY_LABEL[rarity] || rarity)}卡</span>`);
  if (rp.badge) chips.push(`<span class="adv-reward adv-reward-badge">🏅 徽章</span>`);
  return chips.join("");
}

function showLevelIntro(levelId) {
  const level = advFindLevel(levelId);
  if (!level) { advToast("关卡数据还没准备好，稍后再试～"); return; }
  advPendingLevelId = level.id;
  const overlay = advEnsureIntroModal();
  overlay.querySelector(".adv-modal-title").innerHTML =
    `${level.type === "boss" ? "👑 " : ""}${advEsc(level.name)}`;
  overlay.querySelector(".adv-modal-cond").innerHTML =
    `<span class="adv-modal-cond-label">🎯 目标</span>${advEsc(advConditionText(level))}`;
  overlay.querySelector(".adv-modal-rewards").innerHTML = advRewardChips(level.rewards_preview);
  overlay.classList.remove("hidden");
}

/* ---------------- 通关弹窗（LevelCompleteModal，全局 #adventure-complete-modal） ---------------- */
function advEnsureCompleteModal() {
  let overlay = document.getElementById("adventure-complete-modal");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "adventure-complete-modal";
  overlay.className = "adv-complete-overlay hidden";
  overlay.innerHTML = `
    <div class="adv-complete-card" role="dialog" aria-modal="true">
      <div class="adv-complete-title">🎉 通关啦！</div>
      <div class="adv-complete-stars"></div>
      <div class="adv-complete-rewards"></div>
      <div class="adv-complete-unlock"></div>
      <div class="adv-complete-msg"></div>
      <button class="adv-complete-close">收下奖励 🎁</button>
    </div>`;
  overlay.addEventListener("click", e => {
    if (e.target === e.currentTarget || e.target.closest(".adv-complete-close")) {
      overlay.classList.add("hidden");
    }
  });
  document.body.appendChild(overlay);
  return overlay;
}

function showComplete(data) {
  if (!data) return;
  const overlay = advEnsureCompleteModal();
  const stars = data.stars_earned != null ? data.stars_earned : (data.completed ? 3 : 0);
  const max = data.stars_max || 3;
  const rewards = data.rewards || {};

  const chips = [];
  if (rewards.xp != null) chips.push(`<span class="adv-reward adv-reward-xp">+${rewards.xp} XP</span>`);
  const card = rewards.card_dropped || rewards.card;
  if (card) chips.push(`<span class="adv-reward adv-reward-card">🎴 ${advEsc(card.name || "新卡片")}</span>`);
  const badge = rewards.badge_unlocked || rewards.badge;
  if (badge) {
    const badgeName = typeof badge === "string" ? badge : (badge.name || "徽章");
    chips.push(`<span class="adv-reward adv-reward-badge">🏅 ${advEsc(badgeName)}</span>`);
  }

  overlay.querySelector(".adv-complete-stars").innerHTML = advStarsHtml(stars, max);
  overlay.querySelector(".adv-complete-rewards").innerHTML = chips.join("");
  const unlockEl = overlay.querySelector(".adv-complete-unlock");
  const unlocked = (data.newly_unlocked || []).filter(Boolean);
  unlockEl.innerHTML = unlocked.length
    ? `<span class="adv-unlock-label">🔓 解锁新关卡：</span>${unlocked.map(id => advEsc(advLevelNameById(id))).join("、")}`
    : "";
  overlay.querySelector(".adv-complete-msg").textContent = data.message || "";
  overlay.classList.remove("hidden");
  advCelebrate();
}

/* ---------------- 进入关卡 ---------------- */
function advSwitchToChat() {
  if (typeof window.__switchView === "function") { window.__switchView("chat"); return; }
  const tab = document.querySelector('[data-view="chat"]');
  if (tab) tab.click();
}

async function enterLevel(levelId) {
  const sid = advGetSid();
  if (!sid) { advToast("请先登录再闯关哦～"); return; }
  try {
    const res = await advRequest(`/api/adventure/${sid}/enter`, { level_id: levelId });
    if (res && res.success) {
      closeModals();
      if (res.intro_message) advToast(res.intro_message, 3200);
      // 告知集成方当前关卡上下文（可选钩子）
      if (typeof window.setCurrentLevel === "function") window.setCurrentLevel(levelId, res.level);
      advSwitchToChat();
    } else {
      advToast((res && res.reason) || "这关还没解锁，先完成前面的关卡吧～");
    }
  } catch (e) {
    advToast("进入关卡失败：" + (e.message || "未知错误"));
  }
}

function closeModals() {
  const intro = document.getElementById("adventure-intro-modal");
  if (intro) intro.classList.add("hidden");
  const complete = document.getElementById("adventure-complete-modal");
  if (complete) complete.classList.add("hidden");
}

/* ---------------- 加载地图（由 app.js 调用） ---------------- */
async function load() {
  const section = advEnsureSection();
  const sid = advGetSid();
  if (!sid) { section.innerHTML = advEmptyHint(); return null; }
  try {
    const res = await advRequest(`/api/adventure/${sid}`, null, "GET");
    advCache = res || null;
    if (!res || !(res.continents && res.continents.length)) {
      section.innerHTML = advEmptyHint();
    } else {
      advRenderMap(res);
    }
    return res;
  } catch (_) {
    section.innerHTML = advEmptyHint();
    return null;
  }
}

/* ---------------- 事件委托（挂载一次） ---------------- */
function advBindEvents() {
  document.addEventListener("click", e => {
    const tab = e.target.closest(".adv-tab");
    if (tab) { advSelectContinent(tab.dataset.continent); return; }

    const node = e.target.closest(".adv-node");
    if (!node) return;
    const wrapper = node.closest(".adv-level");
    if (!wrapper) return;
    if (wrapper.classList.contains("adv-status-locked")) {
      advToast("🔒 这关还没解锁，先完成前面的关卡吧～");
      return;
    }
    showLevelIntro(wrapper.dataset.levelId);
  });
}

/* ---------------- 初始化（由 app.js 调用一次） ---------------- */
function init(apiBase) {
  if (advInited) return;
  advInited = true;
  advApiBase = apiBase || "";
  advEnsureIntroModal();
  advEnsureCompleteModal();
  advBindEvents();
}

/* ---------------- 对外暴露的全局对象（由 app.js 调用） ---------------- */
window.AdventureView = {
  init,
  load,
  showLevelIntro,
  closeModals,
  enterLevel,
  showComplete,
};
