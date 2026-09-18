/* V3.0 · 前端音效系统 (sound.js)
 * - 用 Web Audio API 合成提示音，不引入任何音频文件
 * - 暴露 window.Sound：enabled()/setEnabled()/play(name)
 * - 懒创建单例 AudioContext，浏览器策略导致失败时静默降级
 */

window.Sound = (function () {
  let ctx = null;

  function getCtx() {
    if (ctx) return ctx;
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (_) {
      ctx = null;
    }
    return ctx;
  }

  function _tone(freq, startDelay, dur, vol, waveType) {
    const ac = getCtx();
    if (!ac) return;
    try {
      if (ac.state === "suspended") ac.resume();
    } catch (_) { /* 静默 */ }

    const t = ac.currentTime + startDelay;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = waveType;
    osc.frequency.setValueAtTime(freq, t);
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(vol, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.start(t);
    osc.stop(t + dur);
  }

  function enabled() {
    return localStorage.getItem("xy_sound") !== "0";
  }

  function setEnabled(on) {
    localStorage.setItem("xy_sound", on ? "1" : "0");
  }

  const SEQUENCES = {
    // 连击：两个快速上行短音
    combo: [
      [660, 0.00, 0.08, 0.15, "triangle"],
      [880, 0.09, 0.08, 0.15, "triangle"],
    ],
    // 卡片掉落：清脆"叮"
    card: [
      [1318, 0.00, 0.25, 0.18, "sine"],
    ],
    // 顿悟金色特效：辉煌上行琶音 C5-E5-G5-C6
    insight: [
      [523, 0.00, 0.15, 0.20, "sine"],
      [659, 0.15, 0.15, 0.20, "sine"],
      [784, 0.30, 0.15, 0.20, "sine"],
      [1047, 0.45, 0.35, 0.20, "sine"],
    ],
    // 宠物升级：欢快上行琶音 C5-E5-G5-C6
    level_up: [
      [523, 0.00, 0.15, 0.18, "triangle"],
      [659, 0.15, 0.15, 0.18, "triangle"],
      [784, 0.30, 0.15, 0.18, "triangle"],
      [1047, 0.45, 0.20, 0.18, "triangle"],
    ],
    // 挑战成功/关卡通关：大调胜利号角 G4-C5-E5-G5
    victory: [
      [392, 0.00, 0.20, 0.22, "sine"],
      [523, 0.20, 0.20, 0.22, "sine"],
      [659, 0.40, 0.20, 0.22, "sine"],
      [784, 0.60, 0.30, 0.22, "sine"],
    ],
  };

  function play(name) {
    if (!enabled()) return;
    const seq = SEQUENCES[name];
    if (!seq) return; // 未知音效名静默
    seq.forEach(([freq, delay, dur, vol, wave]) => _tone(freq, delay, dur, vol, wave));
  }

  return { enabled, setEnabled, play };
})();
