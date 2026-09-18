/* V3.0 P2 · 模块「🎵 音乐与数学」PBL 集成逻辑 (pbl-music.js)
 * - 暴露 window.MusicProject 供 app.js 接线：
 *   LEVEL_CONFIGS（simulator_type → 默认 config，无后端 config 时兜底）
 *   mountSimulator(containerEl, simulatorType, config) → 创建模拟器并接入 onHit → onLevelComplete(payload)
 *   setCompleteHandler(fn)（app.js 调 submitComplete）
 *   displayHint(levelId) / getLevelIntro(levelId)
 * 依赖：window.MusicSimulator（simulators/music.js）
 */

(function () {
  "use strict";

  /* ---------------- 关卡默认配置（与后端 simulator_config 对齐，simulator_type = music_level1..6） ---------------- */
  const LEVEL_CONFIGS = {
    music_level1: {
      mode: "beat",
      target_beats: 4,
      note_pool: [1, 0.5, 2, 4],
      grid_rows: 2,
      grid_cols: 4,
      help_button: true,
    },
    music_level2: {
      mode: "interval",
      base_freq: 261.63,
      target_ratio: 1.5,
      count: 1,
      help_button: true,
    },
    music_level3: {
      mode: "chord",
      base_freq: 261.63,
      target_ratio: 6,
      help_button: true,
    },
    music_level4: {
      mode: "scale",
      notes: [261.63, 293.66, 329.63, 349.23, 392.00, 440.00],
      period_multiplier: 2,
      help_button: true,
    },
    music_level5: {
      mode: "rhythm_compose",
      measure_beats: 4,
      help_button: true,
    },
    music_level6: {
      mode: "free",
      grid_cols: 8,
      grid_rows: 2,
      help_button: false,
    },
  };

  /* ---------------- 小圆开场话术（音乐主题，助手口吻） ---------------- */
  const INTROS = {
    music_level1: "欢迎来到音乐工坊！我是你的助手小圆。今天我们把分数音符拼成一整小节——一个小节有 4 拍，用四分音符（1拍）、八分音符（半拍）等凑满正好 4 拍，不多也不少。选一个音符再点格子试试～",
    music_level2: "声音的高低叫音高，两个音高的频率比就是「音程」。听一听根音和目标音，判断它们是什么音程——同度、八度、五度、四度还是大三度？",
    music_level3: "和弦是几个音一起响。大三和弦的频率比是 4:5:6。调出低、中、高三个音，组成 4:5:6 的和弦吧！",
    music_level4: "音阶有个神奇规律：同一个音升一个八度，频率正好翻倍（×2）。找一找这个倍数，感受音乐的周期性。",
    music_level5: "来当小小作曲家！把分数音符自由组合，填满一小节（4 拍）。先选音符时长，再点格子，最后点播放听一听。",
    music_level6: "大作曲家，尽情创作吧！选音高和时值，在格子里写下你的旋律，播放试听，满意了就保存下来。",
  };

  /* ---------------- 「计算辅助」提示 ---------------- */
  const HINTS = {
    music_level1: "整小节 = 4 拍。四分音符=1拍、八分音符=半拍、二分音符=2拍、全音符=4拍，加起来正好 4 就行。",
    music_level2: "记住频率比：1/1 同度、2/1 八度、3/2 五度、4/3 四度、5/4 大三度。",
    music_level3: "大三和弦 4:5:6：低音 4、中音 5、高音 6（相对比例）。",
    music_level4: "升一个八度，频率 ×2；再升一个八度，再 ×2。这就是周期的秘密。",
    music_level5: "一小节 4 拍，怎么组合都行：4 个四分音符、2 个二分音符、或 8 个八分音符，只要总拍数 = 4。",
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
    if (!window.MusicSimulator) throw new Error("MusicProject: 缺少 window.MusicSimulator");
    const cfg = Object.assign({}, LEVEL_CONFIGS[simulatorType] || {}, config || {});
    const sim = window.MusicSimulator.createSimulator(containerEl, cfg);
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
    window.MusicProject._sim = sim;
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

  window.MusicProject = {
    LEVEL_CONFIGS,
    mountSimulator,
    setCompleteHandler,
    onLevelComplete,
    displayHint,
    getLevelIntro,
  };
})();
