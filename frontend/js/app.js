/* 小圆助教前端逻辑 */

const API = "";
let studentId = localStorage.getItem("xy_student_id") || null;
let sessionStartTime = null;
let timerInterval = null;
let currentView = "chat";

// ---------------------------------------------------------------- i18n
async function initI18n() {
  if (window.I18n) {
    await I18n.init();
    // Bind language switcher buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const lang = btn.getAttribute('data-lang');
        I18n.setLang(lang);
      });
    });
  }
}
initI18n();

// ---------------------------------------------------------------- 工具
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return document.querySelectorAll(sel); }

// ---------------------------------------------------------------- 主题系统
const THEME_META = {
  matcha: { name: "🍵 抹茶绿", swatch: "linear-gradient(135deg,#e7f0de 20%,#96bb85)" },
  pink: { name: "🌸 樱花粉", swatch: "linear-gradient(135deg,#ffe4e8 20%,#ffb6c1)" },
  lavender: { name: "💜 薰衣草", swatch: "linear-gradient(135deg,#ebe6f7 20%,#b4a6dc)" },
};

function cssVar(name, fallback = "") {
  const v = getComputedStyle(document.body).getPropertyValue(name).trim();
  return v || fallback;
}

function applyTheme(id, save = true) {
  if (!THEME_META[id]) id = "matcha";
  document.body.dataset.theme = id;
  if (save) localStorage.setItem("xy_theme", id);
  $all(".theme-card").forEach(c => c.classList.toggle("selected", c.dataset.theme === id));
}

function initThemeUI() {
  const grid = $("#theme-grid");
  grid.innerHTML = "";
  Object.entries(THEME_META).forEach(([id, meta]) => {
    const card = document.createElement("div");
    card.className = "theme-card";
    card.dataset.theme = id;
    card.innerHTML = `<div class="theme-swatch" style="background:${meta.swatch}"></div>
                      <div class="theme-name">${meta.name}</div>`;
    card.onclick = () => applyTheme(id);
    grid.appendChild(card);
  });
  $("#btn-settings").onclick = () => {
    $("#settings-overlay").classList.remove("hidden");
    loadApiKey();
  };
  $("#btn-settings-close").onclick = () => $("#settings-overlay").classList.add("hidden");
  $("#settings-overlay").addEventListener("click", e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add("hidden");
  });
  $("#btn-apikey-save").onclick = saveApiKey;
  applyTheme(localStorage.getItem("xy_theme") || "matcha", false);
}

async function loadApiKey() {
  try {
    const data = await api("/api/config", null, "GET");
    const input = $("#apikey-input");
    const status = $("#apikey-status");
    input.value = "";
    input.placeholder = data.has_key ? data.api_key_masked : "sk-xxxxxxxxxxxxxxxx";
    status.textContent = "";
    status.className = "apikey-status";
  } catch (_) { /* 静默 */ }
}

async function saveApiKey() {
  const input = $("#apikey-input");
  const status = $("#apikey-status");
  const key = input.value.trim();
  if (!key) { status.textContent = "请输入 API Key"; status.className = "apikey-status err"; return; }
  try {
    await api("/api/config", { api_key: key });
    status.textContent = "已保存！下次对话自动生效 ✅";
    status.className = "apikey-status ok";
    input.value = "";
    input.placeholder = (key.slice(0, 7) + "****" + key.slice(-4));
  } catch (e) {
    status.textContent = "保存失败：" + (e.message || "未知错误");
    status.className = "apikey-status err";
  }
}

async function api(path, body, method = "POST") {
  const resp = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let msg = "请求失败";
    try { msg = (await resp.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return resp.json();
}

function toast(text, ms = 2200) {
  const t = $("#toast");
  t.textContent = text;
  t.classList.remove("hidden");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), ms);
}

// ---------------------------------------------------------------- 档案
async function initProfile() {
  try {
    const students = await api("/api/students", null, "GET");
    if (studentId && students.some(s => s.id === studentId)) {
      enterApp();
      return;
    }
    renderStudentChips(students);
  } catch { /* 服务未起时静默 */ }
  $("#profile-overlay").classList.remove("hidden");
}

function renderStudentChips(students) {
  const wrap = $("#existing-students");
  wrap.innerHTML = "";
  students.forEach(s => {
    const div = document.createElement("div");
    div.className = "student-chip-wrap";
    const chip = document.createElement("button");
    chip.className = "student-chip";
    chip.textContent = s.name;
    chip.onclick = () => {
      studentId = s.id;
      localStorage.setItem("xy_student_id", studentId);
      enterApp();
    };
    const del = document.createElement("button");
    del.className = "student-del";
    del.title = "删除此账号";
    del.textContent = "×";
    del.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(`确定删除「${s.name}」的账号？所有学习记录都会丢失，删了就回不来了哦。`)) return;
      try {
        await api(`/api/student/${s.id}`, null, "DELETE");
        toast("已删除");
        initProfile();
      } catch (_) {
        toast("删除失败");
      }
    };
    div.appendChild(chip);
    div.appendChild(del);
    wrap.appendChild(div);
  });
}

$("#btn-create").onclick = async () => {
  const name = $("#new-name").value.trim();
  if (!name) { toast("给自己起个可爱的名字吧～"); return; }
  const res = await api("/api/student", { name });
  studentId = res.student_id;
  localStorage.setItem("xy_student_id", studentId);
  enterApp();
};

function enterApp() {
  $("#profile-overlay").classList.add("hidden");
  $("#mood-overlay").classList.remove("hidden");
  modeBarShown = false;  // 重置模式选择条状态
  $("#mode-modal").classList.add("hidden");  // 隐藏模式弹窗
  $("#mode-quick-bar").classList.add("hidden");  // 隐藏模式快捷栏
  $(".input-area").classList.remove("disabled");  // 始终可用
  $("#pomodoro-float").classList.add("hidden");  // 隐藏番茄钟
  const pc = document.getElementById("pomodoro-controls");
  if (pc) pc.classList.add("hidden");  // 隐藏控制面板
}

// ---------------------------------------------------------------- 心情打卡
$all(".mood-btn").forEach(btn => {
  btn.onclick = async () => {
    const mood = btn.dataset.mood;
    $("#mood-overlay").classList.add("hidden");
    $(".app").classList.remove("hidden");
    await startSession(mood);
  };
});

let modeBarShown = false;  // 跟踪模式选择条是否已显示

async function startSession(mood) {
  addMsg("ai", "……", true);
  try {
    const info = await api("/api/session/start", { student_id: studentId, mood });
    replaceLastAi(info.opening);
    startTimer();
    loadProgressHeader();
  // V-P0-3：开场白（情绪关怀）后显示模式快捷栏，输入框始终可用
  $("#mode-quick-bar").classList.remove("hidden");
} catch (e) {
    replaceLastAi(`哎呀连接出了点问题（${e.message}），刷新再试试？`);
  }
}

// ---------------------------------------------------------------- 聊天
function addMsg(role, text, typing = false) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="avatar">${role === "ai" ? "🐱" : "👧"}</div>
    <div class="bubble ${typing ? "typing-dot" : ""}">${typing ? "" : renderMathText(text)}</div>`;
  $("#chat-scroll").appendChild(div);
  scrollBottom();
  return div.querySelector(".bubble");
}

function scrollBottom() {
  const sc = $("#chat-scroll");
  sc.scrollTop = sc.scrollHeight;
}

function replaceLastAi(text) {
  const bubbles = $all("#chat-scroll .msg.ai .bubble");
  const last = bubbles[bubbles.length - 1];
  last.classList.remove("typing-dot");
  last.innerHTML = renderMathText(text);
}

const MODE_LABELS = { A: "🌟 深度成长", B: "🛡 保底维稳", weekend: "🧹 周末修复" };

// V-P0-3：模式快捷栏按钮点击 → 直接选择（不弹窗、不禁用输入）
$all(".mode-quick-btn").forEach(b => {
  b.onclick = () => {
    chooseMode(b.dataset.mode);
    $("#mode-quick-bar").classList.add("hidden");  // 选择后隐藏快捷栏
  };
});

// 模式选择弹窗按钮（备选入口）
$all(".mode-btn-modal").forEach(b => {
  b.onclick = () => chooseMode(b.dataset.mode);
});

async function chooseMode(mode) {
  const btns = $all(".mode-btn-modal");
  btns.forEach(b => b.disabled = true);
  try {
    const res = await api("/api/session/mode", { student_id: studentId, mode });
    // 关闭弹窗/快捷栏，输入框始终可用（不禁用）
    $("#mode-modal").classList.add("hidden");
    $("#mode-quick-bar").classList.add("hidden");
    if (modeBarShown) modeBarShown = false;
    if (res && res.prompt) addMsg("ai", res.prompt);
    btns.forEach(b => b.disabled = false);
    // 选完模式后显示番茄钟并自动开始计时
    $("#pomodoro-float").classList.remove("hidden");
    if (!pomodoroStarted) {
      pomodoroInterval = setInterval(tickPomodoro, 1000);
      pomodoroStarted = true;
      pomodoroStartBtn.textContent = "⏸";
    }
    toast(`已选「${MODE_LABELS[mode]}」，开始咯～`);
    $("#status-topic").textContent = `📌 今天学法：${MODE_LABELS[mode] || mode}`;
  } catch (e) {
    btns.forEach(b => b.disabled = false);
    toast("模式切换没成功（" + e.message + "），再点一次好吗？");
  }
}

async function consumeSSE(resp, bubble) {
  if (!resp.ok || !(resp.headers.get("content-type") || "").includes("text/event-stream")) {
    let detail = "";
    try { detail = (await resp.json()).detail || ""; } catch (_) { /* 非 JSON */ }
    throw new Error(detail || `服务开小差了（${resp.status}）`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let acc = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop();

    for (const raw of events) {
      const evMatch = raw.match(/^event: (.+)$/m);
      const dataMatch = raw.match(/^data: (.+)$/m);
      if (!evMatch || !dataMatch) continue;
      const type = evMatch[1].trim();
      const data = JSON.parse(dataMatch[1]);

      if (type === "text") {
        acc += data.content;
        bubble.classList.remove("typing-dot");
        bubble.innerHTML = renderMathText(acc);
        scrollBottom();
      } else if (type === "eval") {
        handleEval(data);
      } else if (type === "error") {
        bubble.classList.remove("typing-dot");
        bubble.innerHTML = renderMathText(data.message);
      }
    }
  }
  bubble.classList.remove("typing-dot");
  if (!acc && !bubble.textContent) {
    bubble.innerHTML = "（小圆刚才走神啦，再说一次好吗？）";
  }
}

// ---------------------------------------------------------------- 图片上传
async function sendPhoto(file) {
  const url = URL.createObjectURL(file);
  const userDiv = document.createElement("div");
  userDiv.className = "msg user";
  userDiv.innerHTML = `
    <div class="avatar">👧</div>
    <div class="bubble"><img class="photo-thumb" src="${url}" alt="题目照片"></div>`;
  $("#chat-scroll").appendChild(userDiv);
  scrollBottom();

  const bubble = addMsg("ai", "正在识别照片中的题目，稍等哦～", true);

  try {
    const fd = new FormData();
    fd.append("student_id", studentId);
    fd.append("file", file);
    const resp = await fetch("/api/chat/image", { method: "POST", body: fd });
    await consumeSSE(resp, bubble);
  } catch (e) {
    bubble.classList.remove("typing-dot");
    bubble.innerHTML = e && e.message
      ? renderMathText(`照片识别出了点状况：${e.message}`)
      : "网络开小差了，再试一次好吗？";
  } finally {
    URL.revokeObjectURL(url);
  }
}

// 加号菜单
$("#btn-plus").onclick = () => {
  $("#plus-menu").classList.toggle("hidden");
};
$("#btn-photo").onclick = () => {
  $("#plus-menu").classList.add("hidden");
  $("#photo-input").click();
};
$("#photo-input").addEventListener("change", e => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file) sendPhoto(file);
});
// 点击其他地方关闭菜单
document.addEventListener("click", e => {
  if (!e.target.closest("#btn-plus") && !e.target.closest("#plus-menu")) {
    $("#plus-menu").classList.add("hidden");
  }
});

async function sendChat() {
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";

  // 认知评估模式拦截
  if (input.dataset.assessmentMode === "true") {
    addMsg("user", text);
    submitAssessmentAnswer(text);
    input.focus();
    return;
  }

  addMsg("user", text);

  const bubble = addMsg("ai", "", true);

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, message: text }),
    });
    await consumeSSE(resp, bubble);
  } catch (e) {
    bubble.classList.remove("typing-dot");
    bubble.innerHTML = e && e.message && !e.message.includes("Failed to fetch")
      ? renderMathText(`小圆这边有点状况：${e.message}。稍等一下再试好吗？`)
      : "网络好像开小差了，检查一下再试好吗？";
  } finally {
    input.focus();
  }
}

$("#chat-input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function handleEval(data) {
  if (data.badges && data.badges.length) {
    data.badges.forEach(b => {
      toast(`🎉 获得新徽章：${b}`, 3200);
      celebrate();
    });
  }
  // V-P1-2 思维模型显式化：状态栏显示思维方法标签
  updateThinkingModelTag(data);
  if (data.emotion === "confident") {
    updateConfidenceBar(0.85);
  } else if (data.emotion) {
    loadProgressHeader();
  }
}

// 思维模型 ID → 中文名映射
const THINKING_MODEL_NAMES = {
  reverse: "逆向思维", visualization: "图形化思维", decomposition: "问题拆分",
  analogy: "类比思维", transformation: "转化思维", case_analysis: "分类讨论",
  extreme: "极端思维", holistic: "整体思维", modeling: "建模思维", verification: "检验思维",
};

function updateThinkingModelTag(data) {
  const tag = $("#thinking-model-tag");
  if (!tag) return;
  // 学生主动提出的模型优先高亮显示
  const mid = data.student_initiated_model || data.used_thinking_model;
  if (mid && THINKING_MODEL_NAMES[mid]) {
    const initiated = Boolean(data.student_initiated_model);
    tag.textContent = `🧩 ${THINKING_MODEL_NAMES[mid]}${initiated ? "（你想到的！）" : ""}`;
    tag.classList.remove("hidden");
    tag.style.opacity = 1;
    clearTimeout(tag._tm);
    tag._tm = setTimeout(() => { tag.style.opacity = 0; }, 4000);
    setTimeout(() => tag.classList.add("hidden"), 4500);
  } else {
    tag.classList.add("hidden");
    tag.style.opacity = 0;
  }
}

// ---------------------------------------------------------------- 计时与状态栏
function startTimer() {
  sessionStartTime = Date.now();
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const mins = Math.floor((Date.now() - sessionStartTime) / 60000);
    $("#status-time").textContent = `⏱ ${mins}分钟`;
    // 深度模式15分钟后提示收尾
    if (mins >= 15 && !window._wrapHinted) {
      window._wrapHinted = true;
      toast("和小圆聊了挺久啦，记得说「今天就到这里」收个尾巴哦🌙");
    }
  }, 15000);
  $("#status-time").textContent = "⏱ 0分钟";
}

// ---------------------------------------------------------------- 番茄闹钟（悬浮图标）
const POMODORO_WORK = 25 * 60;  // 25分钟
const POMODORO_BREAK = 5 * 60;  // 5分钟
let pomodoroInterval = null;
let pomodoroTimeLeft = POMODORO_WORK;
let pomodoroIsWork = true;
let pomodoroStarted = false;
const pomodoroRing = $("#pomodoro-ring-fg");
const pomodoroText = $("#pomodoro-text");
const pomodoroLabel = $("#pomodoro-label");
const pomodoroFloat = $("#pomodoro-float");
const circumference = 2 * Math.PI * 18; // r=18

// 创建控制面板
const pomodoroControls = document.createElement("div");
pomodoroControls.className = "pomodoro-controls hidden";
pomodoroControls.id = "pomodoro-controls";
pomodoroControls.innerHTML = `
  <button id="pomodoro-start" title="开始/暂停">▶</button>
  <button id="pomodoro-reset" title="重置">↺</button>
`;
document.body.appendChild(pomodoroControls);

const pomodoroStartBtn = $("#pomodoro-start");
const pomodoroResetBtn = $("#pomodoro-reset");

function updatePomodoroDisplay() {
  const mins = Math.floor(pomodoroTimeLeft / 60);
  const secs = pomodoroTimeLeft % 60;
  pomodoroText.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  const total = pomodoroIsWork ? POMODORO_WORK : POMODORO_BREAK;
  const progress = pomodoroTimeLeft / total;
  pomodoroRing.style.strokeDashoffset = circumference * (1 - progress);
  pomodoroLabel.textContent = pomodoroIsWork ? "学" : "息";
}

function tickPomodoro() {
  if (pomodoroTimeLeft <= 0) {
    clearInterval(pomodoroInterval);
    pomodoroInterval = null;
    pomodoroStarted = false;
    // 切换学习/休息
    if (pomodoroIsWork) {
      pomodoroIsWork = false;
      pomodoroTimeLeft = POMODORO_BREAK;
      pomodoroFloat.classList.add("break-mode");
      toast("学了25分钟啦！休息5分钟吧～站起来走走🫧");
    } else {
      pomodoroIsWork = true;
      pomodoroTimeLeft = POMODORO_WORK;
      pomodoroFloat.classList.remove("break-mode");
      toast("休息结束！准备好了就继续吧💪");
    }
    updatePomodoroDisplay();
    pomodoroStartBtn.textContent = "▶";
    return;
  }
  pomodoroTimeLeft--;
  updatePomodoroDisplay();
}

// 点击悬浮图标：展开/收起控制面板
pomodoroFloat.onclick = () => {
  pomodoroControls.classList.toggle("hidden");
};

// 开始/暂停
pomodoroStartBtn.onclick = (e) => {
  e.stopPropagation();
  if (pomodoroInterval) {
    clearInterval(pomodoroInterval);
    pomodoroInterval = null;
    pomodoroStarted = false;
    pomodoroStartBtn.textContent = "▶";
  } else {
    pomodoroInterval = setInterval(tickPomodoro, 1000);
    pomodoroStarted = true;
    pomodoroStartBtn.textContent = "⏸";
    pomodoroControls.classList.add("hidden");  // 开始后自动收起
  }
};

// 重置
pomodoroResetBtn.onclick = (e) => {
  e.stopPropagation();
  clearInterval(pomodoroInterval);
  pomodoroInterval = null;
  pomodoroStarted = false;
  pomodoroIsWork = true;
  pomodoroTimeLeft = POMODORO_WORK;
  pomodoroFloat.classList.remove("break-mode");
  updatePomodoroDisplay();
  pomodoroStartBtn.textContent = "▶";
  pomodoroControls.classList.add("hidden");
};

updatePomodoroDisplay();

async function loadProgressHeader() {
  try {
    const p = await api(`/api/student/${studentId}/progress`, null, "GET");
    $("#streak-num").textContent = p.streak_chain;
    const conf = p.confidence_trend.length ? Math.round(p.confidence_trend[p.confidence_trend.length-1] * 100) : null;
    $("#status-confidence").textContent = conf === null ? "💪 --" : `💪 ${conf}%`;
  } catch {}
}

function updateConfidenceBar(v) {
  $("#status-confidence").textContent = `💪 ${Math.round(v * 100)}%`;
}

// ---------------------------------------------------------------- 视图切换
$all(".tab").forEach(tab => {
  tab.onclick = () => {
    $all(".tab").forEach(t => t.classList.remove("active"));
    $all(".view").forEach(v => v.classList.remove("active"));
    tab.classList.add("active");
    $(`#view-${tab.dataset.view}`).classList.add("active");
    currentView = tab.dataset.view;
    if (currentView === "sky") renderMindmap();
    if (currentView === "badges") renderBadges();
    if (currentView === "cognitive") renderCognitiveProfile();
  };
});

// ---------------------------------------------------------------- 知识脑图
let knowledgeTree = null;
let mindmapExpanded = {};  // 记录哪些年级展开了

async function renderMindmap() {
  knowledgeTree = await api(`/api/knowledge/tree?student_id=${studentId}`, null, "GET");
  const container = $("#mindmap");
  container.innerHTML = "";

  // 将 chapters 格式转为扁平列表
  const allNodes = [];
  for (const [chapter, nodes] of Object.entries(knowledgeTree.chapters)) {
    nodes.forEach(n => {
      n.chapter = chapter;  // 补充 chapter 字段
      allNodes.push(n);
    });
  }

  // 按年级分组
  const gradeMap = {};
  allNodes.forEach(n => {
    const grade = getGrade(n.chapter);
    if (!gradeMap[grade]) gradeMap[grade] = { chapters: {} };
    if (!gradeMap[grade].chapters[n.chapter]) gradeMap[grade].chapters[n.chapter] = [];
    gradeMap[grade].chapters[n.chapter].push(n);
  });

  const gradeOrder = ["小学回顾", "六年级", "七年级", "八年级", "九年级", "高中"];
  const gradeNames = {
    "小学回顾": "📚 小学回顾（1-5年级）",
    "六年级": "📖 六年级",
    "七年级": "📗 七年级",
    "八年级": "📘 八年级",
    "九年级": "📙 九年级",
    "高中": "🎓 高中（10-12年级）",
  };

  for (const grade of gradeOrder) {
    const data = gradeMap[grade];
    if (!data) continue;

    const totalTopics = Object.values(data.chapters).flat().length;
    const masteredCount = Object.values(data.chapters).flat().filter(n => n.mastery >= 0.8).length;

    const div = document.createElement("div");
    div.className = "mm-grade";

    if (mindmapExpanded[grade] === undefined) {
      mindmapExpanded[grade] = gradeOrder.indexOf(grade) <= 1;
    }

    div.innerHTML = `
      <div class="mm-grade-header" data-grade="${grade}">
        <span class="mm-grade-arrow ${mindmapExpanded[grade] ? 'open' : ''}">▶</span>
        <span class="mm-grade-name">${gradeNames[grade] || grade}</span>
        <span class="mm-grade-badge">${masteredCount}/${totalTopics} 掌握</span>
      </div>
      <div class="mm-chapters ${mindmapExpanded[grade] ? 'open' : ''}"></div>
    `;

    const chaptersDiv = div.querySelector(".mm-chapters");
    const chapterOrder = Object.keys(data.chapters).sort((a, b) => {
      const cnNum = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10};
      const na = a.match(/第(.+?)章/);
      const nb = b.match(/第(.+?)章/);
      const va = na ? (cnNum[na[1]] || parseInt(na[1]) || 0) : 0;
      const vb = nb ? (cnNum[nb[1]] || parseInt(nb[1]) || 0) : 0;
      return va - vb;
    });

    for (const chapter of chapterOrder) {
      const nodes = data.chapters[chapter];
      const chDiv = document.createElement("div");
      chDiv.className = "mm-chapter";
      chDiv.innerHTML = `<div class="mm-chapter-name">${chapter}</div>`;
      const topicsDiv = document.createElement("div");
      topicsDiv.className = "mm-topics";

      nodes.forEach(n => {
        const mastery = n.mastery || 0;
        const hasGap = n.has_open_gap;
        let dotClass = "none";
        if (hasGap) dotClass = "weak";
        else if (mastery >= 0.8) dotClass = "mastered";
        else if (mastery >= 0.3) dotClass = "learning";

        const topic = document.createElement("div");
        topic.className = "mm-topic";
        topic.dataset.id = n.id;
        topic.innerHTML = `
          <span class="mm-dot ${dotClass}"></span>
          <span class="mm-topic-name">${n.name}</span>
          ${n.is_core ? '<span style="font-size:10px">⭐</span>' : ''}
        `;
        topic.addEventListener("click", () => showTopicDetail(n));
        topicsDiv.appendChild(topic);
      });

      chDiv.appendChild(topicsDiv);
      chaptersDiv.appendChild(chDiv);
    }

    // 折叠/展开
    div.querySelector(".mm-grade-header").addEventListener("click", () => {
      const arrow = div.querySelector(".mm-grade-arrow");
      const chapters = div.querySelector(".mm-chapters");
      const isOpen = chapters.classList.toggle("open");
      arrow.classList.toggle("open", isOpen);
      mindmapExpanded[grade] = isOpen;
    });

    container.appendChild(div);
  }
}

function getGrade(chapter) {
  if (chapter.includes("小学")) return "小学回顾";
  if (chapter.includes("六")) return "六年级";
  if (chapter.includes("七")) return "七年级";
  if (chapter.includes("八")) return "八年级";
  if (chapter.includes("九")) return "九年级";
  if (chapter.includes("高中")) return "高中";
  return "其他";
}

function showTopicDetail(n) {
  const pct = Math.round((n.mastery || 0) * 100);
  $("#td-title").textContent = `${n.name} ${n.is_core ? "⭐核心" : ""}`;
  $("#td-body").innerHTML = `
    <p><b>${n.chapter}</b> ｜ 难度 ${"🌸".repeat(n.difficulty)}</p>
    <p>掌握度</p>
    <div class="meter"><div class="meter-fill" style="width:${pct}%"></div></div>
    <p style="color:var(--muted)">${pct}%</p>
    ${n.has_open_gap ? '<p style="color:#d4637a">💫 这里有个小漏洞待修复</p>' : ""}
    ${pct >= 80 ? '<p style="color:#7fbf7f">✨ 这块积木搭得很稳！</p>' : ""}
    ${n.common_mistakes?.length ? `<p style="margin-top:8px"><b>常见误区：</b>${n.common_mistakes.join("；")}</p>` : ""}
    ${n.life_examples?.length ? `<p><b>生活例子：</b>${n.life_examples.join("，")}</p>` : ""}
  `;
  $("#topic-detail").classList.remove("hidden");
}
function hideTopicDetail() { $("#topic-detail").classList.add("hidden"); }

// ---------------------------------------------------------------- 徽章墙
async function renderBadges() {
  const p = await api(`/api/student/${studentId}/progress`, null, "GET");
  $("#stat-sessions").textContent = p.total_sessions;
  $("#stat-gaps").textContent = p.open_gaps.length;
  $("#stat-mastery").textContent = Math.round(p.avg_mastery * 100) + "%";

  // 徽章网格
  const grid = $("#badge-grid");
  grid.innerHTML = "";
  Object.entries(p.badges_all).forEach(([name, info]) => {
    const earned = p.badges_earned.includes(name);
    const div = document.createElement("div");
    div.className = `badge-item ${earned ? "" : "locked"}`;
    div.innerHTML = `
      <div class="badge-icon">${info.icon}</div>
      <div class="badge-name">${name}</div>
      <div class="badge-desc">${earned ? "已解锁！" : info.desc}</div>`;
    grid.appendChild(div);
  });

  // 漏洞清单
  const ul = $("#gap-list");
  ul.innerHTML = "";
  if (!p.open_gaps.length) {
    ul.innerHTML = '<div class="empty-hint">太棒了！目前没有待修复的漏洞 🎉</div>';
  } else {
    p.open_gaps.forEach(g => {
      const li = document.createElement("li");
      li.className = "gap-item";
      li.innerHTML = `
        <span class="gap-tag ${g.type}">${g.type === "concept" ? "概念漏洞" : "粗心标记"}</span>
        <span><b>${g.topic_name}</b> — ${escapeHtml(g.evidence || "细节待补充")}</span>`;
      ul.appendChild(li);
    });
  }

  drawConfidenceChart(p.confidence_trend);

  // 学习记录
  renderHistory();

  // V-P2-1 周学习报告
  try {
    const report = await api(`/api/student/${studentId}/weekly-report`, null, "GET");
    renderWeeklyReport(report);
  } catch (_) { /* 静默 */ }
}

function renderWeeklyReport(report) {
  const delta = report.vs_last_week || {};
  const deltaMinutes = delta.minutes_delta || 0;
  const deltaDays = delta.days_delta || 0;

  const minutesText = report.study_minutes >= 60
    ? `${Math.floor(report.study_minutes / 60)}小时${report.study_minutes % 60}分`
    : `${report.study_minutes}分钟`;

  const deltaMinutesText = deltaMinutes > 0
    ? `<span style="color:#4caf50">↑${deltaMinutes}分</span>`
    : deltaMinutes < 0
      ? `<span style="color:#f44336">↓${Math.abs(deltaMinutes)}分</span>`
      : `<span style="color:#999">持平</span>`;

  const html = `
    <div class="weekly-report-card">
      <h3 class="section-title">📊 本周进步（${report.week_start} ~ ${report.week_end}）</h3>
      <div class="weekly-stats">
        <div class="weekly-stat">
          <div class="weekly-stat-num">${report.study_days}</div>
          <div class="weekly-stat-label">学习天数</div>
          <div class="weekly-stat-delta">${deltaDays > 0 ? '↑' : deltaDays < 0 ? '↓' : '—'}${Math.abs(deltaDays || 0)}天</div>
        </div>
        <div class="weekly-stat">
          <div class="weekly-stat-num">${minutesText}</div>
          <div class="weekly-stat-label">学习时长</div>
          <div class="weekly-stat-delta">${deltaMinutesText}</div>
        </div>
        <div class="weekly-stat">
          <div class="weekly-stat-num">${report.mastered_count}</div>
          <div class="weekly-stat-label">掌握知识点</div>
        </div>
        <div class="weekly-stat">
          <div class="weekly-stat-num">${report.new_badges.length}</div>
          <div class="weekly-stat-label">本周新徽章</div>
        </div>
      </div>
      ${report.streak_chain >= 3 ? `<div class="streak-celebrate">🔥 连续学习${report.streak_chain}天，太棒了！</div>` : ''}
    </div>
  `;

  const badgesView = document.getElementById('view-badges');
  const existing = document.getElementById('weekly-report-container');
  if (existing) existing.remove();
  const container = document.createElement('div');
  container.id = 'weekly-report-container';
  container.innerHTML = html;
  badgesView.insertBefore(container, badgesView.querySelector('.badge-stats').nextSibling);
}

async function renderHistory() {
  const wrap = $("#history-list");
  if (!wrap) return;
  try {
    const res = await api(`/api/student/${studentId}/history`, null, "GET");
    if (!res.sessions.length) {
      wrap.innerHTML = '<div class="history-empty">还没开始学，第一次学完这里就有记录啦 🌱</div>';
      return;
    }
    wrap.innerHTML = "";
    res.sessions.forEach((s, idx) => {
      const spots = s.blind_spots.length
        ? `<div class="history-spots">🔍 发现盲区：${s.blind_spots.map(b => escapeHtml(b)).join("、")}</div>`
        : "";
      const badges = s.new_badges.length
        ? `<span>🏅 ${s.new_badges.length}枚</span>`
        : "";
      const dur = s.duration_minutes > 0 ? `<span>⏱ ${s.duration_minutes}分钟</span>` : "";
      const div = document.createElement("div");
      div.className = "history-item";
      div.style.cursor = "pointer";
      div.onclick = (e) => { if (!e.target.closest(".hist-del")) openHistoryDetail(s); };
      div.innerHTML = `
        <button class="hist-del" title="删除此记录" onclick="event.stopPropagation();deleteHistory(${idx})">×</button>
        <div class="history-date">
          <span>${s.date}</span>
          <span class="history-mode">${s.mode}</span>
        </div>
        <div class="history-topic">${escapeHtml(s.topic_name)}</div>
        <div class="history-meta">
          <span>💬 ${s.turns}轮对话</span>
          ${dur}
          ${badges}
        </div>
        ${spots}`;
      wrap.appendChild(div);
    });
  } catch (_) {
    wrap.innerHTML = '<div class="history-empty">加载中…</div>';
  }
}

function openHistoryDetail(session) {
  const overlay = $("#history-overlay");
  const title = $("#hd-title");
  const meta = $("#hd-meta");
  const msgs = $("#hd-messages");
  const spots = $("#hd-spots");

  title.textContent = `${session.date}  ${session.topic_name}`;
  meta.innerHTML = `
    <span>${session.mode}</span>
    <span>💬 ${session.turns}轮</span>
    ${session.duration_minutes ? `<span>⏱ ${session.duration_minutes}分钟</span>` : ""}
    ${session.mood ? `<span>${session.mood}</span>` : ""}`;

  msgs.innerHTML = "";
  if (session.messages && session.messages.length) {
    session.messages.forEach(m => {
      const isUser = m.role === "user";
      const div = document.createElement("div");
      div.className = isUser ? "hm-user" : "hm-ai";
      div.innerHTML = `<div class="hm-role">${isUser ? "👧 学生" : "🐱 小圆"}</div>${renderMathText(m.content)}`;
      msgs.appendChild(div);
    });
  } else {
    msgs.innerHTML = '<div class="history-empty">这段对话没有详细记录</div>';
  }

  if (session.blind_spots && session.blind_spots.length) {
    spots.classList.remove("hidden");
    spots.innerHTML = `<b>🔍 发现的盲区：</b>${session.blind_spots.map(b => escapeHtml(b)).join("、")}`;
  } else {
    spots.classList.add("hidden");
  }

  overlay.classList.remove("hidden");
}

function closeHistoryDetail() {
  $("#history-overlay").classList.add("hidden");
}

async function deleteHistory(idx) {
  if (!confirm("确定删除这条学习记录？删除后无法恢复哦。")) return;
  try {
    await api("/api/student/history/delete", { student_id: studentId, index: idx });
    renderHistory();
    toast("记录已删除");
  } catch (_) {
    toast("删除失败，再试一次？");
  }
}

$("#history-overlay").addEventListener("click", e => {
  if (e.target === e.currentTarget) closeHistoryDetail();
});

function drawConfidenceChart(values) {
  const canvas = $("#confidence-chart");
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth || 600;
  canvas.width = W * dpr; canvas.height = 120 * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, 120);

  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, 120);

  if (!values || values.length < 2) {
    ctx.fillStyle = cssVar("--muted", "#bdaab0"); ctx.font = "13px sans-serif"; ctx.textAlign = "center";
    ctx.fillText("继续学习两次以上，这里会出现你的信心曲线 🌱", W/2, 62);
    return;
  }
  const lineColor = cssVar("--main-strong", "#ff9eb0");
  const maxV = Math.max(...values), minV = Math.min(...values);
  const range = Math.max(maxV - minV, 0.1);
  const px = i => 30 + (i / (values.length - 1)) * (W - 50);
  const py = v => 100 - ((v - minV) / range) * 76;

  // 渐变填充
  const grad = ctx.createLinearGradient(0, 20, 0, 110);
  grad.addColorStop(0, hexToRgba(lineColor, .35));
  grad.addColorStop(1, hexToRgba(lineColor, 0));
  ctx.beginPath();
  ctx.moveTo(px(0), py(values[0]));
  values.forEach((v, i) => ctx.lineTo(px(i), py(v)));
  ctx.lineTo(px(values.length-1), 108); ctx.lineTo(px(0), 108); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  // 折线
  ctx.beginPath();
  values.forEach((v, i) => i === 0 ? ctx.moveTo(px(i), py(v)) : ctx.lineTo(px(i), py(v)));
  ctx.strokeStyle = lineColor; ctx.lineWidth = 2.5; ctx.stroke();

  // 点
  values.forEach((v, i) => {
    ctx.beginPath(); ctx.arc(px(i), py(v), 3.5, 0, Math.PI*2);
    ctx.fillStyle = "#fff"; ctx.fill(); ctx.stroke();
  });
}

function hexToRgba(hex, alpha) {
  let h = hex.replace("#", "");
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  const n = parseInt(h, 16);
  return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${alpha})`;
}

// ---------------------------------------------------------------- 庆祝动效
function celebrate() {
  const canvas = $("#celebrate-canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = innerWidth; canvas.height = innerHeight;
  const parts = Array.from({ length: 60 }, () => ({
    x: Math.random() * canvas.width,
    y: -20 - Math.random() * canvas.height * .5,
    vy: 2 + Math.random() * 3,
    vx: (Math.random() - .5) * 1.5,
    size: 6 + Math.random() * 8,
    rot: Math.random() * Math.PI * 2,
    vr: (Math.random() - .5) * .2,
    color: [
      cssVar("--main", "#96bb85"),
      cssVar("--main-strong", "#83ab72"),
      cssVar("--accent", "#7ca26c"),
      "#ffd700",
    ][Math.floor(Math.random()*4)],
  }));
  let frames = 0;
  (function tick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    parts.forEach(p => {
      p.y += p.vy; p.x += p.vx; p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      drawStarShape(ctx, 0, 0, p.size, 4); ctx.fill();
      ctx.restore();
    });
    frames++;
    if (frames < 130) requestAnimationFrame(tick);
    else ctx.clearRect(0, 0, canvas.width, canvas.height);
  })();
}

// ---------------------------------------------------------------- 结束会话
let loggingOut = false;

$("#btn-logout").onclick = async () => {
  if (loggingOut) return;
  if (!confirm("要和小圆说再见吗？今天的对话会自动保存哦～")) return;
  loggingOut = true;
  try {
    if (studentId && sessionStartTime) {
      await api("/api/session/end", { student_id: studentId });
    }
  } catch (_) { /* 归档失败也不阻塞退出 */ }
  sessionStartTime = null;
  localStorage.removeItem("xy_student_id");
  location.reload();
};

window.addEventListener("beforeunload", () => {
  if (studentId && sessionStartTime && !loggingOut && navigator.sendBeacon) {
    navigator.sendBeacon(
      `/api/session/end-beacon?student_id=${studentId}`,
      new Blob([], { type: "application/json" })
    );
  }
});

// ---------------------------------------------------------------- 认知画像（EP-P2-3）
let cognitiveData = null;

async function renderCognitiveProfile() {
  if (!studentId) return;
  try {
    cognitiveData = await api(`/api/cognitive-profile?student_id=${studentId}`, null, "GET");
  } catch (_) { return; }

  if (!cognitiveData.has_profile) {
    $("#cognitive-empty").classList.remove("hidden");
    $("#cognitive-profile").classList.add("hidden");
    $("#btn-start-assessment").onclick = startCognitiveAssessment;
    return;
  }

  $("#cognitive-empty").classList.add("hidden");
  $("#cognitive-profile").classList.remove("hidden");
  drawCognitiveRadar(cognitiveData);
  renderCognitiveDetails(cognitiveData);
  renderDomainBars(cognitiveData.domain_levels || {});
}

function drawCognitiveRadar(data) {
  const canvas = $("#cognitive-radar");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  const R = Math.min(W, H) / 2 - 40;
  ctx.clearRect(0, 0, W, H);

  const dims = [
    { label: "\u62bd\u8c61\u601d\u7ef4", value: data.abstract_thinking || 0 },
    { label: "\u5143\u8ba4\u77e5", value: data.metacognition_level || 0 },
    { label: "\u6291\u5236\u63a7\u5236", value: (data.executive_function || {}).inhibition || 0 },
    { label: "\u8ba4\u77e5\u7075\u6d3b", value: (data.executive_function || {}).flexibility || 0 },
    { label: "\u4f4e\u7126\u8651", value: 1 - (data.math_anxiety || 0) },
  ];
  const n = dims.length;
  const step = (Math.PI * 2) / n;

  for (let layer = 1; layer <= 5; layer++) {
    const r = (R * layer) / 5;
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const a = -Math.PI / 2 + step * i;
      const x = cx + r * Math.cos(a);
      const y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "rgba(0,0,0,0.08)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + step * i;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
    ctx.strokeStyle = "rgba(0,0,0,0.1)";
    ctx.stroke();
  }

  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const idx = i % n;
    const a = -Math.PI / 2 + step * idx;
    const r = R * Math.max(0.05, dims[idx].value);
    const x = cx + r * Math.cos(a);
    const y = cy + r * Math.sin(a);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.fillStyle = "rgba(76,175,80,0.25)";
  ctx.fill();
  ctx.strokeStyle = "#4caf50";
  ctx.lineWidth = 2;
  ctx.stroke();

  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + step * i;
    const r = R * Math.max(0.05, dims[i].value);
    ctx.beginPath();
    ctx.arc(cx + r * Math.cos(a), cy + r * Math.sin(a), 4, 0, Math.PI * 2);
    ctx.fillStyle = "#4caf50";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  ctx.fillStyle = "#333";
  ctx.font = "13px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 + step * i;
    ctx.fillText(dims[i].label, cx + (R + 22) * Math.cos(a), cy + (R + 22) * Math.sin(a));
  }
}

function renderCognitiveDetails(data) {
  const stageMap = {
    concrete: "\u5177\u4f53\u8fd0\u7b97\uff08\u9700\u8981\u753b\u56fe/\u5b9e\u7269\u652f\u6491\uff09",
    transitional: "\u8fc7\u6e21\u671f\uff08\u90e8\u5206\u53ef\u62bd\u8c61\u63a8\u7406\uff09",
    formal: "\u5f62\u5f0f\u8fd0\u7b97\uff08\u7eaf\u62bd\u8c61\u63a8\u7406\uff09",
  };
  const wmMap = { low: "\u8f83\u4f4e\uff08\u4e00\u6b211-2\u6b65\uff09", medium: "\u4e2d\u7b49\uff08\u4e00\u6b212-3\u6b65\uff09", high: "\u8f83\u9ad8\uff08\u4e00\u6b213\u6b65+\uff09" };
  const prefMap = { visual: "\u89c6\u89c9\u578b\uff08\u753b\u56fe/\u56fe\u8868\uff09", verbal: "\u8bed\u8a00\u578b\uff08\u542c\u8bb2\u89e3\uff09", kinesthetic: "\u52a8\u89c9\u578b\uff08\u52a8\u624b\u64cd\u4f5c\uff09" };

  const items = [
    { label: "\u8ba4\u77e5\u9636\u6bb5", value: stageMap[data.cognitive_stage] || data.cognitive_stage },
    { label: "\u5de5\u4f5c\u8bb0\u5fc6", value: wmMap[data.working_memory_capacity] || data.working_memory_capacity },
    { label: "\u5b66\u4e60\u504f\u597d", value: prefMap[data.learning_preference] || data.learning_preference },
    { label: "\u6570\u5b66\u7126\u8651", value: Math.round((data.math_anxiety || 0) * 100) + "%" },
    { label: "\u8bc4\u4f30\u7f6e\u4fe1\u5ea6", value: Math.round((data.assessment_confidence || 0) * 100) + "%" },
  ];

  $("#cognitive-details").innerHTML = items.map(function(it) {
    return '<div class="cognitive-item"><span class="cognitive-label">' + it.label + '</span><span class="cognitive-value">' + it.value + '</span></div>';
  }).join("");
}

function renderDomainBars(domainLevels) {
  var container = $("#domain-bars");
  if (!domainLevels || Object.keys(domainLevels).length === 0) {
    container.innerHTML = '<div class="cognitive-item"><span class="cognitive-value" style="color:#999">\u6682\u65e0\u6570\u636e\uff0c\u5b66\u4e60\u540e\u4f1a\u81ea\u52a8\u66f4\u65b0</span></div>';
    return;
  }
  var names = { algebra: "\u4ee3\u6570", geometry: "\u51e0\u4f55", number_theory: "\u6570\u8bba", stats: "\u7edf\u8ba1", general: "\u7efc\u5408" };
  container.innerHTML = Object.entries(domainLevels).map(function(pair) {
    var k = pair[0], v = pair[1];
    var name = names[k] || k;
    var pct = Math.round(v * 100);
    var color = v >= 0.7 ? "#4caf50" : v >= 0.4 ? "#ffc107" : "#f44336";
    return '<div class="domain-bar-row"><span class="domain-bar-label">' + name + '</span><div class="domain-bar-track"><div class="domain-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div><span class="domain-bar-pct">' + pct + '%</span></div>';
  }).join("");
}

var assessmentState = { questionId: null, order: 0, total: 6 };

async function startCognitiveAssessment() {
  var resp = await api("/api/cognitive-assessment/next?student_id=" + studentId, null, "GET");
  if (resp.completed) {
    toast("\u8bc4\u4f30\u5df2\u5b8c\u6210\uff01");
    renderCognitiveProfile();
    return;
  }
  showAssessmentQuestion(resp);
}

function showAssessmentQuestion(q) {
  assessmentState = { questionId: q.question_id, order: q.order, total: q.total };
  addMsg("ai", "\ud83d\udccb \u8ba4\u77e5\u8bca\u65ad\uff08" + q.order + "/" + q.total + "\uff09\n\n" + q.question);
  var input = $("#chat-input");
  input.placeholder = "\u8bf4\u8bf4\u4f60\u7684\u60f3\u6cd5\uff5e";
  input.dataset.assessmentMode = "true";
}

async function submitAssessmentAnswer(answer) {
  var resp = await api("/api/cognitive-assessment/submit", {
    student_id: studentId,
    question_id: assessmentState.questionId,
    answer: answer,
  });
  if (resp.completed) {
    addMsg("ai", "\u2728 \u8bc4\u4f30\u5b8c\u6210\uff01" + (resp.summary || ""));
    $("#chat-input").dataset.assessmentMode = "";
    $("#chat-input").placeholder = "\u548c\u5c0f\u5706\u8bf4\u70b9\u4ec0\u4e48\u2026";
    renderCognitiveProfile();
    return;
  }
  showAssessmentQuestion({ question_id: resp.next_question_id, question: resp.next_question, order: resp.order, total: 6 });
}

// ---------------------------------------------------------------- 语音输入（V-P1-3）
let voiceRecognition = null;
let isListening = false;

function initVoiceInput() {
  const btn = document.getElementById('btn-voice');
  if (!btn) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    btn.classList.add('hidden');
    return;
  }

  voiceRecognition = new SpeechRecognition();
  voiceRecognition.lang = 'zh-CN';
  voiceRecognition.continuous = false;
  voiceRecognition.interimResults = true;

  voiceRecognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    const input = document.getElementById('chat-input');
    if (input) input.value = transcript;
  };

  voiceRecognition.onend = () => {
    isListening = false;
    btn.classList.remove('listening');
  };

  voiceRecognition.onerror = (event) => {
    isListening = false;
    btn.classList.remove('listening');
    if (event.error !== 'no-speech' && event.error !== 'aborted') {
      toast('语音识别出了点问题，再试一次好吗？');
    }
  };

  btn.onclick = () => {
    if (isListening) {
      voiceRecognition.stop();
    } else {
      try {
        voiceRecognition.start();
        isListening = true;
        btn.classList.add('listening');
        toast('正在听你说…🎤');
      } catch (e) {
        toast('语音识别启动失败，请重试');
      }
    }
  };
}

// ---------------------------------------------------------------- 启动
initThemeUI();
initProfile();
initVoiceInput();
