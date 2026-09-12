/* V3.0 P2 · 模块 F「导弹发射弧线」PBL 集成逻辑 (pbl-missile.js)
 * 规格 8.2 关卡设计 / 8.4 通关条件 / 8.5 引导话术
 * - 暴露 window.MissileProject 供 pbl.js 集成者接线：
 *   LEVEL_CONFIGS（simulator_type → 默认 config，无后端 config 时兜底）
 *   mountSimulator(containerEl, simulatorType, config) → 创建模拟器并接入 onHit → onLevelComplete(payload)
 *   setCompleteHandler(fn)（pbl.js 调 submitComplete）
 *   displayHint(levelId) / getLevelIntro(levelId)
 * 依赖：window.MissileSimulator（simulators/missile.js）
 */

(function () {
  "use strict";

  /* ---------------- 关卡默认配置（与后端 simulator_config 对齐） ---------------- */
  const LEVEL_CONFIGS = {
    missile_level1: {
      angle_range: [0, 0],           // 固定角度 0°，只有力度滑块（平抛）
      power_range: [0, 100],
      wind: false,
      wind_range: [-20, 20],
      target_moving: false,
      target_speed: 0,
      target_distance: 100,
      show_trajectory: true,
      help_button: false,
      editor: false,
      launch_height: 60,             // 平抛需要初始高度（8.3 公式为斜抛特例，此处补高台）
    },
    missile_level2: {
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
      launch_height: 0,
    },
    missile_level3: {
      angle_range: [0, 90],
      power_range: [0, 100],
      wind: false,
      wind_range: [-20, 20],
      target_moving: false,
      target_speed: 0,
      target_distance: 100,
      show_trajectory: true,
      help_button: true,
      editor: false,
      launch_height: 0,
    },
    missile_level4: {
      angle_range: [0, 90],
      power_range: [0, 100],
      wind: true,
      wind_range: [-20, 20],
      target_moving: false,
      target_speed: 0,
      target_distance: 100,
      show_trajectory: true,
      help_button: true,
      editor: false,
      launch_height: 0,
    },
    missile_level5: {
      angle_range: [0, 90],
      power_range: [0, 100],
      wind: false,
      wind_range: [-20, 20],
      target_moving: true,
      target_speed: 5,
      target_distance: 100,
      show_trajectory: true,
      help_button: true,
      editor: false,
      launch_height: 0,
    },
    missile_level6: {
      angle_range: [0, 90],
      power_range: [0, 100],
      wind: true,
      wind_range: [-20, 20],
      target_moving: true,
      target_speed: 5,
      target_distance: 100,
      show_trajectory: true,
      help_button: true,
      editor: true,
      launch_height: 0,
    },
  };

  /* ---------------- 小圆开场话术（规格 8.5，助手口吻，不主动打扰） ---------------- */
  const INTROS = {
    missile_level1: "欢迎来到导弹基地！我是你的助手小圆。今天任务很简单：调整力度，把导弹扔到对面的靶子上。试试拖一下力度滑块，然后点发射！",
    missile_level2: "这一关角度和力度都能调啦！记住一个小规律：角度太矮飞不远，太高也飞不远，45° 附近往往飞得最远。试试看，找到一个能命中的组合吧。",
    missile_level3: "靶子在 100 米外，这次要自己算一算角度和力度怎么搭配。卡住了随时点「计算辅助」，我会帮你理清思路。",
    missile_level4: "今天起风了，风会水平推着导弹跑。学会修正风的影响，导弹才能稳稳命中，试试看～",
    missile_level5: "注意！靶子会左右移动啦。别瞄准它现在的位置，要预判它接下来会走到哪里，提前发射。",
    missile_level6: "总工程师，全交给你啦！设计一个打靶关卡——设置靶子距离、风速、移动靶，保存下来，再亲手打通它！",
  };

  /* ---------------- 「计算辅助」提示（规格 8.3 计算辅助按钮） ---------------- */
  const HINTS = {
    missile_level3: "想一想：水平飞行的距离 = 速度 × 时间。初速度越大、在空中待得越久，飞得越远。45° 时飞行时间最长，可以先试试 45° 配不同力度～",
    missile_level4: "风会给导弹一个水平方向的加速度。顺风（风速为正）飞得更远，逆风（风速为负）飞得更近。往风的反方向修正一点角度，或加大/减小力度试试。",
    missile_level5: "别瞄靶子现在的位置！先估算导弹要飞多久，再算这段时间靶子会移动多远（距离 = 速度 × 时间），往它前进的方向提前一段距离发射。",
  };

  let completeHandler = null;

  function setCompleteHandler(fn) {
    completeHandler = typeof fn === "function" ? fn : null;
  }

  function onLevelComplete(payload) {
    if (typeof completeHandler === "function") completeHandler(payload);
  }

  /* 组装 payload 并上报（规格 8.6 / 任务：score=命中时 round(100-|落点-靶心|*2) 最低50，未命中0） */
  function mountSimulator(containerEl, simulatorType, config) {
    if (!window.MissileSimulator) throw new Error("MissileProject: 缺少 window.MissileSimulator");
    const cfg = Object.assign({}, LEVEL_CONFIGS[simulatorType] || {}, config || {});
    const sim = window.MissileSimulator.createSimulator(containerEl, cfg);
    sim.render();

    sim.onHit(result => {
      const score = result.hit ? Math.max(50, Math.round(100 - result.distance * 2)) : 0;
      const payload = {
        score,
        hit: result.hit,
        attempts: result.attempts,
        simulator_data: {
          angle: result.angle,
          power: result.power,
          windSpeed: result.windSpeed,
          hit: result.hit,
        },
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
    window.MissileProject._sim = sim;
    return sim;
  }

  function displayHint(levelId) {
    return HINTS[levelId] || null;
  }

  function getLevelIntro(levelId) {
    return INTROS[levelId] || "";
  }

  window.MissileProject = {
    LEVEL_CONFIGS,
    mountSimulator,
    setCompleteHandler,
    onLevelComplete,
    displayHint,
    getLevelIntro,
  };
})();
