/* V3.0 P2 · 模块「🍰 烘焙实验室」前端模拟器 (simulators/baking.js)
 * - BakingSimulator：交互式"烘焙工作台"（材料滑块 / 温度拨盘 / 计时条，可视化即时反馈）
 *   6 种模式：
 *   recipe_scale 配方换算 / doubling 倍增 / temperature 温度换算 / time 时间分配 / party_plan 派对规划 / free 自由烘焙
 * - 暴露 window.BakingSimulator.createSimulator(containerEl, config) 供 pbl-baking.js 挂载
 * - 纯原生 JS，静态 DOM 渲染 + 响应式（CSS 负责）；判定用相对误差 |输入-期望|/期望
 * 依赖（可选）：app.js 的 escapeHtml()（缺失时本地降级）
 */

(function () {
  "use strict";

  const CREATIONS_KEY = "xy_baking_creations";

  /* 判定容差：相对误差阈值（温度换算要求精确，使用更严的阈值） */
  const TOLERANCE = 0.02;
  const TOLERANCE_TEMP = 0.001;

  /* 自由烘焙的常用材料（材料 emoji 仅作功能语义） */
  const DEFAULT_INGREDIENTS = [
    { name: "低筋面粉", emoji: "🌾", unit: "克" },
    { name: "细砂糖", emoji: "🍬", unit: "克" },
    { name: "黄油", emoji: "🧈", unit: "克" },
    { name: "鸡蛋", emoji: "🥚", unit: "个" },
    { name: "牛奶", emoji: "🥛", unit: "毫升" },
    { name: "巧克力", emoji: "🍫", unit: "块" },
    { name: "草莓", emoji: "🍓", unit: "颗" },
    { name: "淡奶油", emoji: "🍦", unit: "克" },
  ];

  const esc = (typeof escapeHtml === "function") ? escapeHtml
    : (s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }
  function num(v, d) { const n = Number(v); return isFinite(n) ? n : d; }
  function round1(v) { return Math.round(v * 10) / 10; }
  function isIntegerish(v) { return Math.abs(v - Math.round(v)) < 1e-9; }

  /* 摄氏 ↔ 华氏（°F = °C × 9/5 + 32） */
  function toFahrenheit(c) { return round1(num(c, 0) * 9 / 5 + 32); }
  function toCelsius(f) { return round1((num(f, 0) - 32) * 5 / 9); }

  /* 滑块上限：在期望值上方留出余量，避免直接暴露答案 */
  function sliderMax(e) {
    if (!(e > 0)) return 10;
    const mag = Math.pow(10, Math.floor(Math.log10(e)));
    return Math.ceil((e / mag) + 0.5) * mag;
  }

  /* 判定核心：按相对误差 |输入-期望|/期望 逐项判定，输出 {hit, ratio(0-100), okCount, total}
   * ratio：命中=100；未命中=min(79, round(准确率×100)) */
  function judge(inputs, expecteds, tol) {
    const t = tol == null ? TOLERANCE : tol;
    const list = expecteds || [];
    if (list.length === 0) return { hit: false, ratio: 0, okCount: 0, total: 0 };
    const total = list.length;
    let okCount = 0, errSum = 0;
    for (let i = 0; i < total; i++) {
      const inp = Math.max(0, num(inputs[i], 0));
      const exp = num(expecteds[i], 0);
      const err = exp !== 0 ? Math.abs(inp - exp) / Math.abs(exp) : (inp === 0 ? 0 : 1);
      if (err <= t) okCount++;
      errSum += clamp(err, 0, 1);
    }
    const hit = okCount === total;
    let ratio = Math.round((1 - errSum / total) * 100);
    if (hit) ratio = 100; else ratio = Math.min(79, ratio);
    return { hit, ratio, okCount, total };
  }

  function readCreations() {
    try {
      const raw = localStorage.getItem(CREATIONS_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (_) { return []; }
  }
  function writeCreations(arr) {
    try { localStorage.setItem(CREATIONS_KEY, JSON.stringify(arr)); } catch (_) { /* 存储满则忽略 */ }
  }

  const DEFAULT_CONFIG = {
    mode: "free",
    help_button: false,
    // recipe_scale
    ingredients: [], from_servings: 3, to_servings: 5,
    // doubling
    factor: 2,
    // temperature
    temps: [], target: 180,
    // time
    total_minutes: 60, segments: [],
    // party_plan
    per_person: [], target_people: 8,
  };

  /* ---------------------------------------------------------------- 模拟器实例 */
  function createSimulator(containerEl, config) {
    if (!containerEl) throw new Error("BakingSimulator: 缺少容器元素");

    const cfg = Object.assign({}, DEFAULT_CONFIG, config || {});
    const mode = cfg.mode || "free";

    const state = {
      attempts: 0,
      hitResult: null,
      values: {},   // key -> number
      fields: [],   // 判定字段描述
    };

    let els = {};
    let hitCallback = null, helpCallback = null;

    /* ---------------- 目标温度（°C）解析 ---------------- */
    function targetCelsius() {
      const t = cfg.target;
      if (t && typeof t === "object") return num(t.c != null ? t.c : t.f, 180);
      return num(t, 180);
    }

    /* ---------------- 判定字段构建 ---------------- */
    function fieldOf(key, it, expected) {
      return {
        key,
        label: it.name,
        emoji: it.emoji || null,
        unit: it.unit || "份",
        ref: num(it.amount, 0),
        expected: round1(expected),
      };
    }

    function buildFields() {
      let fields = [];
      if (mode === "recipe_scale") {
        const factor = num(cfg.to_servings, 5) / num(cfg.from_servings, 3);
        fields = (cfg.ingredients || []).map((it, i) =>
          fieldOf("ing_" + i, it, num(it.amount, 0) * factor));
      } else if (mode === "doubling") {
        const factor = num(cfg.factor, 2);
        fields = (cfg.ingredients || []).map((it, i) =>
          fieldOf("ing_" + i, it, num(it.amount, 0) * factor));
      } else if (mode === "temperature") {
        const c = targetCelsius();
        fields = [{ key: "temp_f", label: "烤箱温度", emoji: "🌡️", unit: "°F", ref: null, refText: round1(c) + "°C", expected: toFahrenheit(c), max: 450, step: 1 }];
      } else if (mode === "time") {
        const total = num(cfg.total_minutes, 60);
        fields = (cfg.segments || []).map((s, i) => ({
          key: "seg_" + i,
          label: s.name || ("第" + (i + 1) + "步"),
          emoji: null,
          unit: "分钟",
          ref: null,
          expected: round1(total * num(s.ratio, 0)),
          max: total,
          step: 1,
        }));
      } else if (mode === "party_plan") {
        const people = num(cfg.target_people, 8);
        fields = (cfg.per_person || []).map((it, i) =>
          fieldOf("pp_" + i, it, num(it.amount, 0) * people));
      }
      fields.forEach(f => {
        if (f.max == null) f.max = sliderMax(f.expected);
        if (f.step == null) f.step = isIntegerish(f.expected) ? 1 : 0.5;
        state.values[f.key] = 0;
      });
      return fields;
    }

    /* ---------------- 标题 / 引导 ---------------- */
    function titleHTML() {
      const t = {
        recipe_scale: `配方换算：${num(cfg.from_servings, 3)} 人份 → ${num(cfg.to_servings, 5)} 人份`,
        doubling: `配方倍增：所有材料 ×${num(cfg.factor, 2)}`,
        temperature: "温度换算：摄氏（°C）→ 华氏（°F）",
        time: `时间分配：总时长 ${num(cfg.total_minutes, 60)} 分钟`,
        party_plan: `派对规划：${num(cfg.target_people, 8)} 人份整桌食材`,
        free: "自由烘焙：创作你的专属配方",
      };
      return t[mode] || "烘焙工作台";
    }
    function hintHTML() {
      const t = {
        recipe_scale: "把每个材料的用量按人数比例换算，填入你的答案",
        doubling: "把每个材料的用量都乘以同一个倍数",
        temperature: "°F = °C × 9 ÷ 5 + 32，算出对应的华氏温度",
        time: "把总时长按比例拆到每一步，三段加起来正好等于总时长",
        party_plan: "每个人要吃的量 × 人数，就是整桌要准备的总量",
        free: "选几种材料、填好用量，给你的配方起个名字",
      };
      return t[mode] || "";
    }

    /* ---------------- 内容区 HTML ---------------- */
    function amountRowHTML(f) {
      const emoji = f.emoji ? `<span class="bake-ing-emoji" aria-hidden="true">${esc(f.emoji)}</span>` : "";
      const ref = f.ref != null && f.ref !== "" ? `<span class="bake-ref">原配方 ${esc(round1(f.ref))} ${esc(f.unit)}</span>` : "";
      const refText = f.refText ? `<span class="bake-ref">已知 ${esc(f.refText)}</span>` : "";
      const slider = `<input type="range" class="bake-slider js-slider" data-key="${esc(f.key)}" min="0" max="${f.max}" step="${f.step}" value="0" aria-label="调整${esc(f.label)}用量">`;
      const numInput = `<input type="number" class="bake-num js-num" data-key="${esc(f.key)}" min="0" step="any" value="0" inputmode="decimal" aria-label="${esc(f.label)}的用量">`;
      return `
        <div class="bake-row" data-key="${esc(f.key)}">
          <div class="bake-row-head">
            <span class="bake-ing">${emoji}<span class="bake-ing-name">${esc(f.label)}</span></span>
            ${ref}${refText}
          </div>
          <div class="bake-row-body">
            ${slider}
            ${numInput}
            <span class="bake-unit">${esc(f.unit)}</span>
          </div>
          <div class="bake-track" role="img" aria-label="${esc(f.label)}用量可视化"><div class="bake-fill js-fill"></div></div>
        </div>`;
    }

    function temperatureHTML(f) {
      const refs = (cfg.temps || []).map(t =>
        `<span class="bake-temp-ref">${esc(round1(num(t.c, 0)))}°C = ${esc(round1(num(t.f, 0)))}°F</span>`).join("");
      return `
        <div class="bake-temp-guide">${refs}</div>
        <div class="bake-temp-wrap">
          <div class="bake-thermo" role="img" aria-label="烤箱温度计">
            <div class="bake-thermo-fill js-thermo-fill"></div>
            <div class="bake-thermo-bulb"></div>
          </div>
          <div class="bake-temp-input">
            <div class="bake-temp-label">把 ${esc(f.refText || (round1(targetCelsius()) + "°C"))} 换算成华氏温度</div>
            <div class="bake-temp-row">
              <input type="number" class="bake-num bake-temp-num js-num" data-key="${esc(f.key)}" min="0" step="1" value="0" inputmode="numeric" aria-label="华氏温度">
              <span class="bake-unit">°F</span>
            </div>
            <div class="bake-temp-readout js-thermo-read" aria-live="polite">— °F</div>
          </div>
        </div>`;
    }

    function timeHTML(fields) {
      const total = num(cfg.total_minutes, 60);
      const rows = fields.map(f => `
        <div class="bake-timer" data-key="${esc(f.key)}">
          <div class="bake-timer-head">
            <span class="bake-ing-name">${esc(f.label)}</span>
            <span class="bake-timer-val js-timer-val">0 分钟</span>
          </div>
          <div class="bake-timer-body">
            <input type="range" class="bake-slider js-slider" data-key="${esc(f.key)}" min="0" max="${total}" step="1" value="0" aria-label="分配${esc(f.label)}时长">
            <input type="number" class="bake-num js-num" data-key="${esc(f.key)}" min="0" step="1" value="0" inputmode="numeric" aria-label="${esc(f.label)}的分钟数">
            <span class="bake-unit">分钟</span>
          </div>
          <div class="bake-track bake-timer-track"><div class="bake-fill js-fill"></div></div>
        </div>`).join("");
      return `
        <div class="bake-timers">${rows}</div>
        <div class="bake-time-total js-time-total" aria-live="polite">已分配 0 / ${total} 分钟</div>`;
    }

    function freeHTML() {
      const rows = DEFAULT_INGREDIENTS.map((ing, i) => `
        <div class="bake-free-row" data-key="free_${i}">
          <span class="bake-free-ing"><span class="bake-ing-emoji" aria-hidden="true">${esc(ing.emoji)}</span>${esc(ing.name)}</span>
          <input type="number" class="bake-num js-num" data-key="free_${i}" min="0" step="any" value="0" inputmode="decimal" aria-label="${esc(ing.name)}用量">
          <span class="bake-unit">${esc(ing.unit)}</span>
        </div>`).join("");
      return `
        <div class="bake-free">
          <label class="bake-name-row">
            <span class="bake-name-label">配方名</span>
            <input class="bake-name js-name" maxlength="20" placeholder="我的蛋糕" aria-label="配方名">
          </label>
          <div class="bake-free-ing-list">${rows}</div>
          <div class="bake-free-hint">用量填 0 表示不用这种材料</div>
        </div>`;
    }

    function bodyHTML(fields) {
      if (mode === "temperature") return temperatureHTML(fields[0]);
      if (mode === "time") return timeHTML(fields);
      if (mode === "free") return freeHTML();
      return `<div class="bake-rows">${fields.map(amountRowHTML).join("")}</div>`;
    }

    function toolbarHTML() {
      const helpBtn = cfg.help_button ? `<button class="bake-btn bake-btn-help js-help" aria-label="计算辅助">🧮 计算辅助</button>` : "";
      const submitLabel = mode === "free" ? "💾 保存配方" : "🍰 提交烘焙";
      return `
        <div class="bake-toolbar">
          <div class="bake-actions">
            <button class="bake-btn bake-btn-submit js-submit">${submitLabel}</button>
            <button class="bake-btn js-reset">↺ 重置</button>
            ${helpBtn}
          </div>
        </div>`;
    }

    /* ---------------- 渲染 ---------------- */
    function render() {
      state.attempts = 0;
      state.hitResult = null;
      state.values = {};
      state.fields = buildFields();

      containerEl.classList.add("bake-sim");
      containerEl.innerHTML = `
        <div class="bake-title">🍰 ${esc(titleHTML())}</div>
        <div class="bake-hint">${esc(hintHTML())}</div>
        ${bodyHTML(state.fields)}
        <div class="bake-status">
          <span class="bake-attempts js-attempts">已尝试 0 次</span>
          <span class="bake-result js-status"></span>
        </div>
        ${toolbarHTML()}
      `;

      els = {
        submit: containerEl.querySelector(".js-submit"),
        reset: containerEl.querySelector(".js-reset"),
        help: containerEl.querySelector(".js-help"),
        attempts: containerEl.querySelector(".js-attempts"),
        status: containerEl.querySelector(".js-status"),
        name: containerEl.querySelector(".js-name"),
        timeTotal: containerEl.querySelector(".js-time-total"),
        thermoRead: containerEl.querySelector(".js-thermo-read"),
        thermoFill: containerEl.querySelector(".js-thermo-fill"),
      };

      wireEvents();
      syncAll();
      updateHUD();
      updateStatus();
      return inst;
    }

    function wireEvents() {
      if (els.submit) els.submit.onclick = () => (mode === "free" ? saveRecipe() : submitAnswer());
      if (els.reset) els.reset.onclick = () => reset();
      if (els.help) els.help.onclick = () => { if (helpCallback) helpCallback(); };

      containerEl.querySelectorAll(".js-slider").forEach(s => {
        s.addEventListener("input", () => onSlider(s));
      });
      containerEl.querySelectorAll(".js-num").forEach(n => {
        n.addEventListener("input", () => onNum(n));
      });
    }

    /* ---------------- 输入同步 ---------------- */
    function readValue(key) {
      const v = num(state.values[key], 0);
      return isFinite(v) ? Math.max(0, v) : 0;
    }

    function onSlider(slider) {
      const key = slider.dataset.key;
      const v = Math.max(0, num(slider.value, 0));
      state.values[key] = v;
      syncField(key);
    }
    function onNum(input) {
      const key = input.dataset.key;
      let v = num(input.value, 0);
      if (!isFinite(v) || v < 0) v = 0;
      state.values[key] = v;
      syncField(key);
    }

    function fieldByKey(key) {
      return state.fields.find(f => f.key === key) || null;
    }

    function syncField(key) {
      const f = fieldByKey(key);
      const v = readValue(key);
      const slider = containerEl.querySelector(`.js-slider[data-key="${key}"]`);
      const numInput = containerEl.querySelector(`.js-num[data-key="${key}"]`);
      const fill = containerEl.querySelector(`.bake-row[data-key="${key}"] .js-fill`) ||
        containerEl.querySelector(`.bake-timer[data-key="${key}"] .js-fill`);
      if (slider) { const mx = num(slider.max, 10); slider.value = clamp(v, 0, mx); }
      if (numInput) numInput.value = v;
      if (fill) {
        const denom = mode === "time" ? num(cfg.total_minutes, 60) : (f ? f.max : 10);
        fill.style.width = (clamp(v / (denom || 1), 0, 1) * 100) + "%";
      }
      if (mode === "time") updateTimeSummary();
      if (mode === "temperature") updateThermo();
    }

    function syncAll() {
      state.fields.forEach(f => syncField(f.key));
      if (mode === "time") updateTimeSummary();
      if (mode === "temperature") updateThermo();
    }

    function updateTimeSummary() {
      if (!els.timeTotal) return;
      const total = num(cfg.total_minutes, 60);
      let sum = 0;
      state.fields.forEach(f => { sum += readValue(f.key); });
      state.fields.forEach(f => {
        const el = containerEl.querySelector(`.bake-timer[data-key="${f.key}"] .js-timer-val`);
        if (el) el.textContent = round1(readValue(f.key)) + " 分钟";
      });
      els.timeTotal.textContent = `已分配 ${round1(sum)} / ${total} 分钟`;
      els.timeTotal.classList.toggle("bake-time-over", sum > total);
    }

    function updateThermo() {
      const f = state.fields[0];
      if (!f) return;
      const v = readValue(f.key);
      if (els.thermoRead) els.thermoRead.textContent = v + " °F";
      if (els.thermoFill) {
        const pct = clamp((v - 32) / (450 - 32), 0, 1) * 100;
        els.thermoFill.style.height = pct + "%";
      }
    }

    /* ---------------- 状态 / HUD ---------------- */
    function updateStatus() {
      if (!els.status) return;
      let text = "";
      if (state.hitResult) {
        text = state.hitResult.hit ? "🎉 完成！烘烤成功～" : "还差一点，再算一算～";
      } else {
        text = mode === "free" ? "自由发挥，做出属于你的美味" : "填好答案后点「提交烘焙」";
      }
      els.status.textContent = text;
    }
    function updateHUD() {
      if (els.attempts) els.attempts.textContent = "已尝试 " + state.attempts + " 次";
    }

    /* ---------------- 判定 ---------------- */
    function compute() {
      const inputs = state.fields.map(f => readValue(f.key));
      const expecteds = state.fields.map(f => f.expected);

      if (mode === "temperature") {
        const j = judge(inputs, expecteds, TOLERANCE_TEMP);
        const c = targetCelsius();
        return Object.assign({ mode, target_c: round1(c), expected_f: toFahrenheit(c), input_f: round1(inputs[0]) }, j);
      }
      if (mode === "time") {
        const j = judge(inputs, expecteds, TOLERANCE);
        let sum = 0;
        inputs.forEach(v => { sum += v; });
        const segments = state.fields.map((f, i) => ({ name: f.label, ratio: round1(f.expected / (num(cfg.total_minutes, 60) || 1)), expected: f.expected, input: round1(inputs[i]) }));
        return Object.assign({ mode, total_minutes: num(cfg.total_minutes, 60), sum: round1(sum), segments }, j);
      }
      if (mode === "free") {
        const items = recipeItems();
        return { mode, hit: items.length >= 1, ratio: items.length >= 1 ? 100 : 0, items: items.length };
      }
      if (mode === "doubling") {
        const j = judge(inputs, expecteds, TOLERANCE);
        const fields = state.fields.map((f, i) => ({ name: f.label, amount: f.ref, expected: f.expected, input: round1(inputs[i]) }));
        return Object.assign({ mode, factor: num(cfg.factor, 2), fields }, j);
      }
      if (mode === "party_plan") {
        const j = judge(inputs, expecteds, TOLERANCE);
        const fields = state.fields.map((f, i) => ({ name: f.label, amount: f.ref, expected: f.expected, input: round1(inputs[i]) }));
        return Object.assign({ mode, target_people: num(cfg.target_people, 8), fields }, j);
      }
      // recipe_scale
      const j = judge(inputs, expecteds, TOLERANCE);
      const fields = state.fields.map((f, i) => ({ name: f.label, amount: f.ref, expected: f.expected, input: round1(inputs[i]) }));
      return Object.assign({
        mode, factor: round1(num(cfg.to_servings, 5) / num(cfg.from_servings, 3)),
        from_servings: num(cfg.from_servings, 3), to_servings: num(cfg.to_servings, 5), fields,
      }, j);
    }

    function recipeItems() {
      const items = [];
      DEFAULT_INGREDIENTS.forEach((ing, i) => {
        const v = num(state.values["free_" + i], 0);
        if (v > 0) items.push({ name: ing.name, emoji: ing.emoji, unit: ing.unit, amount: round1(v) });
      });
      return items;
    }

    function submitAnswer() {
      state.attempts += 1;
      const result = compute();
      result.attempts = state.attempts;
      state.hitResult = { hit: result.hit };
      updateStatus();
      updateHUD();
      if (hitCallback) hitCallback(result);
    }

    function saveRecipe() {
      const items = recipeItems();
      if (items.length < 1) {
        if (typeof toast === "function") toast("先给至少一种材料填好用量吧～", 2400);
        return;
      }
      const nameInput = els.name;
      const name = (nameInput && String(nameInput.value).trim()) || "我的配方";
      const creations = readCreations();
      creations.push({
        name: String(name),
        date: new Date().toISOString(),
        ingredients: items,
        stats: { ingredients: items.length, total: Math.round(items.reduce((s, it) => s + num(it.amount, 0), 0)) },
      });
      writeCreations(creations);

      state.attempts += 1;
      const result = { hit: true, ratio: 100, attempts: state.attempts, mode: "free", name: String(name), ingredients: items };
      state.hitResult = { hit: true };
      updateStatus();
      updateHUD();
      if (typeof toast === "function") toast("配方已保存！共 " + creations.length + " 个作品 🎂", 2800);
      if (hitCallback) hitCallback(result);
    }

    function reset() {
      state.attempts = 0;
      state.hitResult = null;
      state.fields.forEach(f => { state.values[f.key] = 0; });
      if (els.name) els.name.value = "";
      syncAll();
      updateStatus();
      updateHUD();
    }

    /* ---------------- 对外 API ---------------- */
    const inst = {
      render,
      reset,
      submit: () => (mode === "free" ? saveRecipe() : submitAnswer()),
      getState() {
        return { mode, attempts: state.attempts, hitResult: state.hitResult, config: cfg };
      },
      onHit(cb) { hitCallback = typeof cb === "function" ? cb : null; },
      onHelp(cb) { helpCallback = typeof cb === "function" ? cb : null; },
      getCreations() { return readCreations(); },
      destroy() {
        containerEl.classList.remove("bake-sim");
        containerEl.innerHTML = "";
      },
    };

    return inst;
  }

  window.BakingSimulator = {
    createSimulator,
    DEFAULT_INGREDIENTS,
    readCreations,
    toFahrenheit,
    toCelsius,
    judge,
  };
})();
