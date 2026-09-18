/* V3.0 P2 · 模块「🧱 我的世界建筑」前端模拟器 (simulators/building.js)
 * - BuildingSimulator：Canvas 2D 网格建筑模拟器（6 种模式）
 *   length 城墙 / area 地砖 / coordinate 坐标系 / scale 缩放 / volume 立体仓库 / creator 自由创造
 * - 暴露 window.BuildingSimulator.createSimulator(containerEl, config) 供 pbl-building.js 挂载
 * - 纯原生 JS，静态重绘 + 响应式（容器宽度变化重绘），世界用网格坐标系，格数由 config 决定
 * 依赖（可选）：app.js 的 escapeHtml()（缺失时本地降级）
 */

(function () {
  "use strict";

  const CREATIONS_KEY = "xy_building_creations";

  const esc = (typeof escapeHtml === "function") ? escapeHtml
    : (s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }
  function num(v, d) { const n = Number(v); return isFinite(n) ? n : d; }

  function hexToRgb(hex) {
    const h = String(hex).replace("#", "");
    const v = parseInt(h, 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }
  function lighten(hex, amt) {
    const c = hexToRgb(hex);
    return "rgb(" + Math.round(c[0] + (255 - c[0]) * amt) + "," +
      Math.round(c[1] + (255 - c[1]) * amt) + "," +
      Math.round(c[2] + (255 - c[2]) * amt) + ")";
  }

  /* 颜色名 → 十六进制 / 中文名（坐标模式与创作者色板共用） */
  const COLOR_HEX = { red: "#e8594f", blue: "#4b8be1", green: "#43b97f", yellow: "#f0b542", purple: "#9b6be1", orange: "#ef8a3c" };
  const COLOR_ZH = { red: "红", blue: "蓝", green: "绿", yellow: "黄", purple: "紫", orange: "橙" };
  const PALETTE = ["#e8594f", "#4b8be1", "#43b97f", "#f0b542", "#9b6be1"];

  const DEFAULT_CONFIG = {
    mode: "creator",
    grid_cols: 10,
    grid_rows: 8,
    help_button: false,
    // length
    target_length: 12,
    // area
    room_w: 6, room_h: 4, target_area: 24,
    // coordinate
    axis_range: [-5, 5], targets: [],
    // scale
    design_w: 3, design_h: 2, scale: 2, scale_label: "1:2", target_w: 6, target_h: 4,
    // volume
    target_volume: 30, length_range: [1, 8], width_range: [1, 8], height_range: [1, 8],
    // creator
    max_height: 6,
  };

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

  /* ---------------------------------------------------------------- 模拟器实例 */
  function createSimulator(containerEl, config) {
    if (!containerEl) throw new Error("BuildingSimulator: 缺少容器元素");

    const cfg = Object.assign({}, DEFAULT_CONFIG, config || {});
    const mode = cfg.mode || "creator";
    const gridCols = () => Math.max(2, Math.round(num(cfg.grid_cols, 10)));
    const gridRows = () => Math.max(1, Math.round(num(cfg.grid_rows, 8)));

    const state = {
      attempts: 0,
      hitResult: null,
      hover: null,
      // length
      bricks: [],               // 布尔数组（第 0 行）
      // area
      tiles: {},                // "c,r" -> true
      outOfBounds: 0,
      // coordinate
      coord: {},                // "c,r" -> colorHex
      selectedColor: null,
      // scale
      selW: 0, selH: 0,
      // volume
      len: 0, wid: 0, hei: 0,
      // creator
      grid: [],                 // rows×cols {h,color}
      paintColor: PALETTE[0],
    };

    let canvas, ctx, viewW = 600, viewH = 300;
    let cell = 32, originX = 12, originY = 12, stackH = 12;
    let els = {};
    let hitCallback = null, helpCallback = null;
    let clickTimer = null;

    /* ---------------- 网格 → 屏幕换算 ---------------- */
    function colX(col) { return originX + col * cell; }
    function rowY(row) { return originY + row * cell; }

    function layout() {
      const w = containerEl.clientWidth || 560;
      const cols = gridCols(), rows = gridRows();
      let leftPad = 12, topPad = 12, rightPad = 12, bottomPad = 12;

      if (mode === "coordinate") { leftPad = 30; topPad = 26; bottomPad = 20; rightPad = 16; }

      if (mode === "scale") {
        const designCell = Math.max(8, Math.round(32 * 0.75));
        const panelW = num(cfg.design_w, 3) * designCell + 34;
        const availW = Math.max(120, w - panelW - 16);
        cell = clamp(Math.floor(availW / cols), 10, 38);
        originX = panelW + 10;
        originY = topPad;
        viewW = w;
        viewH = Math.max(topPad + cell * rows + bottomPad, num(cfg.design_h, 2) * designCell + 44);
        return;
      }

      const availW = w - leftPad - rightPad;
      cell = clamp(Math.floor(availW / cols), 12, 40);
      const gridW = cell * cols;
      const gridH = cell * rows;
      originX = leftPad + Math.floor((availW - gridW) / 2);
      originY = topPad;

      let topExtra = 0;
      if (mode === "creator") {
        stackH = Math.max(6, Math.round(cell * 0.4));
        topExtra = num(cfg.max_height, 6) * stackH + 6;
        originY = topPad + topExtra;
      }

      viewW = w;
      viewH = originY + gridH + bottomPad;
    }

    function resize() {
      layout();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(viewW * dpr);
      canvas.height = Math.round(viewH * dpr);
      canvas.style.width = viewW + "px";
      canvas.style.height = viewH + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    function eventToCell(e) {
      const rect = canvas.getBoundingClientRect();
      const px = (e.clientX - rect.left) * (viewW / (rect.width || viewW));
      const py = (e.clientY - rect.top) * (viewH / (rect.height || viewH));
      const col = Math.floor((px - originX) / cell);
      const row = Math.floor((py - originY) / cell);
      return { col, row };
    }
    function inGrid(col, row) {
      return col >= 0 && col < gridCols() && row >= 0 && row < gridRows();
    }

    /* ---------------- 状态初始化 ---------------- */
    function initState() {
      state.attempts = 0;
      state.hitResult = null;
      state.hover = null;
      state.outOfBounds = 0;
      if (mode === "length") {
        state.bricks = new Array(gridCols()).fill(false);
      } else if (mode === "area") {
        state.tiles = {};
      } else if (mode === "coordinate") {
        state.coord = {};
        const t = cfg.targets && cfg.targets.length ? cfg.targets[0] : null;
        state.selectedColor = t ? COLOR_HEX[t.color] : PALETTE[0];
      } else if (mode === "scale") {
        state.selW = clamp(num(cfg.design_w, 3), 1, gridCols());
        state.selH = clamp(num(cfg.design_h, 2), 1, gridRows());
      } else if (mode === "volume") {
        state.len = clamp(Math.round((cfg.length_range[0] + cfg.length_range[1]) / 2), cfg.length_range[0], cfg.length_range[1]);
        state.wid = clamp(Math.round((cfg.width_range[0] + cfg.width_range[1]) / 2), cfg.width_range[0], cfg.width_range[1]);
        state.hei = clamp(Math.round((cfg.height_range[0] + cfg.height_range[1]) / 2), cfg.height_range[0], cfg.height_range[1]);
      } else if (mode === "creator") {
        state.grid = [];
        for (let r = 0; r < gridRows(); r++) {
          const rowArr = [];
          for (let c = 0; c < gridCols(); c++) rowArr.push({ h: 0, color: null });
          state.grid.push(rowArr);
        }
      }
    }

    /* ---------------- DOM 构建 ---------------- */
    function toolbarHTML() {
      const helpBtn = cfg.help_button ? `<button class="bld-btn bld-btn-help js-help">🧮 计算辅助</button>` : "";
      if (mode === "length") {
        return `<div class="bld-toolbar">
          <div class="bld-hint">点击第一行格子，从左往右连续铺砖</div>
          <div class="bld-actions">
            <button class="bld-btn bld-btn-submit js-submit">🏗 提交建造</button>
            <button class="bld-btn js-reset">↺ 重置</button>
            ${helpBtn}
          </div>
        </div>`;
      }
      if (mode === "area") {
        return `<div class="bld-toolbar">
          <div class="bld-hint">点击房间（左上高亮区）内的格子铺地砖</div>
          <div class="bld-actions">
            <button class="bld-btn bld-btn-submit js-submit">🏗 提交建造</button>
            <button class="bld-btn js-reset">↺ 重置</button>
            ${helpBtn}
          </div>
        </div>`;
      }
      if (mode === "coordinate") {
        const targets = (cfg.targets || []);
        const list = targets.map(t => {
          const hex = COLOR_HEX[t.color] || PALETTE[0];
          return `<div class="bld-target js-target" data-color="${esc(t.color)}">
            <span class="bld-dot" style="background:${hex}"></span>
            <span>在 (${esc(t.x)}, ${esc(t.y)}) 放${esc(COLOR_ZH[t.color] || t.color)}色方块</span>
          </div>`;
        }).join("");
        const colorBtns = targets.map(t => {
          const hex = COLOR_HEX[t.color] || PALETTE[0];
          return `<button class="bld-color-btn js-color" data-color="${esc(t.color)}" style="--c:${hex}" title="${esc(COLOR_ZH[t.color] || t.color)}"></button>`;
        }).join("");
        return `<div class="bld-targets"><div class="bld-targets-title">🎯 目标清单</div>${list}</div>
          <div class="bld-toolbar">
            <div class="bld-colorbar">${colorBtns}</div>
            <div class="bld-actions">
              <button class="bld-btn bld-btn-submit js-submit">🏗 提交建造</button>
              <button class="bld-btn js-reset">↺ 重置</button>
              ${helpBtn}
            </div>
          </div>`;
      }
      if (mode === "scale") {
        return `<div class="bld-toolbar">
          <div class="bld-steppers">
            <div class="bld-stepper"><span class="bld-step-name">宽度</span>
              <button class="bld-step-btn js-w-dec">−</button>
              <span class="bld-step-val js-w-val">${state.selW}</span>
              <button class="bld-step-btn js-w-inc">＋</button>
            </div>
            <div class="bld-stepper"><span class="bld-step-name">高度</span>
              <button class="bld-step-btn js-h-dec">−</button>
              <span class="bld-step-val js-h-val">${state.selH}</span>
              <button class="bld-step-btn js-h-inc">＋</button>
            </div>
          </div>
          <div class="bld-actions">
            <button class="bld-btn bld-btn-submit js-submit">🏗 提交建造</button>
            <button class="bld-btn js-reset">↺ 重置</button>
            ${helpBtn}
          </div>
        </div>`;
      }
      if (mode === "volume") {
        const lr = cfg.length_range, wr = cfg.width_range, hr = cfg.height_range;
        return `<div class="bld-toolbar bld-toolbar-col">
          <div class="bld-sliders">
            <label class="bld-slider"><span class="bld-slider-name">长</span>
              <input type="range" class="js-len" min="${lr[0]}" max="${lr[1]}" step="1" value="${state.len}">
              <span class="bld-slider-val js-len-v">${state.len}</span></label>
            <label class="bld-slider"><span class="bld-slider-name">宽</span>
              <input type="range" class="js-wid" min="${wr[0]}" max="${wr[1]}" step="1" value="${state.wid}">
              <span class="bld-slider-val js-wid-v">${state.wid}</span></label>
            <label class="bld-slider"><span class="bld-slider-name">高</span>
              <input type="range" class="js-hei" min="${hr[0]}" max="${hr[1]}" step="1" value="${state.hei}">
              <span class="bld-slider-val js-hei-v">${state.hei}</span></label>
          </div>
          <div class="bld-formula js-formula"></div>
          <div class="bld-actions">
            <button class="bld-btn bld-btn-submit js-submit">🏗 提交建造</button>
            <button class="bld-btn js-reset">↺ 重置</button>
            ${helpBtn}
          </div>
        </div>`;
      }
      // creator
      const colorBtns = PALETTE.map(c =>
        `<button class="bld-color-btn js-paint" data-hex="${c}" style="--c:${c}"></button>`).join("");
      return `<div class="bld-toolbar bld-toolbar-col">
        <div class="bld-colorbar">${colorBtns}<span class="bld-legend">选色</span></div>
        <div class="bld-hint">点击加高一层 · 右键 / 双击去掉一层</div>
        <div class="bld-actions">
          <button class="bld-btn bld-btn-submit js-save">💾 保存作品</button>
          <button class="bld-btn js-reset">↺ 重置</button>
          ${helpBtn}
        </div>
      </div>`;
    }

    function render() {
      initState();
      containerEl.classList.add("bld-sim");
      containerEl.innerHTML = `
        <div class="bld-canvas-wrap"><canvas class="bld-canvas"></canvas></div>
        <div class="bld-status">
          <span class="bld-attempts js-attempts">已尝试 0 次</span>
          <span class="bld-result js-status"></span>
        </div>
        ${toolbarHTML()}
      `;

      canvas = containerEl.querySelector(".bld-canvas");
      ctx = canvas.getContext("2d");
      els = {
        submit: containerEl.querySelector(".js-submit"),
        save: containerEl.querySelector(".js-save"),
        reset: containerEl.querySelector(".js-reset"),
        help: containerEl.querySelector(".js-help"),
        attempts: containerEl.querySelector(".js-attempts"),
        status: containerEl.querySelector(".js-status"),
        wDec: containerEl.querySelector(".js-w-dec"),
        wInc: containerEl.querySelector(".js-w-inc"),
        hDec: containerEl.querySelector(".js-h-dec"),
        hInc: containerEl.querySelector(".js-h-inc"),
        wVal: containerEl.querySelector(".js-w-val"),
        hVal: containerEl.querySelector(".js-h-val"),
        len: containerEl.querySelector(".js-len"),
        wid: containerEl.querySelector(".js-wid"),
        hei: containerEl.querySelector(".js-hei"),
        lenV: containerEl.querySelector(".js-len-v"),
        widV: containerEl.querySelector(".js-wid-v"),
        heiV: containerEl.querySelector(".js-hei-v"),
        formula: containerEl.querySelector(".js-formula"),
      };

      wireEvents();
      syncControls();
      updateStatus();
      updateHUD();
      resize();
      return inst;
    }

    function wireEvents() {
      const btn = els.submit || els.save;
      if (btn) btn.onclick = () => submit();
      if (els.reset) els.reset.onclick = () => reset();
      if (els.help) els.help.onclick = () => { if (helpCallback) helpCallback(); };

      if (els.wDec) els.wDec.onclick = () => stepScale("w", -1);
      if (els.wInc) els.wInc.onclick = () => stepScale("w", 1);
      if (els.hDec) els.hDec.onclick = () => stepScale("h", -1);
      if (els.hInc) els.hInc.onclick = () => stepScale("h", 1);

      if (els.len) els.len.addEventListener("input", onVolumeInput);
      if (els.wid) els.wid.addEventListener("input", onVolumeInput);
      if (els.hei) els.hei.addEventListener("input", onVolumeInput);

      // 颜色选择（坐标 / 创作）
      containerEl.querySelectorAll(".js-color").forEach(b => {
        b.onclick = () => { selectColor(COLOR_HEX[b.dataset.color] || b.dataset.color); };
      });
      containerEl.querySelectorAll(".js-target").forEach(t => {
        t.onclick = () => { selectColor(COLOR_HEX[t.dataset.color] || t.dataset.color); };
      });
      containerEl.querySelectorAll(".js-paint").forEach(b => {
        b.onclick = () => { state.paintColor = b.dataset.hex; refreshColorActive(); };
      });

      // 画布交互
      if (["length", "area", "coordinate", "creator"].indexOf(mode) >= 0) {
        canvas.addEventListener("click", onCanvasClick);
        canvas.addEventListener("mousemove", onCanvasMove);
        canvas.addEventListener("mouseleave", () => { state.hover = null; draw(); });
      }
      if (mode === "creator") {
        canvas.addEventListener("contextmenu", e => { e.preventDefault(); removeAt(eventToCell(e)); });
      }

      window.addEventListener("resize", resize);
      if (typeof ResizeObserver !== "undefined") {
        const ro = new ResizeObserver(() => resize());
        ro.observe(containerEl);
        inst._ro = ro;
      }
    }

    /* ---------------- 交互逻辑 ---------------- */
    function onCanvasClick(e) {
      const c = eventToCell(e);
      if (!inGrid(c.col, c.row)) return;
      if (mode === "length") {
        if (c.row !== 0) return;
        state.bricks[c.col] = !state.bricks[c.col];
      } else if (mode === "area") {
        const rw = num(cfg.room_w, 6), rh = num(cfg.room_h, 4);
        if (c.col < rw && c.row < rh) {
          const k = c.col + "_" + c.row;
          state.tiles[k] = !state.tiles[k];
        } else {
          state.outOfBounds += 1;
          if (typeof toast === "function") toast("这里不在房间里哦，去左上角高亮区铺砖吧～", 2600);
        }
      } else if (mode === "coordinate") {
        const k = c.col + "_" + c.row;
        if (state.coord[k] === state.selectedColor) delete state.coord[k];
        else state.coord[k] = state.selectedColor;
      } else if (mode === "creator") {
        if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; removeAt(c); }
        else { clickTimer = setTimeout(() => { clickTimer = null; addAt(c); }, 280); }
        return;
      }
      updateStatus();
      draw();
    }

    function onCanvasMove(e) {
      if (!["length", "area", "coordinate", "creator"].includes(mode)) return;
      const c = eventToCell(e);
      if (!inGrid(c.col, c.row)) { if (state.hover) { state.hover = null; draw(); } return; }
      if (!state.hover || state.hover.col !== c.col || state.hover.row !== c.row) {
        state.hover = { col: c.col, row: c.row };
        draw();
      }
    }

    function addAt(c) {
      if (!inGrid(c.col, c.row)) return;
      const v = state.grid[c.row][c.col];
      if (v.h >= num(cfg.max_height, 6)) { if (typeof toast === "function") toast("已经到最高啦，不能再加高了～", 2200); return; }
      v.h += 1;
      v.color = state.paintColor;
      updateStatus();
      draw();
    }
    function removeAt(c) {
      if (!inGrid(c.col, c.row)) return;
      const v = state.grid[c.row][c.col];
      if (v.h <= 0) return;
      v.h -= 1;
      if (v.h === 0) v.color = null;
      updateStatus();
      draw();
    }

    function selectColor(hex) {
      state.selectedColor = hex;
      refreshColorActive();
      draw();
    }
    function refreshColorActive() {
      containerEl.querySelectorAll(".js-color").forEach(b => {
        const h = COLOR_HEX[b.dataset.color] || b.dataset.color;
        b.classList.toggle("active", h === state.selectedColor);
      });
      containerEl.querySelectorAll(".js-target").forEach(t => {
        const h = COLOR_HEX[t.dataset.color] || t.dataset.color;
        t.classList.toggle("active", h === state.selectedColor);
      });
      containerEl.querySelectorAll(".js-paint").forEach(b => {
        b.classList.toggle("active", b.dataset.hex === state.paintColor);
      });
    }

    function stepScale(axis, d) {
      if (axis === "w") {
        state.selW = clamp(state.selW + d, 1, gridCols());
        if (els.wVal) els.wVal.textContent = state.selW;
      } else {
        state.selH = clamp(state.selH + d, 1, gridRows());
        if (els.hVal) els.hVal.textContent = state.selH;
      }
      updateStatus();
      draw();
    }

    function onVolumeInput() {
      state.len = Number(els.len.value);
      state.wid = Number(els.wid.value);
      state.hei = Number(els.hei.value);
      syncControls();
      updateStatus();
      draw();
    }

    function syncControls() {
      if (mode === "scale") {
        if (els.wVal) els.wVal.textContent = state.selW;
        if (els.hVal) els.hVal.textContent = state.selH;
      }
      if (mode === "volume") {
        if (els.len) els.len.value = state.len;
        if (els.wid) els.wid.value = state.wid;
        if (els.hei) els.hei.value = state.hei;
        if (els.lenV) els.lenV.textContent = state.len;
        if (els.widV) els.widV.textContent = state.wid;
        if (els.heiV) els.heiV.textContent = state.hei;
        if (els.formula) {
          const vol = state.len * state.wid * state.hei;
          els.formula.textContent = `${state.len} × ${state.wid} × ${state.hei} = ${vol}（目标体积 ${num(cfg.target_volume, 30)}）`;
        }
      }
      refreshColorActive();
    }

    /* ---------------- 进度 / 状态 / HUD ---------------- */
    function currentLength() {
      let k = 0;
      while (k < gridCols() && state.bricks[k]) k++;
      return k;
    }
    function tileCount() {
      return Object.keys(state.tiles).length;
    }
    function coordCorrect() {
      const targets = cfg.targets || [];
      let ok = 0;
      targets.forEach(t => {
        const xMin = num(cfg.axis_range[0], -5), xMax = num(cfg.axis_range[1], 5);
        const xStep = (xMax - xMin) / (gridCols() - 1);
        const yMax = (gridRows() - 1) / 2, yStep = (yMax - (-yMax)) / (gridRows() - 1);
        const col = Math.round((t.x - xMin) / xStep);
        const row = Math.round((yMax - t.y) / yStep);
        if (state.coord[col + "_" + row] === (COLOR_HEX[t.color] || t.color)) ok++;
      });
      return ok;
    }
    function creatorTotal() {
      let s = 0;
      for (let r = 0; r < state.grid.length; r++)
        for (let c = 0; c < state.grid[r].length; c++) s += state.grid[r][c].h;
      return s;
    }

    function updateStatus() {
      if (!els.status) return;
      let text = "";
      if (mode === "length") {
        const len = currentLength();
        text = `当前长度 ${len} 格 / 目标 ${num(cfg.target_length, 12)} 格`;
      } else if (mode === "area") {
        text = `已铺 ${tileCount()} 块 / 需要 ${num(cfg.target_area, 24)} 块`;
        if (state.outOfBounds > 0) text += ` · 越界提醒 ${state.outOfBounds} 次`;
      } else if (mode === "coordinate") {
        const ok = coordCorrect();
        text = `已命中 ${ok} / ${(cfg.targets || []).length} 个目标`;
        if (state.hover) {
          const xMin = num(cfg.axis_range[0], -5), xMax = num(cfg.axis_range[1], 5);
          const xStep = (xMax - xMin) / (gridCols() - 1);
          const yMax = (gridRows() - 1) / 2, yStep = (yMax - (-yMax)) / (gridRows() - 1);
          const x = Math.round((xMin + state.hover.col * xStep) * 10) / 10;
          const y = Math.round((yMax - state.hover.row * yStep) * 10) / 10;
          text += ` · 悬停 (${x}, ${y})`;
        }
      } else if (mode === "scale") {
        text = `你选的 ${state.selW}×${state.selH}，目标 ${num(cfg.target_w, 6)}×${num(cfg.target_h, 4)}`;
      } else if (mode === "volume") {
        const vol = state.len * state.wid * state.hei;
        text = `体积 ${vol}（目标 ${num(cfg.target_volume, 30)}）`;
      } else if (mode === "creator") {
        text = `方块总数 = 体积 ${creatorTotal()}`;
      }
      if (state.hitResult) {
        text = state.hitResult.hit ? "🎉 完成！" + text : "还差一点，" + text;
      }
      els.status.textContent = text;
    }

    function updateHUD() {
      if (els.attempts) els.attempts.textContent = "已尝试 " + state.attempts + " 次";
    }

    /* ---------------- 提交 / 判定 ---------------- */
    function compute() {
      if (mode === "length") {
        const len = currentLength();
        const target = num(cfg.target_length, 12);
        return {
          hit: len === target, ratio: clamp(len / target, 0, 1),
          mode: "length", length: len, target_length: target, distance: Math.abs(len - target),
        };
      }
      if (mode === "area") {
        const tiles = tileCount();
        const target = num(cfg.target_area, 24);
        return {
          hit: tiles === target, ratio: clamp(tiles / target, 0, 1),
          mode: "area", tiles, target_area: target, outOfBounds: state.outOfBounds,
        };
      }
      if (mode === "coordinate") {
        const ok = coordCorrect();
        const total = (cfg.targets || []).length || 1;
        return {
          hit: ok === (cfg.targets || []).length, ratio: clamp(ok / total, 0, 1),
          mode: "coordinate", correct: ok, total,
        };
      }
      if (mode === "scale") {
        const tw = num(cfg.target_w, 6), th = num(cfg.target_h, 4);
        const wOk = state.selW === tw, hOk = state.selH === th;
        return {
          hit: wOk && hOk, ratio: (wOk ? 0.5 : 0) + (hOk ? 0.5 : 0),
          mode: "scale", width: state.selW, height: state.selH, target_w: tw, target_h: th, scale: num(cfg.scale, 2),
        };
      }
      if (mode === "volume") {
        const vol = state.len * state.wid * state.hei;
        const target = num(cfg.target_volume, 30);
        return {
          hit: vol === target, ratio: clamp(1 - Math.abs(vol - target) / (target * 2), 0, 1),
          mode: "volume", length: state.len, width: state.wid, height: state.hei, volume: vol, target_volume: target,
        };
      }
      // creator
      const blocks = creatorTotal();
      return {
        hit: blocks >= 1, ratio: clamp(blocks / (gridCols() * gridRows()), 0, 1),
        mode: "creator", blocks,
      };
    }

    function submit() {
      state.attempts += 1;
      const result = compute();
      result.attempts = state.attempts;
      state.hitResult = { hit: result.hit };

      if (mode === "scale" && !result.hit) {
        if (typeof toast === "function") toast("想一想比例尺：每格 ×" + num(cfg.scale, 2) + "，每条边都乘一乘～", 3200);
      }
      updateStatus();
      updateHUD();
      if (hitCallback) hitCallback(result);
    }

    function saveCreator() {
      const blocks = creatorTotal();
      if (blocks < 1) {
        if (typeof toast === "function") toast("先搭几块砖再保存吧～", 2200);
        return;
      }
      const name = (typeof prompt === "function" ? prompt("给你的作品起个名字吧：", "我的建筑") : "我的建筑") || "我的建筑";
      const heights = state.grid.map(rowArr => rowArr.map(v => v.h));
      const stats = {
        total: blocks,
        max_height: Math.max.apply(null, heights.map(r => Math.max.apply(null, r))),
        colors: (function () {
          const s = new Set();
          state.grid.forEach(r => r.forEach(v => { if (v.h > 0 && v.color) s.add(v.color); }));
          return s.size;
        })(),
      };
      const creations = readCreations();
      creations.push({ name: String(name), date: new Date().toISOString(), grid: heights, stats });
      writeCreations(creations);

      state.attempts += 1;
      const result = { hit: true, attempts: state.attempts, ratio: 1, mode: "creator", blocks, name: String(name) };
      state.hitResult = { hit: true };
      updateStatus();
      updateHUD();
      if (typeof toast === "function") toast("作品已保存！共 " + creations.length + " 件作品 🎨", 2800);
      if (hitCallback) hitCallback(result);
    }

    function reset() {
      if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
      initState();
      if (mode === "scale") {
        // 保留工具栏步进显示同步
        if (els.wVal) els.wVal.textContent = state.selW;
        if (els.hVal) els.hVal.textContent = state.selH;
      }
      syncControls();
      updateStatus();
      updateHUD();
      draw();
    }

    /* ---------------- 渲染 ---------------- */
    function rr(x, y, w, h, r) {
      if (typeof ctx.roundRect === "function") { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); return; }
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    function fillGround() {
      ctx.fillStyle = "rgba(44,58,72,0.30)";
      ctx.fillRect(originX, originY, cell * gridCols(), cell * gridRows());
    }
    function drawGridLines() {
      const cols = gridCols(), rows = gridRows();
      ctx.strokeStyle = "rgba(255,255,255,0.22)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let c = 0; c <= cols; c++) {
        const x = Math.round(colX(c)) + 0.5;
        ctx.moveTo(x, originY); ctx.lineTo(x, originY + cell * rows);
      }
      for (let r = 0; r <= rows; r++) {
        const y = Math.round(rowY(r)) + 0.5;
        ctx.moveTo(originX, y); ctx.lineTo(originX + cell * cols, y);
      }
      ctx.stroke();
    }

    function drawBlock(col, row, color, alpha) {
      const x = colX(col) + 1, y = rowY(row) + 1, s = cell - 2;
      ctx.save();
      ctx.globalAlpha = alpha == null ? 0.92 : alpha;
      ctx.fillStyle = color;
      rr(x, y, s, s, 3);
      ctx.fill();
      ctx.globalAlpha = 0.35;
      ctx.fillStyle = "#ffffff";
      rr(x + 1, y + 1, s - 2, Math.max(2, s * 0.32), 2);
      ctx.fill();
      ctx.restore();
    }

    function drawHoverCell(col, row) {
      const x = colX(col), y = rowY(row), s = cell;
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.75)";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(x + 1, y + 1, s - 2, s - 2);
      ctx.setLineDash([]);
      ctx.restore();
    }

    function draw() {
      ctx.clearRect(0, 0, viewW, viewH);
      if (mode === "length") drawLength();
      else if (mode === "area") drawArea();
      else if (mode === "coordinate") drawCoordinate();
      else if (mode === "scale") drawScale();
      else if (mode === "volume") drawVolume();
      else drawCreator();
    }

    function drawLength() {
      fillGround();
      drawGridLines();
      const len = currentLength();
      for (let c = 0; c < gridCols(); c++) {
        if (state.bricks[c]) drawBlock(c, 0, "#d98b4f");
      }
      // 下一块预览
      if (len < gridCols()) {
        const x = colX(len), y = rowY(0), s = cell;
        ctx.save();
        ctx.globalAlpha = 0.4;
        ctx.fillStyle = "#ffffff";
        rr(x + 2, y + 2, s - 4, s - 4, 3);
        ctx.fill();
        ctx.restore();
      }
      if (state.hover && state.hover.row === 0) drawHoverCell(state.hover.col, 0);
    }

    function drawArea() {
      fillGround();
      drawGridLines();
      const rw = num(cfg.room_w, 6), rh = num(cfg.room_h, 4);
      // 房间高亮边框
      ctx.save();
      ctx.strokeStyle = "rgba(255,220,120,0.85)";
      ctx.lineWidth = 2;
      ctx.strokeRect(originX + 1, originY + 1, rw * cell - 2, rh * cell - 2);
      ctx.globalAlpha = 0.10;
      ctx.fillStyle = "#ffe08a";
      ctx.fillRect(originX, originY, rw * cell, rh * cell);
      ctx.restore();
      Object.keys(state.tiles).forEach(k => {
        const p = k.split("_");
        drawBlock(Number(p[0]), Number(p[1]), "#5aa9e6");
      });
      if (state.hover && state.hover.col < rw && state.hover.row < rh) drawHoverCell(state.hover.col, state.hover.row);
    }

    function drawCoordinate() {
      const cols = gridCols(), rows = gridRows();
      const xMin = num(cfg.axis_range[0], -5), xMax = num(cfg.axis_range[1], 5);
      const xStep = (xMax - xMin) / (cols - 1);
      const yMax = (rows - 1) / 2, yMin = -yMax, yStep = (yMax - yMin) / (rows - 1);

      fillGround();
      // 象限底色弱化
      const gx0 = originX, gy0 = originY, gw = cell * cols, gh = cell * rows;
      const cx = colX((0 - xMin) / xStep);
      const cy = rowY((yMax - 0) / yStep);
      ctx.save();
      ctx.fillStyle = "rgba(90,160,255,0.07)"; ctx.fillRect(gx0, gy0, cx - gx0, cy - gy0);          // Q2
      ctx.fillStyle = "rgba(90,200,130,0.07)"; ctx.fillRect(cx, gy0, gx0 + gw - cx, cy - gy0);      // Q1
      ctx.fillStyle = "rgba(255,160,90,0.07)"; ctx.fillRect(gx0, cy, cx - gx0, gy0 + gh - cy);      // Q3
      ctx.fillStyle = "rgba(200,130,255,0.07)"; ctx.fillRect(cx, cy, gx0 + gw - cx, gy0 + gh - cy); // Q4
      ctx.restore();

      drawGridLines();

      // 坐标轴
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.6)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(originX, cy); ctx.lineTo(originX + gw, cy);   // x 轴
      ctx.moveTo(cx, originY); ctx.lineTo(cx, originY + gh);   // y 轴
      ctx.stroke();
      // 箭头标注
      ctx.fillStyle = "rgba(255,255,255,0.8)";
      ctx.font = "bold " + Math.max(10, Math.round(cell * 0.34)) + "px sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.fillText("x", originX + gw - 12, cy - 10);
      ctx.textAlign = "center"; ctx.textBaseline = "bottom";
      ctx.fillText("y", cx + 8, originY + 12);
      // 刻度数字
      ctx.font = Math.max(9, Math.round(cell * 0.3)) + "px sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      for (let c = 0; c < cols; c++) {
        const v = Math.round((xMin + c * xStep) * 10) / 10;
        ctx.fillText(String(v), colX(c) + cell / 2, cy + 3);
      }
      ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (let r = 0; r < rows; r++) {
        const v = Math.round((yMax - r * yStep) * 10) / 10;
        if (v === 0) continue;
        ctx.fillText(String(v), cx - 4, rowY(r) + cell / 2);
      }
      ctx.restore();

      // 已放方块
      Object.keys(state.coord).forEach(k => {
        const p = k.split("_");
        drawBlock(Number(p[0]), Number(p[1]), state.coord[k]);
      });
      if (state.hover) {
        drawHoverCell(state.hover.col, state.hover.row);
        const hvx = Math.round((xMin + state.hover.col * xStep) * 10) / 10;
        const hvy = Math.round((yMax - state.hover.row * yStep) * 10) / 10;
        ctx.save();
        ctx.fillStyle = "rgba(0,0,0,0.65)";
        const label = "(" + hvx + "," + hvy + ")";
        const tw = ctx.measureText(label).width + 8;
        const tx = colX(state.hover.col) + cell / 2, ty = rowY(state.hover.row) - 6;
        ctx.font = "11px sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "bottom";
        ctx.globalAlpha = 0.9;
        rr(tx - tw / 2, ty - 14, tw, 14, 4);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.fillText(label, tx, ty - 3);
        ctx.restore();
      }
    }

    function drawScale() {
      const cols = gridCols(), rows = gridRows();
      fillGround();
      drawGridLines();
      // 设计图（左侧虚线框）
      const designCell = Math.max(8, Math.round(32 * 0.75));
      const dw = num(cfg.design_w, 3) * designCell, dh = num(cfg.design_h, 2) * designCell;
      const dx = 10, dy = originY;
      ctx.save();
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.fillRect(dx - 6, dy - 22, dw + 12, dh + 40);
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = "rgba(255,220,130,0.9)";
      ctx.lineWidth = 2;
      ctx.strokeRect(dx, dy, dw, dh);
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(255,220,130,0.95)";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillText("图上", dx, dy - 16);
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillText(num(cfg.design_w, 3) + "×" + num(cfg.design_h, 2), dx + dw / 2, dy + dh + 4);
      ctx.restore();

      // 选中真实尺寸预览（左上角 w×h 格）
      const w = state.selW, h = state.selH;
      ctx.save();
      ctx.strokeStyle = "rgba(120,220,255,0.9)";
      ctx.lineWidth = 2;
      ctx.strokeRect(originX + 1, originY + 1, w * cell - 2, h * cell - 2);
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = "#7adcff";
      ctx.fillRect(originX, originY, w * cell, h * cell);
      ctx.restore();
    }

    function drawVolume() {
      const l = state.len, w = state.wid, h = state.hei;
      const u = clamp(Math.floor(Math.min((viewW - 40) / (l + w), (viewH - 60) / (l + w + h))), 4, 30);
      const cx = viewW / 2, cy = viewH - 26;
      function P(x, y, z) {
        return { x: cx + (x - y) * 0.866 * u, y: cy - (x + y) * 0.5 * u - z * 0.866 * u };
      }
      function poly(pts, fill) {
        ctx.beginPath();
        pts.forEach((p, i) => { if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y); });
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.35)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.save();
      // 底面
      poly([P(0, 0, 0), P(l, 0, 0), P(l, w, 0), P(0, w, 0)], "rgba(90,90,90,0.35)");
      // 左面
      poly([P(0, 0, 0), P(0, w, 0), P(0, w, h), P(0, 0, h)], "rgba(120,160,220,0.75)");
      // 右面
      poly([P(0, w, 0), P(l, w, 0), P(l, w, h), P(0, w, h)], "rgba(90,130,190,0.75)");
      // 顶面
      poly([P(0, 0, h), P(l, 0, h), P(l, w, h), P(0, w, h)], "rgba(160,200,255,0.85)");
      ctx.restore();

      // 标注
      ctx.save();
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillText("长 " + l, cx + (l / 2) * 0.866 * u + 6, cy - (l / 2) * 0.5 * u + 4);
      ctx.textAlign = "left";
      ctx.fillText("宽 " + w, cx + (l) * 0.866 * u + 6, cy - (l + w) * 0.5 * u - 4);
      ctx.textAlign = "center";
      ctx.fillText("高 " + h, cx, cy - (l + w) * 0.5 * u - h * 0.866 * u - 10);
      ctx.restore();
    }

    function drawCreator() {
      fillGround();
      drawGridLines();
      const maxH = num(cfg.max_height, 6);
      for (let r = 0; r < gridRows(); r++) {
        for (let c = 0; c < gridCols(); c++) {
          const v = state.grid[r][c];
          if (!v || !v.h) continue;
          const x = colX(c), y = rowY(r), s = cell;
          const baseY = y + s;
          for (let k = 0; k < v.h; k++) {
            const amt = maxH > 1 ? 0.35 * (k / (maxH - 1)) : 0;
            const col = lighten(v.color, amt);
            const by = baseY - (k + 1) * stackH;
            ctx.save();
            ctx.globalAlpha = 0.92;
            ctx.fillStyle = col;
            rr(x + 2, by, s - 4, stackH - 2, 2);
            ctx.fill();
            ctx.globalAlpha = 0.3;
            ctx.fillStyle = "#fff";
            rr(x + 3, by + 1, s - 6, Math.max(2, (stackH - 2) * 0.35), 2);
            ctx.fill();
            ctx.restore();
          }
        }
      }
      if (state.hover) {
        drawHoverCell(state.hover.col, state.hover.row);
      }
    }

    /* ---------------- 对外 API ---------------- */
    const inst = {
      render,
      reset,
      submit,
      getState() {
        return { mode, attempts: state.attempts, hitResult: state.hitResult, config: cfg };
      },
      onHit(cb) { hitCallback = typeof cb === "function" ? cb : null; },
      onHelp(cb) { helpCallback = typeof cb === "function" ? cb : null; },
      getCreations() { return readCreations(); },
      destroy() {
        if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
        window.removeEventListener("resize", resize);
        if (inst._ro) { inst._ro.disconnect(); inst._ro = null; }
        containerEl.classList.remove("bld-sim");
        containerEl.innerHTML = "";
      },
    };

    return inst;
  }

  window.BuildingSimulator = {
    createSimulator,
    COLOR_HEX,
    PALETTE,
    readCreations,
  };
})();
