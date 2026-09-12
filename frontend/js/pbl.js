/* V3.0 P2 · 模块 E「PBL 项目框架」前端 (pbl.js)
 * 规格 7.4（docs/V3.0开发规格说明书.md 929-944 行）
 * - PBLProjectList     ：项目卡片网格（icon/name/description/category/difficulty/status/进度条）
 * - PBLProjectDetail   ：项目 hero + 关卡列表（Lv.N 名称/描述/状态/最佳分 + 进入按钮）
 * - PBLLevelView       ：左右布局（左侧 #simulator-container + 右侧对话区）
 * - PBLLevelCompleteModal：通关结算（星级/rewards/knowledge_summary/message/下一关）
 * - SimulatorContainer ：预留空容器 + setSimulator(renderFn) 挂载点（导弹模拟器由另一个 agent 创建）
 * 依赖 app.js 的 api()/$()/toast()/celebrate() 全局函数，math.js 的 escapeHtml()/renderMathText()。
 * 独立全局对象 window.PBLView + window.PBLLevelView，由集成者后续接入。
 */

/* ---------------- 状态与常量 ---------------- */
const PBL_STATUS_META = {
  available:   { label: "可开始", cls: "available" },
  in_progress: { label: "进行中", cls: "in-progress" },
  completed:   { label: "已完成", cls: "completed" },
  locked:      { label: "未解锁", cls: "locked" },
};

const PBL_LEVEL_STATUS = {
  locked:    { icon: "🔒", label: "未解锁", cls: "locked" },
  available: { icon: "⭐", label: "可挑战", cls: "available" },
  completed: { icon: "✅", label: "已完成", cls: "completed" },
};

/* ---------------- 全局对象 ---------------- */
window.PBLView = {
  apiBase: "",
  containerId: null,          // 显式容器 id（如 "view-pbl"）
  currentProjectId: null,
  currentLevelId: null,
  _container: null,
  _currentProject: null,
  _levelData: null,
  _simulatorRender: null,     // 集成者塞入的模拟器渲染函数
  _recommendedIds: new Set(),

  /* 挂载事件（幂等） */
  init(apiBase) {
    if (apiBase) this.apiBase = apiBase;
    bindPblEvents();
    return this;
  },

  /* 拉取并渲染项目列表（自动确保容器存在） */
  load() { return this._loadList(); },

  /* 挂载到指定容器（如独立视图 #view-pbl） */
  loadInto(containerId) {
    this.containerId = containerId;
    return this._loadList();
  },

  /* 返回项目列表 */
  showProjectList() {
    this.currentProjectId = null;
    this.currentLevelId = null;
    this._levelData = null;
    return this._loadList();
  },

  /* 项目详情 */
  async loadDetail(projectId) {
    this.currentProjectId = projectId;
    this.currentLevelId = null;
    const container = this._ensureContainer();
    const sid = getPblStudentId();
    if (!sid) { container.innerHTML = pblEmpty("请先登录学生档案～"); return; }
    container.innerHTML = pblLoading("正在打开项目…");
    try {
      const data = await pblFetch(`/api/pbl/projects/${projectId}?student_id=${encodeURIComponent(sid)}`, null, "GET");
      this._currentProject = data;
      container.innerHTML = renderProjectDetail(data);
      bindDetailEvents(container);
    } catch (e) {
      container.innerHTML = pblEmpty("项目详情打不开：" + (e.message || "网络开小差了"));
    }
  },

  /* 进入关卡：构建模拟器 + 对话区 */
  async enterLevel(projectId, levelId) {
    this.currentProjectId = projectId;
    this.currentLevelId = levelId;
    const container = this._ensureContainer();
    const sid = getPblStudentId();
    if (!sid) { container.innerHTML = pblEmpty("请先登录学生档案～"); return; }
    container.innerHTML = pblLoading("正在进入关卡…");
    try {
      const res = await pblFetch(`/api/pbl/projects/${projectId}/enter`, { level_id: levelId, student_id: sid });
      if (res && res.success === false) {
        pblToast(res.message || "这关还没解锁哦～");
        this.loadDetail(projectId);
        return;
      }
      if (res && res.can_enter === false) {
        pblToast(res.message || "这关还没解锁哦～");
        this.loadDetail(projectId);
        return;
      }
      this._levelData = res || {};
      container.innerHTML = renderLevelView(res);
      bindLevelEvents(container);
      // 展示开场引导
      if (res && res.intro_message) {
        window.PBLLevelView.showAssistantMessage(res.intro_message);
      }
      // 挂载模拟器渲染函数（若有）
      const box = document.getElementById("simulator-container");
      if (box && this._simulatorRender) {
        this._simulatorRender(box, res ? res.simulator_config : null);
      }
    } catch (e) {
      container.innerHTML = pblEmpty("关卡加载失败：" + (e.message || "网络开小差了"));
    }
  },

  /* 通关提交 */
  async submitComplete(projectId, levelId, payload) {
    const body = Object.assign({ level_id: levelId, student_id: getPblStudentId() }, payload || {});
    try {
      const res = await pblFetch(`/api/pbl/projects/${projectId}/complete`, body);
      if (res && res.success === false) {
        pblToast(res.message || "提交失败，再试一次？");
        return res;
      }
      this.showComplete(res);
      return res;
    } catch (e) {
      pblToast("通关提交失败：" + (e.message || "网络开小差了"));
    }
  },

  /* 通关结算 modal（对外，供 SSE / 集成者调用） */
  showComplete(data) {
    const overlay = ensureCompleteOverlay();
    const stars = (data && data.stars_earned) || 0;
    overlay.querySelector(".pbl-stars").innerHTML =
      "★".repeat(stars) + "☆".repeat(Math.max(0, 3 - stars));
    overlay.querySelector(".pbl-complete-title").textContent =
      (data && data.project_completed) ? "🎉 项目全部通关！" : "关卡通过！";
    overlay.querySelector(".pbl-complete-message").innerHTML = fmt(data && data.message);
    overlay.querySelector(".pbl-rewards").innerHTML = renderRewards(data && data.rewards);
    const knowledge = overlay.querySelector(".pbl-knowledge");
    if (data && data.knowledge_summary) {
      knowledge.classList.remove("hidden");
      knowledge.innerHTML = "💡 你刚才用到了：<br>" + fmt(data.knowledge_summary);
    } else {
      knowledge.classList.add("hidden");
    }
    // 下一关 / 返回项目
    const nextBtn = overlay.querySelector("[data-pbl-action='next-level']");
    if (data && (data.next_level_unlocked || data.project_completed)) {
      nextBtn.classList.remove("hidden");
      nextBtn.textContent = data.project_completed ? "🏆 查看项目" : "下一关 →";
    } else {
      nextBtn.classList.add("hidden");
    }
    overlay.classList.remove("hidden");
    pblCelebrate();
  },

  /* 集成者塞入模拟器渲染函数 renderFn(containerEl, simulatorConfig) */
  setSimulator(renderFn) {
    this._simulatorRender = typeof renderFn === "function" ? renderFn : null;
    const box = document.getElementById("simulator-container");
    if (box && this._simulatorRender && this.currentLevelId && box.children.length === 0) {
      this._simulatorRender(box, this._levelData ? this._levelData.simulator_config : null);
    }
    return this;
  },

  /* ---------------- 内部 ---------------- */
  async _loadList() {
    const container = this._ensureContainer();
    const sid = getPblStudentId();
    if (!sid) { container.innerHTML = pblEmpty("请先登录学生档案～"); return; }
    container.innerHTML = pblLoading("正在加载 PBL 项目…");
    try {
      const data = await pblFetch(`/api/pbl/projects?student_id=${encodeURIComponent(sid)}`, null, "GET");
      const projects = (data && data.projects) || [];
      this._recommendedIds = new Set((data && data.recommended || []).map(p => p && p.id));
      container.innerHTML = renderProjectList(projects);
      bindListEvents(container);
      const coSec = container.querySelector("#co-creation-section");
      if (coSec && window.CoCreation) window.CoCreation.mountInto(coSec, sid);
    } catch (e) {
      container.innerHTML = pblEmpty("项目列表加载失败：" + (e.message || "网络开小差了"));
    }
  },

  _ensureContainer() {
    let container = null;
    if (this.containerId) {
      container = document.getElementById(this.containerId);
      if (!container) {
        container = document.createElement("div");
        container.id = this.containerId;
        container.className = "pbl-view";
        document.body.appendChild(container);
      }
    } else {
      container = document.getElementById("pbl-section");
      if (!container) {
        const badges = document.getElementById("view-badges");
        container = document.createElement("div");
        container.id = "pbl-section";
        container.className = "pbl-section";
        if (badges) badges.appendChild(container);
        else document.body.appendChild(container);
      }
    }
    this._container = container;
    return container;
  },
};

/* ---------------- PBLLevelView（对外方法，供集成者 / 真实对话流调用） ---------------- */
window.PBLLevelView = {
  /* 对话区追加一条小圆消息 */
  showAssistantMessage(text) {
    const scroll = document.getElementById("pbl-chat-scroll");
    if (!scroll) return;
    appendChatBubble(scroll, "ai", text);
  },

  /* 更新关卡进度（集成者在真实对话 / 模拟器反馈时调用） */
  updateProgress(data) {
    if (!data) return;
    const fill = document.getElementById("pbl-level-progress-fill");
    const label = document.getElementById("pbl-level-progress-label");
    if (fill && typeof data.percent === "number") {
      fill.style.width = Math.max(0, Math.min(100, data.percent)) + "%";
    }
    if (label) {
      const parts = [];
      if (data.percent != null) parts.push("进度 " + Math.round(data.percent) + "%");
      if (data.hit != null) parts.push("命中 " + (data.hit ? "✅" : "❌"));
      if (data.attempts != null) parts.push("尝试 " + data.attempts + " 次");
      if (data.message) parts.push(String(data.message));
      label.textContent = parts.join(" · ");
    }
  },
};

/* ================================================================
   内部工具
   ================================================================ */

function getPblStudentId() {
  if (typeof studentId !== "undefined" && studentId) return studentId;
  return localStorage.getItem("xy_student_id") || null;
}

function pblFetch(path, body, method = "POST") {
  const base = window.PBLView.apiBase || "";
  return fetch(base + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (resp) => {
    if (!resp.ok) {
      let msg = "请求失败";
      try { msg = (await resp.json()).detail || msg; } catch (_) { /* 非 JSON */ }
      throw new Error(msg);
    }
    return resp.json();
  });
}

function escapeHtmlSafe(s) {
  const str = s == null ? "" : String(s);
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* 转义 + 公式渲染（优先用全局 renderMathText，缺失时降级转义） */
function fmt(text) {
  if (text == null) return "";
  const s = String(text);
  if (typeof renderMathText === "function") return renderMathText(s);
  return escapeHtmlSafe(s);
}

function pblToast(text, ms) {
  if (typeof toast === "function") toast(text, ms);
}

function pblCelebrate() {
  if (typeof celebrate === "function") celebrate();
}

function pblLoading(text) {
  return `<div class="pbl-loading">${escapeHtmlSafe(text || "加载中…")}</div>`;
}

function pblEmpty(text) {
  return `<div class="empty-hint">${escapeHtmlSafe(text || "暂无内容")}</div>`;
}

function diffStars(d) {
  if (d == null || d === "") return "";
  if (typeof d === "number") return "★".repeat(Math.max(1, Math.min(5, Math.round(d))));
  const n = parseInt(d, 10);
  if (!isNaN(n)) return "★".repeat(Math.max(1, Math.min(5, n)));
  return escapeHtmlSafe(d);
}

function projectStatusMeta(status) {
  return PBL_STATUS_META[status] || { label: status || "可开始", cls: "available" };
}

function levelNumber(lv, idx) {
  return lv.level != null ? lv.level : (lv.number != null ? lv.number : (lv.level_no != null ? lv.level_no : idx + 1));
}

function resolveLevelStatus(lv) {
  if (lv.status) return String(lv.status).toLowerCase();
  if (lv.completed) return "completed";
  if (lv.locked === true || lv.unlocked === false) return "locked";
  return "available";
}

/* ================================================================
   渲染：项目列表（PBLProjectList）
   ================================================================ */

function renderProjectList(projects) {
  const list = projects || [];
  const grid = list.length
    ? `<div class="pbl-grid">${list.map(renderProjectCard).join("")}</div>`
    : pblEmpty("还没有可参加的项目，稍后再来看看吧～");
  return `
    <h3 class="section-title">🚀 PBL 项目区</h3>
    ${grid}
    <div id="co-creation-section" class="co-creation-section"></div>`;
}

function renderProjectCard(p) {
  const meta = projectStatusMeta(p.status);
  const progress = (p.progress || {});
  const percent = clampPct(progress.percent);
  const recommended = window.PBLView._recommendedIds.has(p.id);
  const done = progress.completed_levels != null && progress.total_levels != null
    ? `${progress.completed_levels}/${progress.total_levels} 关`
    : (percent != null ? `${percent}%` : "");
  return `
    <div class="pbl-project-card" data-pbl-action="open-project" data-id="${escapeHtmlSafe(p.id)}" role="button" tabindex="0">
      ${recommended ? '<span class="pbl-recommend">🔥 推荐</span>' : ""}
      <span class="pbl-status-badge ${meta.cls}">${escapeHtmlSafe(meta.label)}</span>
      <div class="pbl-card-icon">${escapeHtmlSafe(p.icon || "🚀")}</div>
      <div class="pbl-card-name">${escapeHtmlSafe(p.name || "未命名项目")}</div>
      <div class="pbl-card-desc">${escapeHtmlSafe(p.description || "")}</div>
      <div class="pbl-card-tags">
        ${p.category ? `<span class="pbl-tag">${escapeHtmlSafe(p.category)}</span>` : ""}
        ${p.difficulty != null && p.difficulty !== "" ? `<span class="pbl-diff">难度 ${diffStars(p.difficulty)}</span>` : ""}
      </div>
      <div class="pbl-progress"><div class="pbl-progress-fill" style="width:${percent}%"></div></div>
      <div class="pbl-progress-text">${escapeHtmlSafe(done)}${percent != null ? `<span>${percent}%</span>` : ""}</div>
    </div>`;
}

function clampPct(v) {
  if (v == null || isNaN(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

/* ================================================================
   渲染：项目详情（PBLProjectDetail）
   ================================================================ */

function renderProjectDetail(data) {
  const project = (data && data.project) || data || {};
  const levels = (data && data.levels) || project.levels || [];
  const coverage = project.knowledge_coverage || [];
  return `
    <button class="pbl-back" data-pbl-action="back-list">← 返回项目列表</button>
    <div class="pbl-hero">
      <div class="pbl-hero-icon">${escapeHtmlSafe(project.icon || "🚀")}</div>
      <div class="pbl-hero-info">
        <h3 class="pbl-hero-name">${escapeHtmlSafe(project.name || "未命名项目")}</h3>
        <p class="pbl-hero-desc">${escapeHtmlSafe(project.description || "")}</p>
        <div class="pbl-hero-tags">
          ${coverage.map(k => `<span class="pbl-tag">${escapeHtmlSafe(k)}</span>`).join("")}
          ${project.estimated_time ? `<span class="pbl-meta">⏱ ${escapeHtmlSafe(project.estimated_time)}</span>` : ""}
          ${project.grade_range ? `<span class="pbl-meta">🎓 ${escapeHtmlSafe(project.grade_range)}</span>` : ""}
        </div>
      </div>
    </div>
    <h4 class="pbl-sub-title">🗺 关卡</h4>
    <div class="pbl-levels">
      ${levels.length ? levels.map((lv, i) => renderLevelRow(lv, i)).join("") : pblEmpty("暂无关卡")}
    </div>`;
}

function renderLevelRow(lv, idx) {
  const status = resolveLevelStatus(lv);
  const meta = PBL_LEVEL_STATUS[status] || PBL_LEVEL_STATUS.locked;
  const num = levelNumber(lv, idx);
  const best = lv.best_score != null && lv.best_score !== ""
    ? `<span class="pbl-level-best">最佳 ⭐ ${escapeHtmlSafe(lv.best_score)}</span>`
    : "";
  const enterBtn = status === "available"
    ? `<button class="pbl-enter-btn" data-pbl-action="enter-level" data-id="${escapeHtmlSafe(lv.id != null ? lv.id : num)}">进入</button>`
    : "";
  return `
    <div class="pbl-level ${meta.cls}">
      <div class="pbl-level-num">Lv.${num}</div>
      <div class="pbl-level-info">
        <div class="pbl-level-name">${escapeHtmlSafe(lv.name || "未命名关卡")}</div>
        <div class="pbl-level-desc">${escapeHtmlSafe(lv.description || "")}</div>
        ${best}
      </div>
      <div class="pbl-level-state" title="${escapeHtmlSafe(meta.label)}">${meta.icon}</div>
      ${enterBtn}
    </div>`;
}

/* ================================================================
   渲染：关卡视图（PBLLevelView）
   ================================================================ */

function renderLevelView(res) {
  const level = (res && res.level) || {};
  const name = level.name || level.title || "关卡";
  const num = level.level != null ? level.level : (level.number != null ? level.number : "");
  const title = num !== "" ? `Lv.${num} · ${name}` : name;
  return `
    <button class="pbl-back" data-pbl-action="back-detail">← 返回关卡列表</button>
    <div class="pbl-level-head">
      <h3 class="pbl-level-title">${escapeHtmlSafe(title)}</h3>
      <div class="pbl-level-progress">
        <div class="pbl-progress"><div class="pbl-progress-fill" id="pbl-level-progress-fill" style="width:0%"></div></div>
        <div class="pbl-level-progress-label" id="pbl-level-progress-label">任务进行中…</div>
      </div>
    </div>
    <div class="pbl-level-layout">
      <div class="pbl-sim-pane">
        <div id="simulator-container" class="pbl-sim-placeholder">
          <div class="pbl-sim-hint">🧪 模拟器加载中…（由集成者挂载）</div>
        </div>
      </div>
      <div class="pbl-chat-pane">
        <div class="pbl-chat-title">💬 小圆 · 关卡引导</div>
        <div class="pbl-chat-scroll" id="pbl-chat-scroll"></div>
        <div class="pbl-chat-input-row">
          <input id="pbl-chat-input" type="text" maxlength="200" placeholder="和小圆说说你的思路…">
          <button class="pbl-send-btn" data-pbl-action="send">发送</button>
        </div>
        <div class="pbl-chat-hint">真实意图处理由集成者接入，此处仅本地反馈</div>
      </div>
    </div>`;
}

function appendChatBubble(scroll, role, text) {
  const div = document.createElement("div");
  div.className = `pbl-msg ${role}`;
  const avatar = role === "ai" ? "🐱" : "👧";
  div.innerHTML = `<div class="pbl-avatar">${avatar}</div><div class="pbl-bubble">${fmt(text)}</div>`;
  scroll.appendChild(div);
  scroll.scrollTop = scroll.scrollHeight;
  return div;
}

function handleLevelSend() {
  const input = document.getElementById("pbl-chat-input");
  const scroll = document.getElementById("pbl-chat-scroll");
  if (!input || !scroll) return;
  const text = (input.value || "").trim();
  if (!text) return;
  appendChatBubble(scroll, "user", text);
  // 本地占位反馈（真实 intent 处理由集成者接 chat 系统）
  // eslint-disable-next-line no-console
  console.log("[PBL] 关卡对话输入：", text, { projectId: window.PBLView.currentProjectId, levelId: window.PBLView.currentLevelId });
  appendChatBubble(scroll, "ai", "（本地反馈）已收到你的想法，小圆正在看着你操作模拟器～");
  input.value = "";
  input.focus();
}

/* ================================================================
   通关结算 modal（PBLLevelCompleteModal）
   ================================================================ */

function ensureCompleteOverlay() {
  let overlay = document.getElementById("pbl-complete-overlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "pbl-complete-overlay";
  overlay.className = "pbl-complete-overlay hidden";
  overlay.innerHTML = `
    <div class="pbl-complete-card">
      <div class="pbl-stars">★★★</div>
      <div class="pbl-complete-title">关卡通过！</div>
      <div class="pbl-complete-message"></div>
      <div class="pbl-rewards"></div>
      <div class="pbl-knowledge hidden"></div>
      <div class="pbl-complete-btns">
        <button class="pbl-next-btn" data-pbl-action="next-level">下一关 →</button>
        <button class="pbl-ghost-btn" data-pbl-action="close-complete">返回项目</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) overlay.classList.add("hidden");
  });
  return overlay;
}

function closeComplete() {
  const overlay = document.getElementById("pbl-complete-overlay");
  if (overlay) overlay.classList.add("hidden");
}

function renderRewards(rewards) {
  if (!rewards) return "";
  if (Array.isArray(rewards)) {
    return `<div class="pbl-rewards-row">${rewards.map(r => renderRewardItem(r)).join("")}</div>`;
  }
  const parts = [];
  if (rewards.xp) parts.push(renderRewardItem({ type: "xp", label: `+${rewards.xp} XP` }));
  const card = rewards.card_dropped;
  if (card) {
    parts.push(renderRewardItem({
      type: "card",
      label: `🎴 ${card.name || card.front_icon || "新卡片"}`,
    }));
  }
  return parts.length ? `<div class="pbl-rewards-row">${parts.join("")}</div>` : "";
}

function renderRewardItem(r) {
  if (!r) return "";
  const label = r.label || r.name || r.text || (r.amount != null ? `+${r.amount}` : "");
  return `<div class="pbl-reward ${r.type ? "pbl-reward-" + escapeHtmlSafe(r.type) : ""}">${escapeHtmlSafe(label)}</div>`;
}

/* ================================================================
   事件绑定
   ================================================================ */

let pblEventsBound = false;

function bindPblEvents() {
  if (pblEventsBound) return;
  pblEventsBound = true;

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-pbl-action]");
    if (!el) return;
    const action = el.dataset.pblAction;
    const id = el.dataset.id;
    switch (action) {
      case "open-project":
        window.PBLView.loadDetail(id);
        break;
      case "back-list":
        window.PBLView.showProjectList();
        break;
      case "back-detail":
        window.PBLView.loadDetail(window.PBLView.currentProjectId);
        break;
      case "enter-level":
        window.PBLView.enterLevel(window.PBLView.currentProjectId, id);
        break;
      case "send":
        handleLevelSend();
        break;
      case "next-level":
        closeComplete();
        // 下一关：刷新详情（关卡列表会解锁下一关）
        window.PBLView.loadDetail(window.PBLView.currentProjectId);
        break;
      case "close-complete":
        closeComplete();
        break;
    }
  });

  // 输入框回车发送（关卡对话区）
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    if (e.target && e.target.id === "pbl-chat-input") {
      e.preventDefault();
      handleLevelSend();
    }
  });
}

/* 列表卡片事件（键盘可访问性） */
function bindListEvents(container) {
  container.querySelectorAll("[data-pbl-action='open-project']").forEach(card => {
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        window.PBLView.loadDetail(card.dataset.id);
      }
    });
  });
}

function bindDetailEvents(container) { /* 由全局委托处理，无需额外绑定 */ }

function bindLevelEvents(container) { /* 由全局委托处理，无需额外绑定 */ }
