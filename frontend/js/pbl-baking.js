/* V3.0 P2 · 模块「🍰 烘焙实验室」PBL 集成逻辑 (pbl-baking.js)
 * - 暴露 window.BakingProject 供 app.js 接线：
 *   LEVEL_CONFIGS（simulator_type → 默认 config，无后端 config 时兜底）
 *   mountSimulator(containerEl, simulatorType, config) → 创建模拟器并接入 onHit → onLevelComplete(payload)
 *   setCompleteHandler(fn)（app.js 调 submitComplete）
 *   displayHint(levelId) / getLevelIntro(levelId)
 * 依赖：window.BakingSimulator（simulators/baking.js）
 */

(function () {
  "use strict";

  /* ---------------- 关卡默认配置（与后端 simulator_config 对齐，simulator_type = baking_level1..6） ---------------- */
  const LEVEL_CONFIGS = {
    baking_level1: {
      mode: "recipe_scale",
      from_servings: 3,
      to_servings: 5,
      help_button: true,
      ingredients: [
        { name: "低筋面粉", emoji: "🌾", amount: 150, unit: "克" },
        { name: "细砂糖", emoji: "🍬", amount: 90, unit: "克" },
        { name: "黄油", emoji: "🧈", amount: 60, unit: "克" },
        { name: "鸡蛋", emoji: "🥚", amount: 3, unit: "个" },
      ],
    },
    baking_level2: {
      mode: "doubling",
      factor: 2,
      help_button: true,
      ingredients: [
        { name: "面粉", emoji: "🌾", amount: 100, unit: "克" },
        { name: "牛奶", emoji: "🥛", amount: 120, unit: "毫升" },
        { name: "黄油", emoji: "🧈", amount: 80, unit: "克" },
        { name: "细砂糖", emoji: "🍬", amount: 50, unit: "克" },
      ],
    },
    baking_level3: {
      mode: "temperature",
      target: 180,
      help_button: true,
      temps: [
        { c: 0, f: 32 },
        { c: 100, f: 212 },
      ],
    },
    baking_level4: {
      mode: "time",
      total_minutes: 60,
      help_button: true,
      segments: [
        { name: "和面", ratio: 0.25 },
        { name: "发酵", ratio: 0.5 },
        { name: "烘烤", ratio: 0.25 },
      ],
    },
    baking_level5: {
      mode: "party_plan",
      target_people: 8,
      help_button: true,
      per_person: [
        { name: "饼干", emoji: "🍪", amount: 2, unit: "块" },
        { name: "杯子蛋糕", emoji: "🧁", amount: 1, unit: "个" },
        { name: "果汁", emoji: "🧃", amount: 200, unit: "毫升" },
        { name: "水果串", emoji: "🍢", amount: 3, unit: "串" },
      ],
    },
    baking_level6: {
      mode: "free",
      help_button: false,
    },
  };

  /* ---------------- 小圆开场话术（烘焙主题，助手口吻） ---------------- */
  const INTROS = {
    baking_level1: "欢迎来到烘焙实验室！我是你的助手小圆。今天要做一个 3 人份的蛋糕，但客人来了 5 位——把每样材料都按比例放大就好啦。先想想 5 是 3 的几倍？",
    baking_level2: "朋友要来啦，蛋糕得做双份！把每个材料的用量都乘以 2，填进工作台里。乘法会帮你把面团变大哦。",
    baking_level3: "烤箱说明书上写的是华氏温度，可配方里是摄氏。记住换算小口诀：先乘 9，再除 5，最后加 32。把 180°C 换成华氏吧。",
    baking_level4: "做面包要分三段：和面、发酵、烘烤。总共 60 分钟，按 1 : 2 : 1 的比例拆开——加起来必须正好等于 60 分钟哦。",
    baking_level5: "要办一场 8 个人的生日派对！每个人吃多少是已知的，那整桌要准备多少？一个人 × 人数 = 总量，逐样算出来。",
    baking_level6: "首席烘焙师，尽情发挥吧！挑几种喜欢的材料、填好用量、起个名字，保存你的专属配方。",
  };

  /* ---------------- 「计算辅助」提示 ---------------- */
  const HINTS = {
    baking_level1: "5÷3 是倍数，每个材料都乘上它。150×5÷3=250，其他材料也照这样做",
    baking_level2: "所有材料都 ×2：100→200、120→240、80→160、50→100",
    baking_level3: "°F = °C × 9 ÷ 5 + 32，180×9÷5+32=356",
    baking_level4: "总 60 分钟按 1:2:1 拆成 15、30、15，三段加起来正好 60",
    baking_level5: "每人份 × 8 人：饼干 2×8=16 块，其他材料也乘 8",
  };

  let completeHandler = null;

  function setCompleteHandler(fn) {
    completeHandler = typeof fn === "function" ? fn : null;
  }

  function onLevelComplete(payload) {
    if (typeof completeHandler === "function") completeHandler(payload);
  }

  /* 组装 payload 并上报
   * score 规则：hit ? 100 : min(79, round(ratio))；simulator_data = {mode, ...关键参数} */
  function mountSimulator(containerEl, simulatorType, config) {
    if (!window.BakingSimulator) throw new Error("BakingProject: 缺少 window.BakingSimulator");
    const cfg = Object.assign({}, LEVEL_CONFIGS[simulatorType] || {}, config || {});
    const sim = window.BakingSimulator.createSimulator(containerEl, cfg);
    sim.render();

    sim.onHit(result => {
      const score = result.hit ? 100 : Math.min(79, Math.round((result.ratio || 0)));
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
    window.BakingProject._sim = sim;
    return sim;
  }

  function toSimulatorData(r) {
    const d = { mode: r.mode };
    const skip = { hit: 1, attempts: 1, ratio: 1, mode: 1, okCount: 1, total: 1 };
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

  window.BakingProject = {
    LEVEL_CONFIGS,
    mountSimulator,
    setCompleteHandler,
    onLevelComplete,
    displayHint,
    getLevelIntro,
  };
})();
