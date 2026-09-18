/* V3.0 P2 · 模块「🎵 音乐与数学」前端模拟器 (simulators/music.js)
 * - MusicSimulator：Web Audio 音乐模拟器（6 种模式）
 *   beat 拍子拼接 / interval 音程 / chord 和弦 / scale 音阶周期 / rhythm_compose 节拍创作 / free 自由创作
 * - 暴露 window.MusicSimulator.createSimulator(containerEl, config) 供 pbl-music.js 挂载
 * - 纯原生 JS，AudioContext 实际播放音高；自动播放被拒时 try/catch 降级为无声但功能照常
 * 依赖（可选）：app.js 的 escapeHtml()（缺失时本地降级）
 */

(function () {
  "use strict";

  const CREATIONS_KEY = "xy_music_creations";

  const esc = (typeof escapeHtml === "function") ? escapeHtml
    : (s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"));

  function clamp(v, min, max) { return v < min ? min : (v > max ? max : v); }
  function num(v, d) { const n = Number(v); return isFinite(n) ? n : d; }
  function round1(v) { return Math.round(v * 10) / 10; }

  /* ---------------- 音符时长（拍） ---------------- */
  const BEAT_META = { 4: { label: "全音符" }, 2: { label: "二分音符" }, 1: { label: "四分音符" }, 0.5: { label: "八分音符" }, 0.25: { label: "十六分音符" } };
  function beatLabel(b) {
    const m = BEAT_META[b];
    return (m ? m.label + " " : "") + b + " 拍";
  }
  function beatGlyph(b) {
    if (b === 0.5) return "½";
    if (b === 0.25) return "¼";
    return String(b);
  }

  /* ---------------- 音程比率（频率比 → 音高） ---------------- */
  const INTERVALS = [
    { ratio: 1, label: "1/1 同度" },
    { ratio: 5 / 4, label: "5/4 大三度" },
    { ratio: 4 / 3, label: "4/3 四度" },
    { ratio: 3 / 2, label: "3/2 五度" },
    { ratio: 2, label: "2/1 八度" },
  ];
  function intervalLabel(r) {
    for (let i = 0; i < INTERVALS.length; i++) {
      if (Math.abs(INTERVALS[i].ratio - r) < 0.001) return INTERVALS[i].label;
    }
    return round1(r) + " 倍";
  }

  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  function freqName(f) {
    if (!f || f <= 0) return "";
    const midi = Math.round(69 + 12 * Math.log(f / 440) / Math.LN2);
    const name = NOTE_NAMES[((midi % 12) + 12) % 12];
    const oct = Math.floor(midi / 12) - 1;
    return name + oct;
  }

  const C_MAJOR = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25];

  /* ---------------- 纯数学判定（供内部 compute 与外部自测复用） ---------------- */
  function beatCompute(total, target) {
    const t = target || 1;
    return { hit: Math.abs(total - t) < 0.001, ratio: clamp(1 - Math.abs(total - t) / t, 0, 1) };
  }
  function intervalCompute(selected, target) {
    const d = Math.abs(Math.log(selected / target) / Math.LN2);
    return { hit: Math.abs(selected - target) < 0.001, ratio: clamp(1 - d, 0, 1) };
  }
  function chordCompute(voices, target) {
    const t = target.slice().sort((a, b) => a - b);
    const v = voices.slice().sort((a, b) => a - b);
    let matched = 0;
    for (let i = 0; i < Math.max(t.length, v.length); i++) if (t[i] === v[i]) matched++;
    return { hit: matched === t.length && v.length === t.length, ratio: clamp(matched / t.length, 0, 1), matched };
  }
  function scaleCompute(mult, period) {
    const d = Math.abs(Math.log(mult / period) / Math.LN2);
    return { hit: Math.abs(mult - period) < 0.001, ratio: clamp(1 - d, 0, 1) };
  }
  function freqForRatio(base, ratio) { return base * ratio; }
  function chordFreqs(base, multiples) {
    const root = Math.min.apply(null, multiples);
    return multiples.map(m => base * m / root);
  }

  /* ---------------- Web Audio ---------------- */
  let sharedCtx = null;
  const activeOscs = new Set();
  const BEAT_SEC = 0.5; // 120 BPM → 一拍 0.5 秒

  function ensureCtx() {
    if (!sharedCtx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      try { sharedCtx = new AC(); } catch (e) { sharedCtx = null; return null; }
    }
    if (sharedCtx && sharedCtx.state === "suspended") {
      try { sharedCtx.resume().catch(() => {}); } catch (e) {}
    }
    return sharedCtx;
  }

  function scheduleTone(freq, start, dur, type) {
    const ctx = ensureCtx();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = type || "triangle";
      osc.frequency.setValueAtTime(freq, start);
      g.gain.setValueAtTime(0.0001, start);
      g.gain.exponentialRampToValueAtTime(0.5, start + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + dur + 0.05);
      activeOscs.add(osc);
      osc.onended = () => { activeOscs.delete(osc); };
    } catch (e) { /* 自动播放被拒：静默降级，功能照常 */ }
  }

  function stopAll() {
    activeOscs.forEach(o => { try { o.stop(); } catch (e) {} });
    activeOscs.clear();
  }

  function playTone(freq, durSec) {
    const ctx = ensureCtx();
    if (!ctx) return;
    stopAll();
    scheduleTone(freq, ctx.currentTime + 0.05, Math.max(0.15, durSec || 0.6));
  }

  function playSequence(items) {
    const ctx = ensureCtx();
    if (!ctx) return;
    stopAll();
    let t = ctx.currentTime + 0.05;
    items.forEach(it => {
      const beats = it.beats != null ? it.beats : it.dur;
      const dur = Math.max(0.1, (beats || 1) * BEAT_SEC);
      scheduleTone(it.freq, t, dur);
      t += dur;
    });
  }

  function playChord(freqs) {
    const ctx = ensureCtx();
    if (!ctx) return;
    stopAll();
    const t = ctx.currentTime + 0.05;
    freqs.forEach(f => scheduleTone(f, t, 1.2, "sine"));
  }

  /* ---------------- localStorage 作品 ---------------- */
  function readCreations() {
    try {
      const raw = localStorage.getItem(CREATIONS_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function writeCreations(arr) {
    try { localStorage.setItem(CREATIONS_KEY, JSON.stringify(arr)); } catch (e) { /* 存储满则忽略 */ }
  }

  /* ---------------- 默认配置 ---------------- */
  const DEFAULT_CONFIG = {
    mode: "free",
    grid_cols: 8,
    grid_rows: 2,
    help_button: false,
    // beat
    target_beats: 4,
    note_pool: [1, 0.5, 2, 4],
    // interval
    base_freq: 261.63,
    target_ratio: 1.5,
    count: 1,
    // chord（base_freq 复用；target_ratio 仅作元数据）
    // scale
    notes: [261.63, 293.66, 329.63, 349.23, 392.00, 440.00],
    period_multiplier: 2,
    // rhythm_compose
    measure_beats: 4,
    // free
    pitches: [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25],
    durations: [0.5, 1, 2],
  };

  /* ---------------------------------------------------------------- 模拟器实例 */
  function createSimulator(containerEl, config) {
    if (!containerEl) throw new Error("MusicSimulator: 缺少容器元素");

    const cfg = Object.assign({}, DEFAULT_CONFIG, config || {});
    const mode = cfg.mode || "free";
    function notePool() {
      const p = Array.isArray(cfg.note_pool) && cfg.note_pool.length ? cfg.note_pool : [1, 0.5, 2, 4];
      return p.map(Number).filter(isFinite).sort((a, b) => b - a);
    }
    function freePitches() {
      return (Array.isArray(cfg.pitches) && cfg.pitches.length) ? cfg.pitches.map(Number).filter(isFinite) : C_MAJOR;
    }
    function freeDurations() {
      return (Array.isArray(cfg.durations) && cfg.durations.length) ? cfg.durations.map(Number).filter(isFinite) : [0.5, 1, 2];
    }
    function scaleNotes() {
      return (Array.isArray(cfg.notes) && cfg.notes.length) ? cfg.notes.map(Number).filter(isFinite) : [261.63, 293.66, 329.63, 349.23, 392.00, 440.00];
    }
    const gridCols = () => Math.max(1, Math.round(num(cfg.grid_cols, 8)));
    const gridRows = () => Math.max(1, Math.round(num(cfg.grid_rows, 2)));
    const isFree = mode === "free";
    const isBeat = mode === "beat" || mode === "rhythm_compose";

    const state = {
      attempts: 0,
      hitResult: null,
      notes: {},            // "r_c" -> beats(beat/rhythm) | {freq,dur}(free)
      ratio: null,          // interval 选中的比率
      mult: 1,              // scale 选中的倍数
      voices: [3, 3, 3],    // chord 三个声部（相对比例 3..6）
      paintFreq: null,      // free 当前音高
      paintDur: 1,          // 当前时值（拍）
    };

    let els = {};
    let hitCallback = null, helpCallback = null;

    /* ---------------- 状态初始化 ---------------- */
    function initState() {
      state.attempts = 0;
      state.hitResult = null;
      state.notes = {};
      state.ratio = null;
      state.mult = 1;
      state.voices = [3, 3, 3];
      state.paintFreq = null;
      state.paintDur = 1;
    }

    function targetBeats() {
      return mode === "rhythm_compose" ? num(cfg.measure_beats, 4) : num(cfg.target_beats, 4);
    }
    function currentBeats() {
      let s = 0;
      Object.keys(state.notes).forEach(k => { s += num(state.notes[k], 0); });
      return s;
    }
    function freeCount() { return Object.keys(state.notes).length; }

    /* ---------------- DOM 构建 ---------------- */
    function hintText() {
      if (mode === "beat") return "选一个音符时长，点格子摆放，凑满整小节的拍数";
      if (mode === "rhythm_compose") return "自由组合音符，把这一小节填满";
      if (mode === "interval") return "听根音和目标音，判断它们的频率比（音程）";
      if (mode === "chord") return "调出 4:5:6 的大三和弦（低/中/高三个音）";
      if (mode === "scale") return "找到升一个八度要乘的倍数";
      return "选音高和时值，点格子写旋律，点播放听一听";
    }

    function beatStageHTML() {
      const btns = notePool().map(b =>
        '<button type="button" class="mus-palette-btn js-beat-note" data-beat="' + b + '" aria-label="' + esc(beatLabel(b)) + '">' + esc(beatLabel(b)) + '</button>').join("");
      return '<div class="mus-palette"><span class="mus-legend">音符时长</span>' + btns + '</div>' +
        '<div class="mus-grid js-grid" role="grid" aria-label="拍子网格"></div>';
    }

    function intervalStageHTML() {
      const base = num(cfg.base_freq, 261.63);
      const btns = INTERVALS.map(it =>
        '<button type="button" class="mus-palette-btn js-interval" data-ratio="' + it.ratio + '" aria-label="' + esc(it.label) + '">' + esc(it.label) + '</button>').join("");
      return '<div class="mus-audio-row">' +
        '<button type="button" class="mus-btn js-play-base">听根音 ' + round1(base) + ' Hz</button>' +
        '<button type="button" class="mus-btn js-play-target">听目标音</button>' +
        '<button type="button" class="mus-btn js-play-answer">试听我的答案</button>' +
        '</div><div class="mus-palette"><span class="mus-legend">选择音程</span>' + btns + '</div>';
    }

    function chordStageHTML() {
      let s = '<div class="mus-steppers">';
      ["低音", "中音", "高音"].forEach((name, i) => {
        s += '<div class="mus-stepper"><span class="mus-step-name">' + name + '</span>' +
          '<button type="button" class="mus-step-btn js-voice-dec" data-i="' + i + '" aria-label="' + name + '减">−</button>' +
          '<span class="mus-step-val js-voice-val" data-i="' + i + '">' + state.voices[i] + '</span>' +
          '<button type="button" class="mus-step-btn js-voice-inc" data-i="' + i + '" aria-label="' + name + '加">＋</button></div>';
      });
      s += '</div><div class="mus-audio-row"><button type="button" class="mus-btn js-play-chord">播放我的和弦</button></div>';
      return s;
    }

    function scaleStageHTML() {
      const noteBtns = scaleNotes().map(f =>
        '<button type="button" class="mus-palette-btn js-scale-note" data-freq="' + f + '" aria-label="播放 ' + round1(f) + ' Hz">' + round1(f) + ' Hz</button>').join("");
      const multBtns = [1, 1.5, 2, 3, 4].map(m =>
        '<button type="button" class="mus-palette-btn js-scale-mult" data-mult="' + m + '" aria-label="×' + m + '">×' + m + '</button>').join("");
      return '<div class="mus-audio-row"><button type="button" class="mus-btn js-play-scale">试听 ×' + state.mult + '</button></div>' +
        '<div class="mus-palette"><span class="mus-legend">音高（可点听）</span>' + noteBtns + '</div>' +
        '<div class="mus-palette"><span class="mus-legend">升一个八度要乘几？</span>' + multBtns + '</div>';
    }

    function freeStageHTML() {
      const pitchBtns = freePitches().map(f =>
        '<button type="button" class="mus-palette-btn js-pitch" data-freq="' + f + '" aria-label="音高 ' + esc(freqName(f)) + '">' + esc(freqName(f)) + '</button>').join("");
      const durBtns = freeDurations().map(d =>
        '<button type="button" class="mus-palette-btn js-dur" data-dur="' + d + '" aria-label="时值 ' + esc(beatLabel(d)) + '">' + esc(beatLabel(d)) + '</button>').join("");
      return '<div class="mus-palette"><span class="mus-legend">音高</span>' + pitchBtns + '</div>' +
        '<div class="mus-palette"><span class="mus-legend">时值</span>' + durBtns + '</div>' +
        '<div class="mus-grid js-grid" role="grid" aria-label="自由创作网格"></div>';
    }

    function stageHTML() {
      if (isBeat) return beatStageHTML();
      if (mode === "interval") return intervalStageHTML();
      if (mode === "chord") return chordStageHTML();
      if (mode === "scale") return scaleStageHTML();
      return freeStageHTML();
    }

    function actionsHTML() {
      const helpBtn = cfg.help_button ? '<button type="button" class="mus-btn mus-btn-help js-help">计算辅助</button>' : "";
      if (isFree) {
        return '<div class="mus-actions">' +
          '<button type="button" class="mus-btn js-play">播放</button>' +
          '<button type="button" class="mus-btn mus-btn-submit js-submit">保存作品</button>' +
          '<button type="button" class="mus-btn js-reset">重置</button>' + helpBtn + '</div>';
      }
      const playBtn = isBeat ? '<button type="button" class="mus-btn js-play">播放</button>' : "";
      return '<div class="mus-actions">' + playBtn +
        '<button type="button" class="mus-btn mus-btn-submit js-submit">提交</button>' +
        '<button type="button" class="mus-btn js-reset">重置</button>' + helpBtn + '</div>';
    }

    function render() {
      initState();
      containerEl.classList.add("mus-sim");
      containerEl.innerHTML =
        '<div class="mus-status">' +
          '<span class="mus-attempts js-attempts">已尝试 0 次</span>' +
          '<span class="mus-result js-status"></span>' +
        '</div>' +
        '<div class="mus-stage">' + stageHTML() + '</div>' +
        '<div class="mus-toolbar">' +
          '<div class="mus-hint js-hint">' + hintText() + '</div>' + actionsHTML() +
        '</div>';

      els = {
        attempts: containerEl.querySelector(".js-attempts"),
        status: containerEl.querySelector(".js-status"),
        grid: containerEl.querySelector(".js-grid"),
        submit: containerEl.querySelector(".js-submit"),
        reset: containerEl.querySelector(".js-reset"),
        help: containerEl.querySelector(".js-help"),
        play: containerEl.querySelector(".js-play"),
        playBase: containerEl.querySelector(".js-play-base"),
        playTarget: containerEl.querySelector(".js-play-target"),
        playAnswer: containerEl.querySelector(".js-play-answer"),
        playChord: containerEl.querySelector(".js-play-chord"),
        playScale: containerEl.querySelector(".js-play-scale"),
      };

      wireEvents();
      syncStage();
      updateStatus();
      updateHUD();
      return inst;
    }

    function wireEvents() {
      if (els.submit) els.submit.onclick = () => submit();
      if (els.reset) els.reset.onclick = () => reset();
      if (els.help) els.help.onclick = () => { if (helpCallback) helpCallback(); };
      if (els.play) els.play.onclick = () => playCurrent();
      if (els.playBase) els.playBase.onclick = () => playTone(num(cfg.base_freq, 261.63), 0.8);
      if (els.playTarget) els.playTarget.onclick = () => playTone(num(cfg.base_freq, 261.63) * num(cfg.target_ratio, 1.5), 0.8);
      if (els.playAnswer) els.playAnswer.onclick = () => { if (state.ratio) playTone(num(cfg.base_freq, 261.63) * state.ratio, 0.8); };
      if (els.playChord) els.playChord.onclick = () => playChord(chordFreqs(num(cfg.base_freq, 261.63), state.voices));
      if (els.playScale) els.playScale.onclick = () => playTone((scaleNotes()[0] || 261.63) * state.mult, 0.8);

      if (els.grid) els.grid.addEventListener("click", onGridClick);

      containerEl.querySelectorAll(".js-beat-note").forEach(b => {
        b.onclick = () => { state.paintFreq = null; state.paintDur = Number(b.dataset.beat); refreshPaletteActive(); };
      });
      containerEl.querySelectorAll(".js-interval").forEach(b => {
        b.onclick = () => { state.ratio = Number(b.dataset.ratio); refreshPaletteActive(); updateStatus(); };
      });
      containerEl.querySelectorAll(".js-scale-mult").forEach(b => {
        b.onclick = () => {
          state.mult = Number(b.dataset.mult);
          refreshPaletteActive();
          if (els.playScale) els.playScale.textContent = "试听 ×" + state.mult;
          updateStatus();
        };
      });
      containerEl.querySelectorAll(".js-scale-note").forEach(b => {
        b.onclick = () => playTone(Number(b.dataset.freq), 0.6);
      });
      containerEl.querySelectorAll(".js-voice-dec").forEach(b => {
        b.onclick = () => stepVoice(Number(b.dataset.i), -1);
      });
      containerEl.querySelectorAll(".js-voice-inc").forEach(b => {
        b.onclick = () => stepVoice(Number(b.dataset.i), 1);
      });
      containerEl.querySelectorAll(".js-pitch").forEach(b => {
        b.onclick = () => { state.paintFreq = Number(b.dataset.freq); refreshPaletteActive(); playTone(state.paintFreq, 0.3); };
      });
      containerEl.querySelectorAll(".js-dur").forEach(b => {
        b.onclick = () => { state.paintDur = Number(b.dataset.dur); refreshPaletteActive(); };
      });
    }

    /* ---------------- 交互逻辑 ---------------- */
    function onGridClick(e) {
      const cell = e.target.closest(".mus-cell");
      if (!cell) return;
      const r = Number(cell.dataset.row), c = Number(cell.dataset.col);
      const k = r + "_" + c;
      if (isFree) {
        if (!state.paintFreq) { if (typeof toast === "function") toast("先选一个音高再点格子哦～", 2200); return; }
        if (state.notes[k] && state.notes[k].freq === state.paintFreq && state.notes[k].dur === state.paintDur) delete state.notes[k];
        else state.notes[k] = { freq: state.paintFreq, dur: state.paintDur };
      } else {
        if (state.notes[k] === state.paintDur) delete state.notes[k];
        else state.notes[k] = state.paintDur;
      }
      updateStatus();
      syncGrid();
    }

    function stepVoice(i, d) {
      state.voices[i] = clamp(state.voices[i] + d, 3, 6);
      const valEl = containerEl.querySelector('.js-voice-val[data-i="' + i + '"]');
      if (valEl) valEl.textContent = state.voices[i];
      updateStatus();
    }

    function playCurrent() {
      const rows = gridRows(), cols = gridCols();
      const items = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const v = state.notes[r + "_" + c];
          if (!v) continue;
          if (isFree) items.push({ freq: v.freq, beats: v.dur });
          else items.push({ freq: C_MAJOR[items.length % C_MAJOR.length], beats: v });
        }
      }
      if (!items.length) { if (typeof toast === "function") toast("先放几个音符再播放吧～", 2200); return; }
      playSequence(items);
    }

    /* ---------------- 渲染同步 ---------------- */
    function syncGrid() {
      if (!els.grid) return;
      const rows = gridRows(), cols = gridCols();
      let html = "";
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const k = r + "_" + c;
          const v = state.notes[k];
          let label = "", cls = "mus-cell";
          let desc = "空";
          if (v) {
            cls = "mus-cell mus-cell-on";
            if (isFree) { label = esc(freqName(v.freq)); desc = freqName(v.freq) + " " + beatLabel(v.dur); }
            else { label = beatGlyph(v); desc = beatLabel(v); }
          }
          html += '<button type="button" class="' + cls + '" data-row="' + r + '" data-col="' + c +
            '" aria-label="第' + (r + 1) + '行第' + (c + 1) + '列，' + desc + '">' + label + '</button>';
        }
      }
      els.grid.style.gridTemplateColumns = "repeat(" + cols + ", 1fr)";
      els.grid.innerHTML = html;
    }

    function refreshPaletteActive() {
      containerEl.querySelectorAll(".js-interval").forEach(b => {
        b.classList.toggle("active", state.ratio != null && Math.abs(Number(b.dataset.ratio) - state.ratio) < 0.001);
      });
      containerEl.querySelectorAll(".js-beat-note").forEach(b => {
        b.classList.toggle("active", Math.abs(Number(b.dataset.beat) - state.paintDur) < 0.001);
      });
      containerEl.querySelectorAll(".js-pitch").forEach(b => {
        b.classList.toggle("active", state.paintFreq != null && Math.abs(Number(b.dataset.freq) - state.paintFreq) < 0.001);
      });
      containerEl.querySelectorAll(".js-dur").forEach(b => {
        b.classList.toggle("active", Math.abs(Number(b.dataset.dur) - state.paintDur) < 0.001);
      });
      containerEl.querySelectorAll(".js-scale-mult").forEach(b => {
        b.classList.toggle("active", Math.abs(Number(b.dataset.mult) - state.mult) < 0.001);
      });
    }

    function syncStage() {
      syncGrid();
      refreshPaletteActive();
      if (mode === "chord") {
        state.voices.forEach((v, i) => {
          const valEl = containerEl.querySelector('.js-voice-val[data-i="' + i + '"]');
          if (valEl) valEl.textContent = v;
        });
      }
      if (els.playScale) els.playScale.textContent = "试听 ×" + state.mult;
    }

    /* ---------------- 进度 / 状态 ---------------- */
    function updateStatus() {
      if (!els.status) return;
      let text = "";
      if (isBeat) {
        text = "已拼 " + round1(currentBeats()) + " 拍 / 需要 " + round1(targetBeats()) + " 拍";
      } else if (mode === "interval") {
        text = state.ratio ? "你选：" + intervalLabel(state.ratio) : "请选择一个音程";
      } else if (mode === "chord") {
        text = "当前和弦比例 " + state.voices.join(" : ") + "（目标 4 : 5 : 6）";
      } else if (mode === "scale") {
        text = "你选：×" + state.mult + "（升一个八度要乘几？）";
      } else {
        text = "已放置 " + freeCount() + " 个音符";
      }
      if (state.hitResult) text = (state.hitResult.hit ? "完成！" : "还差一点，") + text;
      els.status.textContent = text;
    }

    function updateHUD() {
      if (els.attempts) els.attempts.textContent = "已尝试 " + state.attempts + " 次";
    }

    /* ---------------- 提交 / 判定 ---------------- */
    function compute() {
      if (isBeat) {
        const total = currentBeats();
        const target = targetBeats();
        const c = beatCompute(total, target);
        return Object.assign({ mode, total_beats: round1(total), target_beats: target }, c);
      }
      if (mode === "interval") {
        const sel = state.ratio || 0;
        const target = num(cfg.target_ratio, 1.5);
        const c = intervalCompute(sel, target);
        return Object.assign({ mode, ratio_sel: round1(sel), target_ratio: target }, c);
      }
      if (mode === "chord") {
        const target = [4, 5, 6];
        const c = chordCompute(state.voices, target);
        return Object.assign({ mode, voices: state.voices.slice(), target_ratio: "4:5:6" }, c);
      }
      if (mode === "scale") {
        const period = num(cfg.period_multiplier, 2);
        const c = scaleCompute(state.mult, period);
        return Object.assign({ mode, multiplier: state.mult, period_multiplier: period }, c);
      }
      const count = freeCount();
      return { hit: count >= 1, ratio: clamp(count / (gridRows() * gridCols()), 0, 1), mode: "free", notes: count };
    }

    function saveCreation(result) {
      const rows = gridRows(), cols = gridCols();
      const items = [];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const v = state.notes[r + "_" + c];
          if (v) items.push({ freq: v.freq, dur: v.dur });
        }
      }
      if (!items.length) return;
      const name = (typeof prompt === "function" ? prompt("给你的作品起个名字吧：", "我的旋律") : "我的旋律") || "我的旋律";
      const creations = readCreations();
      creations.push({ name: String(name), date: new Date().toISOString(), notes: items });
      writeCreations(creations);
      if (typeof toast === "function") toast("作品已保存！共 " + creations.length + " 件作品", 2800);
      result.name = String(name);
    }

    function submit() {
      if (isFree && freeCount() < 1) {
        if (typeof toast === "function") toast("先放几个音符再保存吧～", 2200);
        return;
      }
      state.attempts += 1;
      const result = compute();
      result.attempts = state.attempts;
      state.hitResult = { hit: result.hit };
      if (isFree) saveCreation(result);
      updateStatus();
      updateHUD();
      if (hitCallback) hitCallback(result);
    }

    function reset() {
      initState();
      syncStage();
      updateStatus();
      updateHUD();
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
      getContext() { return ensureCtx(); },
      getCreations() { return readCreations(); },
      destroy() {
        stopAll();
        containerEl.classList.remove("mus-sim");
        containerEl.innerHTML = "";
      },
    };

    return inst;
  }

  window.MusicSimulator = {
    createSimulator,
    INTERVALS,
    readCreations,
    _math: { clamp, beatCompute, intervalCompute, chordCompute, scaleCompute, freqForRatio, chordFreqs },
  };
})();
