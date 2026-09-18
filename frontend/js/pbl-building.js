/* V3.0 P2 · 模块「🧱 我的世界建筑」PBL 集成逻辑 (pbl-building.js)
 * - 暴露 window.BuildingProject 供 app.js 接线：
 *   LEVEL_CONFIGS（simulator_type → 默认 config，无后端 config 时兜底）
 *   mountSimulator(containerEl, simulatorType, config) → 创建模拟器并接入 onHit → onLevelComplete(payload)
 *   setCompleteHandler(fn)（app.js 调 submitComplete）
 *   displayHint(levelId) / getLevelIntro(levelId)
 * 依赖：window.BuildingSimulator（simulators/building.js）
 */

(function () {
  "use strict";

  /* ---------------- 关卡默认配置（与后端 simulator_config 对齐，simulator_type = building_level1..6） ---------------- */
  const LEVEL_CONFIGS = {
    building_level1: {
      mode: "length",
      target_length: 12,
      grid_cols: 14,
      grid_rows: 4,
      help_button: false,
    },
    building_level2: {
      mode: "area",
      room_w: 6,
      room_h: 4,
      target_area: 24,
      grid_cols: 8,
      grid_rows: 6,
      help_button: true,
    },
    building_level3: {
      mode: "coordinate",
      grid_cols: 11,
      grid_rows: 9,
      axis_range: [-5, 5],
      targets: [
        { color: "red", x: 3, y: 2 },
        { color: "blue", x: -2, y: 4 },
        { color: "green", x: 0, y: -3 },
      ],
      help_button: true,
    },
    building_level4: {
      mode: "scale",
      design_w: 3,
      design_h: 2,
      scale: 2,
      scale_label: "1:2",
      target_w: 6,
      target_h: 4,
      grid_cols: 10,
      grid_rows: 8,
      help_button: true,
    },
    building_level5: {
      mode: "volume",
      target_volume: 30,
      length_range: [1, 8],
      width_range: [1, 8],
      height_range: [1, 8],
      help_button: true,
    },
    building_level6: {
      mode: "creator",
      grid_cols: 10,
      grid_rows: 8,
      max_height: 6,
      help_button: false,
    },
  };

  /* ---------------- 小圆开场话术（建筑主题，助手口吻） ---------------- */
  const INTROS = {
    building_level1: "欢迎来到建筑工地！我是你的助手小圆。今天要砌一面城墙：从最左边开始，一格一格往右铺砖，铺满 12 格就成功啦。点一下第一行的格子试试～",
    building_level2: "这次我们铺房间的地砖。房间在左上角那块高亮区域，一格一格点进去，把整个房间铺满 24 块砖，不多也不少哦。",
    building_level3: "建筑师要会看图纸坐标。先找横轴（x），再找竖轴（y）——(3,2) 就是先往右 3 格、再往上 2 格。按目标清单把彩色方块放到正确的位置吧！",
    building_level4: "比例尺是放大图纸的魔法。图上 1 格代表实际 2 格，所以 3×2 的图要建成 6×4 的真实房子。调好宽度和高度再提交～",
    building_level5: "来盖一座立体仓库！仓库的容量 = 长 × 宽 × 高。拖动三个滑块，找到乘积正好等于 30 的那组尺寸。",
    building_level6: "总设计师，尽情发挥吧！在空地上自由搭建你的作品——点击加高、右键去掉，还能选颜色。搭好后点「保存作品」收藏起来！",
  };

  /* ---------------- 「计算辅助」提示 ---------------- */
  const HINTS = {
    building_level2: "面积=长×宽，6×4=24 块砖",
    building_level3: "先看横轴再看竖轴，(3,2) 是先右 3 再上 2，负数往左/下",
    building_level4: "比例尺 1:2：长 3×2=6、宽 2×2=4，每条边都乘 2",
    building_level5: "体积=长×宽×高，你只需要让三数乘积=30",
  };

  let completeHandler = null;

  function setCompleteHandler(fn) {
    completeHandler = typeof fn === "function" ? fn : null;
  }

  function onLevelComplete(payload) {
    if (typeof completeHandler === "function") completeHandler(payload);
  }

  /* 组装 payload 并上报
   * score 规则：hit ? 100 : min(79, round(达成比例*100))；simulator_data = {mode, ...关键参数} */
  function mountSimulator(containerEl, simulatorType, config) {
    if (!window.BuildingSimulator) throw new Error("BuildingProject: 缺少 window.BuildingSimulator");
    const cfg = Object.assign({}, LEVEL_CONFIGS[simulatorType] || {}, config || {});
    const sim = window.BuildingSimulator.createSimulator(containerEl, cfg);
    sim.render();

    sim.onHit(result => {
      const score = result.hit ? 100 : Math.min(79, Math.round((result.ratio || 0) * 100));
      const payload = {
        score,
        hit: result.hit,
        attempts: result.attempts,
        simulator_data: toSimulatorData(result),
      };
      if (result.hit) onLevelComplete(payload);
    });

    if (cfg.help_button) {
      sim.onHelp(() => {
        const hint = displayHint(simulatorType);
        if (hint && typeof window.toast === "function") window.toast(hint, 4200);
      });
    }

    sim._simulatorType = simulatorType;
    window.BuildingProject._sim = sim;
    return sim;
  }

  function toSimulatorData(r) {
    const d = { mode: r.mode };
    const skip = { hit: 1, attempts: 1, ratio: 1, mode: 1 };
    Object.keys(r).forEach(k => {
      if (!skip[k]) d[k] = r[k];
    });
    return d;
  }

  function displayHint(levelId) {
    return HINTS[levelId] || null;
  }

  function getLevelIntro(levelId) {
    return INTROS[levelId] || "";
  }

  window.BuildingProject = {
    LEVEL_CONFIGS,
    mountSimulator,
    setCompleteHandler,
    onLevelComplete,
    displayHint,
    getLevelIntro,
  };
})();
