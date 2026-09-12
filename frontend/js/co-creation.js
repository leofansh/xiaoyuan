/* V3.0 P3 · 模块 G「兴趣共创机制」前端 (co-creation.js)
 * 规格 9.4 / 9.5（docs/V3.0开发规格说明书.md 1132-1290 行）
 * - CustomProjectCard   ：共创项目卡片，标"我的项目"标签
 * - CustomProjectDetail ：步骤列表 / 进度条 / 状态切换（标记完成/放弃/完成项目）
 * - ProjectPlanModal    ：项目规划确认弹窗（可编辑步骤名称与描述）
 * 依赖 app.js 的 api()/toast()/celebrate() 全局函数（缺省自动降级，不抛错）。
 * 暴露 window.CoCreation，由 pbl.js 在项目列表下挂载"我的项目"区。
 * 后端共创接口未就绪（404）时自动降级为静态 mock 数据以验证 UI 结构。
 */

(function () {
  "use strict";

  /* ---------------- 常量 ---------------- */
  const CO_STATUS_META = {
    planning:    { label: "规划中", cls: "planning" },
    in_progress: { label: "进行中", cls: "in-progress" },
    completed:   { label: "已完成", cls: "completed" },
    abandoned:   { label: "已放弃", cls: "abandoned" },
  };

  const CO_STEP_META = {
    pending:     { icon: "⏳", label: "待开始", cls: "pending" },
    in_progress: { icon: "🚀", label: "进行中", cls: "in-progress" },
    done:        { icon: "✅", label: "已完成", cls: "done" },
  };

  const INTEREST_ICONS = {
    "游戏": "🎮", "烘焙": "🧁", "运动": "⚽", "音乐": "🎵",
    "美食": "🍜", "科学": "🔬", "动物": "🐾", "画画": "🎨",
    "阅读": "📚", "手工": "🧶", "天文": "🪐", "种植": "🌱",
  };

  /* 后端未就绪时的演示数据（规格 9.2 项目对象形状） */
  const MOCK_PROJECTS = [
    {
      id: "custom_001",
      name: "游戏里最快赚100万金币",
      origin_interest: "游戏",
      created_at: "2026-09-08T20:00:00",
      status: "in_progress",
      steps: [
        { id: 1, name: "统计每天收入", description: "记录游戏中每天各种任务能赚多少钱", math_knowledge: ["统计", "平均数"], status: "done", completed_at: "2026-09-08T20:30:00" },
        { id: 2, name: "算不同任务收益比", description: "比较不同任务的时间和收益，找出性价比最高的", math_knowledge: ["比和比例"], status: "in_progress", completed_at: null },
        { id: 3, name: "找最优组合", description: "用方程找最快赚100万的最优方案", math_knowledge: ["方程", "优化"], status: "pending", completed_at: null },
      ],
      notes: "孩子自己想出来的项目，积极性很高",
      completed_at: null,
    },
    {
      id: "custom_002",
      name: "烘焙店怎么定价",
      origin_interest: "烘焙",
      created_at: "2026-09-09T10:00:00",
      status: "completed",
      steps: [
        { id: 1, name: "算材料成本", description: "统计做一炉饼干的材料成本", math_knowledge: ["统计"], status: "done", completed_at: "2026-09-09T11:00:00" },
        { id: 2, name: "定一个不亏本的售价", description: "用百分数算利润率和定价", math_knowledge: ["百分数"], status: "done", completed_at: "2026-09-10T12:00:00" },
      ],
      notes: "",
      completed_at: "2026-09-10T12:00:00",
    },
  ];

  /* ---------------- 状态 ---------------- */
  let coApiBase = "";
  let coInited = false;
  let coEventsBound = false;
  let coContainer = null;
  let currentSid = null;
  let currentProjectId = null;
  let backendReady = false;      // true 表示后端共创接口可用
  let mockProjects = [];         // 后端未就绪时的内存工作副本
  let projectsCache = [];        // 当前展示的项目列表
  let forceEmpty = false;        // E2E 调试：强制空态（验证空态渲染）

  /* ---------------- 工具 ---------------- */
  function coEsc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function coToast(text, ms) {
    if (typeof toast === "function") toast(text, ms);
    else if (typeof console !== "undefined") console.log(text);
  }

  function coCelebrate() {
    if (typeof celebrate === "function") celebrate();
  }

  function coGetSid() {
    if (typeof window !== "undefined" && window.currentStudentId) return window.currentStudentId;
    if (typeof studentId !== "undefined" && studentId) return studentId;
    try { return localStorage.getItem("xy_student_id") || null; } catch (_) { return null; }
  }

  function deepClone(x) { return x ? JSON.parse(JSON.stringify(x)) : x; }

  function coFmtDate(s) {
    if (!s) return "";
    const str = String(s);
    return str.slice(0, 10) || str;
  }

  function coInterestIcon(k) {
    if (!k) return "✨";
    const s = String(k);
    for (const key of Object.keys(INTEREST_ICONS)) {
      if (s.indexOf(key) >= 0) return INTEREST_ICONS[key];
    }
    return "✨";
  }

  function coLoading(text) {
    return `<div class="co-loading">${coEsc(text || "加载中…")}</div>`;
  }

  function coEmpty(text) {
    return `<div class="co-empty">${coEsc(text || "暂无内容")}</div>`;
  }

  /* 统一请求：返回 { ok, status, data }，不抛非 ok 错误，便于识别 404 降级 */
  async function coRequest(path, body, method) {
    method = method || "POST";
    try {
      const resp = await fetch(coApiBase + path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data = null;
      try { data = await resp.json(); } catch (_) { /* 非 JSON */ }
      return { ok: resp.ok, status: resp.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: null, error: e };
    }
  }

  /* ---------------- 数据获取（含 mock 降级） ---------------- */
  async function loadProjects(sid) {
    if (forceEmpty) { backendReady = true; projectsCache = []; return; }
    const res = await coRequest(`/api/custom-projects/${encodeURIComponent(sid)}`, null, "GET");
    if (res.ok && res.data && res.data.success) {
      backendReady = true;
      projectsCache = res.data.projects || [];
      return;
    }
    backendReady = false;
    if (!mockProjects.length) mockProjects = deepClone(MOCK_PROJECTS);
    projectsCache = mockProjects;
  }

  function findProject(id) {
    return projectsCache.find(p => String(p.id) === String(id)) || null;
  }

  async function createProject(payload) {
    const res = await coRequest(`/api/custom-projects/${encodeURIComponent(currentSid)}`, payload, "POST");
    if (res.ok && res.data && res.data.success) {
      backendReady = true;
      return res.data;
    }
    backendReady = false;
    if (!mockProjects.length) mockProjects = deepClone(MOCK_PROJECTS);
    return mockCreate(payload);
  }

  async function markStepDone(stepId) {
    const url = `/api/custom-projects/${encodeURIComponent(currentSid)}/${encodeURIComponent(currentProjectId)}/steps/${encodeURIComponent(stepId)}`;
    const res = await coRequest(url, { status: "done" }, "POST");
    if (res.ok && res.data && res.data.success) { backendReady = true; return res.data; }
    backendReady = false;
    return mockStepDone(currentProjectId, stepId);
  }

  async function setProjectStatus(status) {
    const url = `/api/custom-projects/${encodeURIComponent(currentSid)}/${encodeURIComponent(currentProjectId)}/status`;
    const res = await coRequest(url, { status }, "POST");
    if (res.ok && res.data && res.data.success) { backendReady = true; return res.data; }
    backendReady = false;
    return mockSetStatus(currentProjectId, status);
  }

  /* ---------------- mock 写操作 ---------------- */
  function mockCreate(payload) {
    const p = {
      id: "custom_mock_" + Date.now(),
      name: payload.name,
      origin_interest: payload.origin_interest || "兴趣",
      created_at: new Date().toISOString(),
      status: "in_progress",
      steps: (payload.steps || []).map((s, i) => ({
        id: i + 1,
        name: s.name,
        description: s.description || "",
        math_knowledge: s.math_knowledge || [],
        status: i === 0 ? "in_progress" : "pending",
        completed_at: null,
      })),
      notes: payload.notes || "",
      completed_at: null,
    };
    mockProjects.unshift(p);
    return { success: true, project: p };
  }

  function mockStepDone(projectId, stepId) {
    const p = findProject(projectId);
    if (!p) throw new Error("项目不存在");
    const idx = p.steps.findIndex(s => String(s.id) === String(stepId));
    if (idx < 0) throw new Error("步骤不存在");
    p.steps[idx].status = "done";
    p.steps[idx].completed_at = new Date().toISOString();
    const next = p.steps[idx + 1];
    let unlocked = false;
    if (next && next.status === "pending") { next.status = "in_progress"; unlocked = true; }
    return { success: true, step: p.steps[idx], next_step_unlocked: unlocked };
  }

  function mockSetStatus(projectId, status) {
    const p = findProject(projectId);
    if (!p) throw new Error("项目不存在");
    p.status = status;
    if (status === "completed") p.completed_at = new Date().toISOString();
    return { success: true, project: p };
  }

  /* ================================================================
     渲染：项目列表（CustomProjectCard）
     ================================================================ */
  function renderProjectList() {
    if (!coContainer) return Promise.resolve();
    const sid = currentSid || coGetSid();
    if (!sid) { coContainer.innerHTML = coEmpty("请先登录学生档案～"); return Promise.resolve(); }
    currentSid = sid;
    coContainer.innerHTML = coLoading("正在加载我的项目…");
    return loadProjects(sid).then(() => {
      coContainer.innerHTML = renderListHTML(projectsCache);
      bindCoCardKeys(coContainer);
    }).catch((e) => {
      coContainer.innerHTML = coEmpty("我的项目加载失败：" + (e && e.message ? e.message : "网络开小差了"));
    });
  }

  function renderListHTML(list) {
    const items = list || [];
    const body = items.length
      ? `<div class="co-grid">${items.map(renderCard).join("")}</div>`
      : `<div class="co-empty">💭 还没有共创项目，和我说说你的兴趣，一起设计一个吧！</div>`;
    return `
      <div class="co-wrap">
        <div class="co-head">
          <h4 class="co-title">🌟 我的项目</h4>
          <button class="co-new-btn" data-co-action="new-project">＋ 新建项目</button>
        </div>
        ${backendReady ? "" : '<div class="co-mock-tip">后端共创接口尚未就绪，当前展示演示数据</div>'}
        ${body}
      </div>`;
  }

  function renderCard(p) {
    const steps = p.steps || [];
    const done = steps.filter(s => s.status === "done").length;
    const total = steps.length;
    const pct = total ? Math.round(done / total * 100) : 0;
    const meta = CO_STATUS_META[p.status] || { label: p.status || "进行中", cls: "in-progress" };
    return `
      <div class="co-card" data-co-action="open-project" data-id="${coEsc(p.id)}" role="button" tabindex="0">
        <span class="co-my-tag">我的项目</span>
        <span class="co-status-badge ${meta.cls}">${coEsc(meta.label)}</span>
        <div class="co-card-icon">${coInterestIcon(p.origin_interest)}</div>
        <div class="co-card-name">${coEsc(p.name || "未命名项目")}</div>
        <div class="co-card-interest">🎯 ${coEsc(p.origin_interest || "兴趣")}</div>
        <div class="co-progress"><div class="co-progress-fill" style="width:${pct}%"></div></div>
        <div class="co-progress-text">${done}/${total} 步</div>
      </div>`;
  }

  /* ================================================================
     渲染：项目详情（CustomProjectDetail）
     ================================================================ */
  function renderDetail(projectId) {
    if (!coContainer) return Promise.resolve();
    const p = findProject(projectId);
    if (!p) { coToast("项目不见了，返回列表看看吧～"); return renderProjectList(); }
    currentProjectId = projectId;
    coContainer.innerHTML = renderDetailHTML(p);
    return Promise.resolve();
  }

  function renderDetailHTML(p) {
    const steps = p.steps || [];
    const done = steps.filter(s => s.status === "done").length;
    const total = steps.length;
    const pct = total ? Math.round(done / total * 100) : 0;
    const allDone = total > 0 && done === total;
    const meta = CO_STATUS_META[p.status] || { label: p.status || "进行中", cls: "in-progress" };
    const isAbandoned = p.status === "abandoned";
    const isCompleted = p.status === "completed";
    const inProg = steps.findIndex(s => s.status === "in_progress");
    const firstPending = steps.findIndex(s => s.status === "pending");
    const activeIdx = inProg >= 0 ? inProg : firstPending;

    return `
      <div class="co-wrap">
        <button class="co-back" data-co-action="back-list">← 返回我的项目</button>
        <div class="co-detail-hero">
          <div class="co-hero-icon">${coInterestIcon(p.origin_interest)}</div>
          <div class="co-hero-info">
            <h3 class="co-hero-name">${coEsc(p.name || "未命名项目")}</h3>
            <div class="co-hero-meta">
              <span>🎯 ${coEsc(p.origin_interest || "兴趣")}</span>
              <span>📅 ${coEsc(coFmtDate(p.created_at))}</span>
              <span class="co-status-badge ${meta.cls}">${coEsc(meta.label)}</span>
            </div>
          </div>
        </div>
        <div class="co-progress"><div class="co-progress-fill" style="width:${pct}%"></div></div>
        <div class="co-progress-text">已完成 ${done}/${total} 步 · ${pct}%</div>
        ${p.notes ? `<div class="co-notes">📝 ${coEsc(p.notes)}</div>` : ""}
        <h5 class="co-sub-title">🗺 项目步骤</h5>
        <div class="co-steps">
          ${steps.length ? steps.map((s, i) => renderStepRow(s, i, activeIdx, isAbandoned, isCompleted)).join("") : coEmpty("还没有步骤")}
        </div>
        <div class="co-detail-actions">
          ${(isAbandoned || isCompleted) ? "" : '<button class="co-abandon-btn" data-co-action="abandon-project">🪁 先放着（放弃）</button>'}
          ${allDone && !isCompleted ? '<button class="co-complete-btn" data-co-action="complete-project">🎉 完成项目</button>' : ""}
        </div>
      </div>`;
  }

  function renderStepRow(s, i, activeIdx, isAbandoned, isCompleted) {
    const smeta = CO_STEP_META[s.status] || CO_STEP_META.pending;
    const active = i === activeIdx && !isAbandoned && !isCompleted;
    const canComplete = s.status === "in_progress" && !isAbandoned && !isCompleted;
    return `
      <div class="co-step ${smeta.cls} ${active ? "active" : ""}">
        <div class="co-step-num">${i + 1}</div>
        <div class="co-step-info">
          <div class="co-step-name">${coEsc(s.name || "未命名步骤")}</div>
          <div class="co-step-desc">${coEsc(s.description || "")}</div>
          ${s.math_knowledge && s.math_knowledge.length ? `<div class="co-step-k">📚 ${s.math_knowledge.map(coEsc).join(" · ")}</div>` : ""}
        </div>
        <div class="co-step-state" title="${coEsc(smeta.label)}">${smeta.icon} <span>${coEsc(smeta.label)}</span></div>
        ${canComplete ? `<button class="co-step-done-btn" data-co-action="mark-step-done" data-step-id="${coEsc(s.id)}">标记完成 ✅</button>` : ""}
      </div>`;
  }

  /* ================================================================
     项目规划弹窗（ProjectPlanModal）
     ================================================================ */
  function ensurePlanModal() {
    let overlay = document.getElementById("co-plan-modal");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "co-plan-modal";
    overlay.className = "co-overlay hidden";
    overlay.innerHTML = `
      <div class="co-modal-card" role="dialog" aria-modal="true">
        <button class="co-modal-close" data-co-action="plan-close" aria-label="关闭">×</button>
        <div class="co-modal-title">📝 一起设计你的项目</div>
        <div class="co-modal-hint">把小圆陪你聊出来的想法，整理成一个属于你的项目吧～</div>
        <label class="co-field">
          <span class="co-field-label">项目名称</span>
          <input id="co-plan-name" type="text" maxlength="40" placeholder="比如：游戏里最快赚100万金币">
        </label>
        <label class="co-field">
          <span class="co-field-label">来自你的兴趣</span>
          <input id="co-plan-interest" type="text" maxlength="20" placeholder="比如：游戏 / 烘焙 / 运动">
        </label>
        <div class="co-field">
          <span class="co-field-label">项目步骤（名称和描述都可以改）</span>
          <div id="co-plan-steps" class="co-plan-steps"></div>
          <button class="co-add-step-btn" data-co-action="plan-add-step" type="button">＋ 添加步骤</button>
        </div>
        <label class="co-field">
          <span class="co-field-label">小圆备注（可选）</span>
          <textarea id="co-plan-notes" rows="2" maxlength="200" placeholder="记下这次共创的小发现～"></textarea>
        </label>
        <div class="co-modal-btns">
          <button class="co-ghost-btn" data-co-action="plan-close" type="button">再想想</button>
          <button class="co-submit-btn" data-co-action="plan-submit" type="button">确认创建 ✨</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", e => {
      if (e.target === e.currentTarget) closePlanModal();
    });
    return overlay;
  }

  function openPlanModal() {
    const overlay = ensurePlanModal();
    overlay.querySelector("#co-plan-name").value = "";
    overlay.querySelector("#co-plan-interest").value = "";
    overlay.querySelector("#co-plan-notes").value = "";
    const box = overlay.querySelector("#co-plan-steps");
    box.innerHTML = "";
    for (let i = 0; i < 3; i++) appendPlanStepRow(box);
    overlay.classList.remove("hidden");
  }

  function closePlanModal() {
    const overlay = document.getElementById("co-plan-modal");
    if (overlay) overlay.classList.add("hidden");
  }

  function appendPlanStepRow(box) {
    const idx = box.children.length;
    const row = document.createElement("div");
    row.className = "co-plan-step";
    row.dataset.stepIndex = idx;
    row.innerHTML = `
      <div class="co-plan-step-head">
        <span class="co-plan-step-no">步骤 ${idx + 1}</span>
        <button class="co-plan-step-del" data-co-action="plan-remove-step" type="button" aria-label="删除此步骤">×</button>
      </div>
      <input class="co-plan-step-name" type="text" maxlength="40" placeholder="步骤名称，比如：统计每天收入">
      <input class="co-plan-step-desc" type="text" maxlength="120" placeholder="这一步要做什么？（一句话描述）">
    `;
    box.appendChild(row);
  }

  function reindexPlanSteps(box) {
    box.querySelectorAll(".co-plan-step").forEach((row, i) => {
      row.dataset.stepIndex = i;
      const no = row.querySelector(".co-plan-step-no");
      if (no) no.textContent = `步骤 ${i + 1}`;
    });
  }

  async function submitPlan() {
    const overlay = document.getElementById("co-plan-modal");
    if (!overlay) return;
    const name = overlay.querySelector("#co-plan-name").value.trim();
    const interest = overlay.querySelector("#co-plan-interest").value.trim();
    const notes = overlay.querySelector("#co-plan-notes").value.trim();
    const steps = Array.prototype.map.call(overlay.querySelectorAll(".co-plan-step"), row => ({
      name: row.querySelector(".co-plan-step-name").value.trim(),
      description: row.querySelector(".co-plan-step-desc").value.trim(),
      math_knowledge: [],
    })).filter(s => s.name);

    if (!name) { coToast("先给项目起个名字吧～"); return; }
    if (!steps.length) { coToast("至少要有一步哦，先写一个第一步吧～"); return; }

    const submitBtn = overlay.querySelector("[data-co-action='plan-submit']");
    submitBtn.disabled = true;
    try {
      await createProject({ name, origin_interest: interest, steps, notes });
      closePlanModal();
      coToast("🎉 项目创建好啦！从第一步开始吧～", 2800);
      coCelebrate();
      await renderProjectList();
    } catch (e) {
      coToast("创建失败：" + (e && e.message ? e.message : "网络开小差了"));
    } finally {
      submitBtn.disabled = false;
    }
  }

  /* ================================================================
     动作处理（事件委托 + 对外接口）
     ================================================================ */
  function doMarkStepDone(stepId) {
    return markStepDone(stepId).then((res) => {
      if (backendReady) return loadProjects(currentSid);
    }).then(() => {
      coToast("✅ 这一步完成啦！");
      renderDetail(currentProjectId);
    }).catch((e) => {
      coToast("标记失败：" + (e && e.message ? e.message : "网络开小差了"));
    });
  }

  function doSetStatus(status) {
    return setProjectStatus(status).then(() => {
      if (backendReady) return loadProjects(currentSid);
    }).then(() => {
      coToast(status === "completed" ? "🎉 恭喜完成项目！" : "没关系，随时可以回来继续～");
      if (status === "completed") coCelebrate();
      renderProjectList();
    }).catch((e) => {
      coToast("操作失败：" + (e && e.message ? e.message : "网络开小差了"));
    });
  }

  function handleAction(action, payload) {
    switch (action) {
      case "new-project": openPlanModal(); break;
      case "open-project": renderDetail(payload && payload.id); break;
      case "back-list": renderProjectList(); break;
      case "mark-step-done": doMarkStepDone(payload && payload.stepId); break;
      case "abandon-project": doSetStatus("abandoned"); break;
      case "complete-project": doSetStatus("completed"); break;
      case "plan-add-step": {
        const box = document.getElementById("co-plan-steps");
        if (box) appendPlanStepRow(box);
        break;
      }
      case "plan-remove-step": {
        const box = document.getElementById("co-plan-steps");
        const row = payload && payload.el ? payload.el.closest(".co-plan-step") : null;
        if (row && box && box.children.length > 1) { row.remove(); reindexPlanSteps(box); }
        break;
      }
      case "plan-close": closePlanModal(); break;
      case "plan-submit": submitPlan(); break;
    }
  }

  function bindCoEvents() {
    if (coEventsBound) return;
    coEventsBound = true;
    document.addEventListener("click", (e) => {
      const el = e.target.closest("[data-co-action]");
      if (!el) return;
      const action = el.dataset.coAction;
      handleAction(action, { id: el.dataset.id, stepId: el.dataset.stepId, el });
    });
  }

  function bindCoCardKeys(container) {
    container.querySelectorAll("[data-co-action='open-project']").forEach(card => {
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          renderDetail(card.dataset.id);
        }
      });
    });
  }

  /* ---------------- 对外暴露 ---------------- */
  function mountInto(containerEl, sid) {
    coContainer = containerEl;
    if (sid) currentSid = sid;
    return renderProjectList();
  }

  function init(apiBase) {
    if (coInited) return;
    coInited = true;
    coApiBase = apiBase || "";
    ensurePlanModal();
    bindCoEvents();
  }

  window.CoCreation = {
    init,
    mountInto,
    renderProjectList,
    renderDetail,
    handleAction,
    /* E2E 调试钩子：置空 mock 以验证空态渲染 */
    _debugEmpty() { mockProjects = []; projectsCache = []; backendReady = false; forceEmpty = true; return renderProjectList(); },
    _debugRestore() { forceEmpty = false; mockProjects = []; projectsCache = []; return renderProjectList(); },
  };
})();
