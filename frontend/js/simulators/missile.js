/* V3.0 P2 · 模块 F「导弹发射弧线」前端模拟器 (simulators/missile.js)
 * 规格 8.3 技术设计 / 8.4 通关条件
 * - MissileSimulator：Canvas 2D 物理模拟器（平抛/斜抛 + 恒定水平风 + 匀速移动靶）
 * - 暴露 window.MissileSimulator.createSimulator(containerEl, config) 供 pbl-missile.js 挂载
 * - 纯原生 JS（无 p5/three），requestAnimationFrame 循环 ≥30fps
 * 依赖（可选）：app.js 的 escapeHtml()（缺失时本地降级）
 */

(function () {
  "use strict";

  // ---- 世界/物理常量（规格 8.3）----
  const WORLD_W = 180;         // 世界宽（米）
  const WORLD_H = 150;         // 世界高（米）
  const G = 9.8;               // 重力加速度
  const DT = 0.05;             // 轨迹步进（秒）
  const TARGET_HALF = 5;       // 命中判定：落点与靶心水平距离 ≤ 5m
  const PAD_X = 10;            // 发射台世界 X（米）
  const CUSTOM_LEVEL_KEY = "xy_missile_custom_levels";

  const DEFAULT_CONFIG = {
    angle_range: [0, 90],
    power_range: [0, 100],
    wind: false,
    wind_range: [-20, 20],
    target_moving: false,
    target_speed: 0,
    target_distance: 100,
    show_trajectory: true,
    help_button: false,
    editor: false,
    launch_height: 0,          // 平抛（Lv.1）的初始高度；斜抛为 0
  };

  const esc = (typeof escapeHtml === "function") ? escapeHtml
    : (s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }

  /* 斜抛/平抛轨迹（规格 8.3 精确实现：v0=power*0.5, g=9.8, ax=windSpeed*windDirection*0.1）
   * launchHeight 为平抛初始高度（默认 0，此时即 8.3 公式原式）；x0 为发射点世界 X */
  function calculateTrajectory(angle, power, windSpeed, windDirection, launchHeight, x0) {
    const v0 = power * 0.5;
    const rad = angle * Math.PI / 180;
    const vx = v0 * Math.cos(rad);
    const vy = v0 * Math.sin(rad);
    const ax = windSpeed * windDirection * 0.1;
    const points = [];
    let t = 0;
    while (true) {
      const x = (x0 || 0) + vx * t + 0.5 * ax * t * t;
      const y = (launchHeight || 0) + vy * t - 0.5 * G * t * t;
      points.push({ x, y });
      if (y < 0) break;
      t += DT;
      if (t > 30) break;       // 安全上限
    }
    return points;
  }

  function readCustomLevels() {
    try {
      const raw = localStorage.getItem(CUSTOM_LEVEL_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (_) { return []; }
  }
  function writeCustomLevels(levels) {
    try { localStorage.setItem(CUSTOM_LEVEL_KEY, JSON.stringify(levels)); } catch (_) { /* 存储满则忽略 */ }
  }
  function persistCustomLevel(levelConfig) {
    const levels = readCustomLevels();
    levels.push(levelConfig || {});
    writeCustomLevels(levels);
    return levels;
  }

  /* ---------------------------------------------------------------- 模拟器实例 */
  function createSimulator(containerEl, config) {
    if (!containerEl) throw new Error("MissileSimulator: 缺少容器元素");

    const cfg = Object.assign({}, DEFAULT_CONFIG, config || {});
    const a0 = cfg.angle_range[0], a1 = cfg.angle_range[1];
    const angleFixed = a0 === a1;
    const defaultAngle = angleFixed ? a0 : clamp(45, a0, a1);
    const defaultPower = clamp(50, cfg.power_range[0], cfg.power_range[1]);

    const state = {
      angle: defaultAngle,
      power: defaultPower,
      windSpeed: 0,
      windDirection: 1,                       // 1=向右（顺风），-1=向左
      targetX: cfg.target_distance,
      targetY: 0,
      targetMoving: !!cfg.target_moving,
      targetSpeed: cfg.target_speed || 0,
      targetDir: 1,
      targetMin: clamp((cfg.target_distance || 100) - 25, 15, WORLD_W - 10),
      targetMax: clamp((cfg.target_distance || 100) + 25, 15, WORLD_W - 10),
      isFlying: false,
      trajectory: [],                          // 落地后的完整轨迹（绝对坐标）
      preview: null,                           // 待发射的预测轨迹
      trail: [],                               // 飞行中的尾迹点
      missile: null,                           // 当前导弹 {x,y}
      landing: null,                           // 落点 {x,y}
      hitResult: null,                         // {hit, distance}
      explosion: null,                         // {x,y,t}
      simTime: 0,
      launch: null,                            // 本次发射参数 {vx,vy,ax,launchHeight}
      attempts: 0,
    };

    let canvas, ctx, viewW = 800, viewH = 464, groundH, groundTop;
    let rafId = null, lastTime = 0, destroyed = false;
    let els = {};
    let hitCallback = null, helpCallback = null;

    /* ---------------- 坐标换算：世界(m) → 屏幕(px) ---------------- */
    function sx(wx) { return (wx / WORLD_W) * viewW; }
    function sy(wy) { return groundTop - (wy / WORLD_H) * groundTop; }

    function resize() {
      const w = containerEl.clientWidth || 800;
      const h = Math.max(240, Math.round(w * 0.58));
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      viewW = w; viewH = h;
      groundH = Math.round(h * 0.16);
      groundTop = h - groundH;
    }

    /* ---------------- DOM 构建 ---------------- */
    function render() {
      containerEl.classList.add("missile-sim");
      containerEl.innerHTML = `
        <div class="missile-canvas-wrap">
          <canvas class="missile-canvas"></canvas>
          <div class="missile-hit-flash"></div>
        </div>
        <div class="missile-hud">
          <span class="missile-attempts js-attempts">已尝试 0 次</span>
          <span class="missile-result js-result"></span>
        </div>
        <div class="missile-controls">
          ${angleFixed ? "" : `
          <label class="missile-param">
            <span class="missile-param-name">角度</span>
            <input type="range" class="js-angle" min="${a0}" max="${a1}" step="1" value="${defaultAngle}">
            <span class="missile-param-val js-angle-val">${defaultAngle}°</span>
          </label>`}
          <label class="missile-param">
            <span class="missile-param-name">力度</span>
            <input type="range" class="js-power" min="${cfg.power_range[0]}" max="${cfg.power_range[1]}" step="1" value="${defaultPower}">
            <span class="missile-param-val js-power-val">${defaultPower}</span>
          </label>
          ${cfg.wind ? `
          <label class="missile-param">
            <span class="missile-param-name">风速</span>
            <input type="range" class="js-wind" min="${cfg.wind_range[0]}" max="${cfg.wind_range[1]}" step="1" value="0">
            <span class="missile-param-val js-wind-val">无风</span>
          </label>` : ""}
          <div class="missile-actions">
            <button class="missile-btn missile-btn-fire js-fire">🚀 发射</button>
            <button class="missile-btn js-reset">↺ 重置</button>
            ${cfg.help_button ? `<button class="missile-btn missile-btn-help js-help">🧮 计算辅助</button>` : ""}
            ${cfg.editor ? `<button class="missile-btn missile-btn-edit js-editor-toggle">🛠 关卡编辑器</button>` : ""}
          </div>
        </div>
        ${cfg.editor ? editorTemplate() : ""}
      `;

      canvas = containerEl.querySelector(".missile-canvas");
      ctx = canvas.getContext("2d");
      els = {
        angle: containerEl.querySelector(".js-angle"),
        angleVal: containerEl.querySelector(".js-angle-val"),
        power: containerEl.querySelector(".js-power"),
        powerVal: containerEl.querySelector(".js-power-val"),
        wind: containerEl.querySelector(".js-wind"),
        windVal: containerEl.querySelector(".js-wind-val"),
        fire: containerEl.querySelector(".js-fire"),
        reset: containerEl.querySelector(".js-reset"),
        help: containerEl.querySelector(".js-help"),
        editorToggle: containerEl.querySelector(".js-editor-toggle"),
        attempts: containerEl.querySelector(".js-attempts"),
        result: containerEl.querySelector(".js-result"),
        flash: containerEl.querySelector(".missile-hit-flash"),
      };

      wireEvents();
      resize();
      syncControls();
      updatePreview();
      updateHUD();
      lastTime = 0;
      rafId = requestAnimationFrame(loop);
      return inst;
    }

    function editorTemplate() {
      const custom = readCustomLevels();
      const list = custom.length
        ? custom.map((c, i) => `<div class="missile-level-item">
            <span class="missile-level-name">${esc(c.name || ("自定义关卡 " + (i + 1)))}</span>
            <span class="missile-level-meta">距离 ${c.target_distance}m${c.target_moving ? " · 移动靶" : ""}${c.wind ? " · 风速 " + c.wind_range[0] + "~" + c.wind_range[1] : ""}</span>
            <button class="missile-btn js-level-load" data-idx="${i}">载入</button>
          </div>`).join("")
        : `<div class="missile-level-empty">还没有保存的关卡，先设计一个吧～</div>`;
      return `
        <div class="missile-editor js-editor" hidden>
          <div class="missile-editor-title">🛠 自定义关卡编辑器</div>
          <div class="missile-editor-grid">
            <label class="missile-editor-field">靶子距离(米)
              <input type="number" class="js-ed-target" min="20" max="170" step="5" value="${cfg.target_distance}">
            </label>
            <label class="missile-editor-field">风速范围(±)
              <input type="number" class="js-ed-wind" min="0" max="20" step="1" value="${Math.abs(cfg.wind_range[1])}">
            </label>
            <label class="missile-editor-field">移动速度(米/秒, 0=静止)
              <input type="number" class="js-ed-speed" min="0" max="20" step="1" value="${cfg.target_speed || 0}">
            </label>
            <label class="missile-editor-check">
              <input type="checkbox" class="js-ed-moving" ${cfg.target_moving ? "checked" : ""}> 移动靶
            </label>
          </div>
          <div class="missile-editor-actions">
            <button class="missile-btn missile-btn-fire js-ed-apply">应用预览</button>
            <button class="missile-btn missile-btn-help js-ed-save">保存自定义关卡</button>
          </div>
          <div class="missile-editor-title missile-editor-subtitle">已保存关卡</div>
          <div class="missile-level-list js-ed-list">${list}</div>
        </div>`;
    }

    function wireEvents() {
      if (els.angle) els.angle.addEventListener("input", onControlInput);
      if (els.power) els.power.addEventListener("input", onControlInput);
      if (els.wind) els.wind.addEventListener("input", onControlInput);
      if (els.fire) els.fire.onclick = () => fire();
      if (els.reset) els.reset.onclick = () => reset();
      if (els.help) els.help.onclick = () => { if (helpCallback) helpCallback(); };
      if (els.editorToggle) els.editorToggle.onclick = () => {
        const ed = containerEl.querySelector(".js-editor");
        if (ed) ed.hidden = !ed.hidden;
      };

      const edApply = containerEl.querySelector(".js-ed-apply");
      const edSave = containerEl.querySelector(".js-ed-save");
      if (edApply) edApply.onclick = applyEditor;
      if (edSave) edSave.onclick = saveEditorLevel;
      const edList = containerEl.querySelector(".js-ed-list");
      if (edList) edList.addEventListener("click", e => {
        const btn = e.target.closest(".js-level-load");
        if (!btn) return;
        loadCustomLevel(Number(btn.dataset.idx));
      });

      window.addEventListener("resize", resize);
      if (typeof ResizeObserver !== "undefined") {
        const ro = new ResizeObserver(() => resize());
        ro.observe(containerEl);
        inst._ro = ro;
      }
    }

    function onControlInput() {
      if (els.angle) state.angle = Number(els.angle.value);
      if (els.power) state.power = Number(els.power.value);
      if (els.wind) state.windSpeed = Number(els.wind.value);
      syncControls();
      if (!state.isFlying) updatePreview();
    }

    function syncControls() {
      if (els.angle) els.angle.value = state.angle;
      if (els.angleVal) els.angleVal.textContent = state.angle + "°";
      if (els.power) els.power.value = state.power;
      if (els.powerVal) els.powerVal.textContent = state.power;
      if (els.wind) els.wind.value = state.windSpeed;
      if (els.windVal) {
        els.windVal.textContent = state.windSpeed === 0 ? "无风"
          : (state.windSpeed > 0 ? "顺风 +" + state.windSpeed : "逆风 " + state.windSpeed) + " m/s";
      }
    }

    function updateHUD() {
      if (els.attempts) els.attempts.textContent = "已尝试 " + state.attempts + " 次";
      if (els.result) {
        if (state.hitResult) {
          els.result.textContent = state.hitResult.hit
            ? "🎯 命中！偏离靶心 " + state.hitResult.distance.toFixed(1) + " 米"
            : "未命中，偏差 " + state.hitResult.distance.toFixed(1) + " 米";
        } else if (state.isFlying) {
          els.result.textContent = "导弹飞行中…";
        } else {
          els.result.textContent = "";
        }
      }
    }

    function updatePreview() {
      state.preview = calculateTrajectory(state.angle, state.power, state.windSpeed,
        state.windDirection, cfg.launch_height, PAD_X);
    }

    /* ---------------- 发射 / 命中 / 重置 ---------------- */
    function fire() {
      if (state.isFlying || destroyed) return;
      state.attempts += 1;
      state.simTime = 0;
      state.isFlying = true;
      state.trajectory = [];
      state.trail = [];
      state.missile = { x: PAD_X, y: cfg.launch_height };
      state.landing = null;
      state.hitResult = null;
      state.explosion = null;

      const rad = state.angle * Math.PI / 180;
      const v0 = state.power * 0.5;
      state.launch = {
        vx: v0 * Math.cos(rad),
        vy: v0 * Math.sin(rad),
        ax: state.windSpeed * state.windDirection * 0.1,
        launchHeight: cfg.launch_height,
      };
      updateHUD();
    }

    function landMissile() {
      state.isFlying = false;
      const landX = state.missile.x;
      state.landing = { x: landX, y: 0 };
      state.trajectory = calculateTrajectory(state.angle, state.power, state.windSpeed,
        state.windDirection, cfg.launch_height, PAD_X);
      const distance = Math.abs(landX - state.targetX);
      const hit = distance <= TARGET_HALF;
      state.hitResult = { hit, distance };
      if (hit) {
        state.explosion = { x: landX, y: 0, t: 0 };
        if (els.flash) {
          els.flash.classList.remove("active");
          void els.flash.offsetWidth;
          els.flash.classList.add("active");
        }
      }
      updateHUD();
      if (hitCallback) {
        hitCallback({
          hit, distance, landX, targetX: state.targetX,
          attempts: state.attempts, angle: state.angle, power: state.power, windSpeed: state.windSpeed,
        });
      }
    }

    function reset() {
      state.angle = defaultAngle;
      state.power = defaultPower;
      state.windSpeed = 0;
      state.targetX = cfg.target_distance;
      state.targetDir = 1;
      state.isFlying = false;
      state.trajectory = [];
      state.preview = null;
      state.trail = [];
      state.missile = null;
      state.landing = null;
      state.hitResult = null;
      state.explosion = null;
      state.attempts = 0;
      syncControls();
      updatePreview();
      updateHUD();
    }

    /* ---------------- 编辑器（Lv.6） ---------------- */
    function applyEditor() {
      const elTarget = containerEl.querySelector(".js-ed-target");
      const elWind = containerEl.querySelector(".js-ed-wind");
      const elSpeed = containerEl.querySelector(".js-ed-speed");
      const elMoving = containerEl.querySelector(".js-ed-moving");
      if (!elTarget) return;

      const dist = clamp(Number(elTarget.value) || 100, 20, 170);
      const windMag = clamp(Number(elWind.value) || 0, 0, 20);
      const speed = clamp(Number(elSpeed.value) || 0, 0, 20);
      const moving = elMoving.checked;

      cfg.target_distance = dist;
      cfg.target_moving = moving;
      cfg.target_speed = speed;
      cfg.wind_range = [-windMag, windMag];
      state.targetX = dist;
      state.targetMoving = moving;
      state.targetSpeed = speed;
      state.targetDir = 1;
      state.targetMin = clamp(dist - 25, 15, WORLD_W - 10);
      state.targetMax = clamp(dist + 25, 15, WORLD_W - 10);
      state.windSpeed = 0;

      // 同步风速滑块范围
      if (els.wind) { els.wind.min = -windMag; els.wind.max = windMag; }
      syncControls();
      reset();
    }

    function saveEditorLevel() {
      const elTarget = containerEl.querySelector(".js-ed-target");
      const elWind = containerEl.querySelector(".js-ed-wind");
      const elSpeed = containerEl.querySelector(".js-ed-speed");
      const elMoving = containerEl.querySelector(".js-ed-moving");
      const dist = clamp(Number(elTarget.value) || 100, 20, 170);
      const windMag = clamp(Number(elWind.value) || 0, 0, 20);
      const speed = clamp(Number(elSpeed.value) || 0, 0, 20);
      const moving = elMoving ? elMoving.checked : false;
      persistCustomLevel({
        name: "自定义关卡 " + (readCustomLevels().length + 1),
        target_distance: dist,
        wind: windMag > 0,
        wind_range: [-windMag, windMag],
        target_moving: moving,
        target_speed: speed,
      });
      const list = containerEl.querySelector(".js-ed-list");
      if (list) list.innerHTML = renderLevelList();
    }

    function renderLevelList() {
      const custom = readCustomLevels();
      if (!custom.length) return `<div class="missile-level-empty">还没有保存的关卡，先设计一个吧～</div>`;
      return custom.map((c, i) => `<div class="missile-level-item">
        <span class="missile-level-name">${esc(c.name || ("自定义关卡 " + (i + 1)))}</span>
        <span class="missile-level-meta">距离 ${c.target_distance}m${c.target_moving ? " · 移动靶" : ""}${c.wind ? " · 风速 ±" + Math.abs(c.wind_range[1]) : ""}</span>
        <button class="missile-btn js-level-load" data-idx="${i}">载入</button>
      </div>`).join("");
    }

    function loadCustomLevel(idx) {
      const levels = readCustomLevels();
      const c = levels[idx];
      if (!c) return;
      applyEditorValues(c);
      const ed = containerEl.querySelector(".js-editor");
      if (ed) ed.hidden = true;
    }

    function applyEditorValues(c) {
      cfg.target_distance = c.target_distance;
      cfg.target_moving = !!c.target_moving;
      cfg.target_speed = c.target_speed || 0;
      cfg.wind_range = c.wind_range || [-0, 0];
      state.targetX = c.target_distance;
      state.targetMoving = !!c.target_moving;
      state.targetSpeed = c.target_speed || 0;
      state.targetDir = 1;
      state.targetMin = clamp(c.target_distance - 25, 15, WORLD_W - 10);
      state.targetMax = clamp(c.target_distance + 25, 15, WORLD_W - 10);
      state.windSpeed = 0;
      if (els.wind) { els.wind.min = cfg.wind_range[0]; els.wind.max = cfg.wind_range[1]; }
      syncControls();
      reset();
    }

    /* ---------------- 物理更新 ---------------- */
    function update(realDt) {
      if (state.targetMoving && state.targetSpeed > 0) {
        state.targetX += state.targetDir * state.targetSpeed * realDt;
        if (state.targetX > state.targetMax) { state.targetX = state.targetMax; state.targetDir = -1; }
        else if (state.targetX < state.targetMin) { state.targetX = state.targetMin; state.targetDir = 1; }
      }
      if (state.isFlying) {
        state.simTime += realDt;
        const L = state.launch;
        const t = state.simTime;
        const x = PAD_X + L.vx * t + 0.5 * L.ax * t * t;
        const y = L.launchHeight + L.vy * t - 0.5 * G * t * t;
        state.missile = { x, y };
        state.trail.push({ x, y });
        if (state.trail.length > 48) state.trail.shift();
        if (y < 0 && t > 0.05) landMissile();
      }
      if (state.explosion) {
        state.explosion.t += realDt;
        if (state.explosion.t > 0.8) state.explosion = null;
      }
    }

    /* ---------------- 渲染 ---------------- */
    function loop(now) {
      if (destroyed) return;
      const realDt = lastTime ? Math.min(0.05, (now - lastTime) / 1000) : 0.016;
      lastTime = now;
      update(realDt);
      draw();
      rafId = requestAnimationFrame(loop);
    }

    function draw() {
      ctx.clearRect(0, 0, viewW, viewH);
      drawSky();
      drawGround();

      if (cfg.show_trajectory) {
        if (state.trajectory.length) {
          drawTrajectory(state.trajectory, "#7ca26c", 0.9);
        } else if (!state.isFlying && state.preview && state.preview.length > 1) {
          drawTrajectory(state.preview, "#97a78d", 0.65);
        }
      }

      drawLaunchPad();
      drawTarget();
      if (state.landing) drawLandingMarker();
      drawMissile();
      drawExplosion();
    }

    function drawSky() {
      const g = ctx.createLinearGradient(0, 0, 0, groundTop);
      g.addColorStop(0, "#a7d8ff");
      g.addColorStop(1, "#eaf6ff");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, viewW, groundTop);
      // 太阳
      ctx.fillStyle = "rgba(255, 230, 150, 0.9)";
      ctx.beginPath();
      ctx.arc(viewW * 0.82, groundTop * 0.16, Math.max(10, viewW * 0.025), 0, Math.PI * 2);
      ctx.fill();
    }

    function drawGround() {
      const g = ctx.createLinearGradient(0, groundTop, 0, viewH);
      g.addColorStop(0, "#b5dda8");
      g.addColorStop(1, "#8fc77f");
      ctx.fillStyle = g;
      ctx.fillRect(0, groundTop, viewW, groundH);
      ctx.strokeStyle = "rgba(0,0,0,0.15)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, groundTop);
      ctx.lineTo(viewW, groundTop);
      ctx.stroke();
    }

    function drawTrajectory(points, color, alpha) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      points.forEach((p, i) => {
        const X = sx(p.x), Y = sy(p.y);
        if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }

    function drawLaunchPad() {
      const px = sx(PAD_X);
      const baseY = sy(0);
      // 底座
      ctx.fillStyle = "#7a7a7a";
      ctx.fillRect(px - 10, baseY - 10, 22, 10);
      // 高台（平抛时）
      if (cfg.launch_height > 0) {
        const topY = sy(cfg.launch_height);
        ctx.strokeStyle = "#8a8a8a";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(px, baseY);
        ctx.lineTo(px, topY);
        ctx.stroke();
      }
      // 炮管（指向当前角度）
      const muzzleY = sy(cfg.launch_height);
      const rad = state.angle * Math.PI / 180;
      const barrel = 12; // 米
      const endX = sx(PAD_X + barrel * Math.cos(rad));
      const endY = sy(cfg.launch_height + barrel * Math.sin(rad));
      ctx.strokeStyle = "#5b6b7a";
      ctx.lineWidth = 7;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(px, muzzleY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
      // 炮口
      ctx.fillStyle = "#3a4a58";
      ctx.beginPath();
      ctx.arc(px, muzzleY, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    function drawTarget() {
      const cx = sx(state.targetX);
      const baseY = sy(0);
      const topY = sy(8); // 靶板中心高 8m
      // 支架
      ctx.strokeStyle = "#8a6a4a";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx, baseY);
      ctx.lineTo(cx, topY);
      ctx.stroke();
      // 靶环（同心圆）
      const r = Math.max(8, sx(TARGET_HALF) * 0.9);
      const rings = [
        { frac: 1.0, color: "#e14b4b" },
        { frac: 0.66, color: "#f7f7f7" },
        { frac: 0.33, color: "#e14b4b" },
      ];
      rings.forEach(ring => {
        ctx.fillStyle = ring.color;
        ctx.beginPath();
        ctx.arc(cx, topY, r * ring.frac, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.strokeStyle = "rgba(0,0,0,0.25)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, topY, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    function drawLandingMarker() {
      const cx = sx(state.landing.x);
      const baseY = sy(0);
      ctx.strokeStyle = "#c0392b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(cx - 6, baseY - 6); ctx.lineTo(cx + 6, baseY + 6);
      ctx.moveTo(cx + 6, baseY - 6); ctx.lineTo(cx - 6, baseY + 6);
      ctx.stroke();
    }

    function drawMissile() {
      // 尾迹
      if (state.trail.length > 1) {
        for (let i = 0; i < state.trail.length; i++) {
          const p = state.trail[i];
          const a = (i + 1) / state.trail.length;
          ctx.fillStyle = "rgba(255, 150, 60, " + (a * 0.5) + ")";
          ctx.beginPath();
          ctx.arc(sx(p.x), sy(p.y), 2 + a * 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      // 导弹本体
      if (state.missile) {
        const X = sx(state.missile.x), Y = sy(state.missile.y);
        ctx.fillStyle = "#e8643c";
        ctx.beginPath();
        ctx.arc(X, Y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(X, Y, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawExplosion() {
      if (!state.explosion) return;
      const e = state.explosion;
      const progress = clamp(e.t / 0.8, 0, 1);
      const X = sx(e.x), Y = sy(e.y);
      const radius = 8 + progress * 34;
      ctx.save();
      ctx.globalAlpha = 1 - progress;
      // 外圈火焰
      const g = ctx.createRadialGradient(X, Y, 1, X, Y, radius);
      g.addColorStop(0, "rgba(255, 255, 210, 0.95)");
      g.addColorStop(0.5, "rgba(255, 150, 60, 0.8)");
      g.addColorStop(1, "rgba(230, 80, 40, 0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(X, Y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    /* ---------------- 对外 API ---------------- */
    const inst = {
      render,
      fire,
      reset,
      getState() {
        return {
          angle: state.angle,
          power: state.power,
          windSpeed: state.windSpeed,
          windDirection: state.windDirection,
          targetX: state.targetX,
          targetY: state.targetY,
          targetMoving: state.targetMoving,
          targetSpeed: state.targetSpeed,
          isFlying: state.isFlying,
          attempts: state.attempts,
          hitResult: state.hitResult ? Object.assign({}, state.hitResult) : null,
          trajectoryLength: state.trajectory.length,
        };
      },
      onHit(cb) { hitCallback = typeof cb === "function" ? cb : null; },
      onHelp(cb) { helpCallback = typeof cb === "function" ? cb : null; },
      getCustomLevels() { return readCustomLevels(); },
      saveCustomLevel(levelConfig) {
        return persistCustomLevel(levelConfig);
      },
      destroy() {
        destroyed = true;
        if (rafId) cancelAnimationFrame(rafId);
        window.removeEventListener("resize", resize);
        if (inst._ro) { inst._ro.disconnect(); inst._ro = null; }
        containerEl.classList.remove("missile-sim");
        containerEl.innerHTML = "";
      },
    };

    return inst;
  }

  window.MissileSimulator = {
    createSimulator,
    calculateTrajectory,
    WORLD_W, WORLD_H, G, DT, TARGET_HALF,
  };
})();
