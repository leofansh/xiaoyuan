/* V3.0 P1 · 宠物系统前端 (pet.js)
 * - 聊天页悬浮宠物头像（点击开面板）
 * - 宠物面板：喂食 / 皮肤 / 改名 / 互动 / 讲解课堂（I-11.3）
 * - SSE pet_feed 事件：XP 飘字 + 升级庆祝
 * 依赖 app.js 的 api()/$()/toast()/celebrate() 全局函数。
 */

const PET_SPECIES_EMOJI = { cat: "🐱", rabbit: "🐰", dino: "🦕" };
const PET_SKIN_INFO = {
  default: { name: "初始皮肤", emoji: "🐱", lv: 1 },
  sakura:  { name: "樱花限定", emoji: "🌸", lv: 5 },
  starry:  { name: "星空幻想", emoji: "🌌", lv: 10 },
  golden:  { name: "黄金传说", emoji: "👑", lv: 15 },
  cosmic:  { name: "宇宙霸主", emoji: "🪐", lv: 20 },
};
const PET_TALENT_EMOJI = { number_theory: "🔢", algebra: "🧮", geometry: "📐", function: "📈" };

let petCache = null;      // 最近一次宠物状态
const petTalentQueue = [];  // 待展示天赋归因（评估块产生）

/* ---------------- 宠物头像渲染（聊天页右下角） ---------------- */
function petFaceEmoji(pet) {
  if (!pet) return "🥚";
  if (pet.species === "egg" || !PET_SPECIES_EMOJI[pet.species]) return "🥚";
  return PET_SPECIES_EMOJI[pet.species];
}

function renderPetAvatar(pet) {
  const box = $("#pet-avatar");
  if (!box) return;
  box.classList.remove("hidden");
  const skin = PET_SKIN_INFO[pet.current_skin] || PET_SKIN_INFO.default;
  box.innerHTML = `
    <span class="pet-emoji">${petFaceEmoji(pet)}</span>
    <span class="pet-lv-badge">Lv.${pet.level || 1}</span>
    <span class="pet-mood-dot ${pet.mood || "normal"}"></span>`;
  box.title = `${pet.name || ""} · 等级 ${pet.level || 1}`;
}

/* ---------------- 宠物头像悬浮 XP 飘字 ---------------- */
function petXpFloat(amount) {
  const box = $("#pet-avatar");
  if (!box || !amount) return;
  const el = document.createElement("div");
  el.className = "xp-float";
  el.textContent = `+${amount} XP`;
  box.appendChild(el);
  box.classList.remove("pet-bounce");
  void box.offsetWidth;
  box.classList.add("pet-bounce");
  setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 1500);
}

/* ---------------- SSE pet_feed 事件处理 ---------------- */
function handlePetFeedSSE(data) {
  if (!data) return;
  const prevPet = petCache;
  const pet = data.pet || prevPet;
  const events = data.events || [];
  const xpTotal = events.reduce((s, ev) => s + (ev.amount || 0), 0);
  if (xpTotal) petXpFloat(xpTotal);

  const leveledUp = events.some(ev => ev.leveled_up);

  // 本次新解锁皮肤：对比旧/新 unlocked_skins + 事件字段
  const oldSkins = new Set((prevPet && prevPet.unlocked_skins) || []);
  const newSkins = new Set((pet && pet.unlocked_skins) || []);
  const unlockedSkins = [];
  newSkins.forEach(id => { if (!oldSkins.has(id)) unlockedSkins.push(id); });
  const evSkin = events.find(ev => ev.unlocked_skin);
  if (evSkin && unlockedSkins.indexOf(evSkin.unlocked_skin) === -1) unlockedSkins.push(evSkin.unlocked_skin);

  if (pet) {
    petCache = pet;
    renderPetAvatar(pet);
  }

  if (leveledUp) {
    showPetLevelUpModal({
      oldLevel: prevPet ? prevPet.level : null,
      newLevel: pet ? pet.level : null,
      unlockedSkins,
    });
  } else if (unlockedSkins.length) {
    unlockedSkins.forEach(id => {
      const info = PET_SKIN_INFO[id];
      toast(`✨ 新皮肤：${info ? info.name : id} 解锁！`, 3200);
    });
  }
}

/* ---------------- 升级庆祝弹窗（规格 3.7 PetLevelUpModal） ---------------- */
function showPetLevelUpModal({ oldLevel, newLevel, unlockedSkins }) {
  const emoji = petFaceEmoji(petCache);
  const skinLines = (unlockedSkins || []).map(id => {
    const info = PET_SKIN_INFO[id];
    return info ? `<span class="levelup-skin"><span class="skin-emoji">${info.emoji}</span>${info.name}</span>` : "";
  }).filter(Boolean).join("");

  const overlay = document.createElement("div");
  overlay.className = "pet-levelup-overlay";
  overlay.innerHTML = `
    <div class="pet-levelup-card">
      <div class="levelup-emoji">${emoji}</div>
      <div class="levelup-title">🎉</div>
      <div class="levelup-text">Lv.${oldLevel ?? "?"} → Lv.${newLevel ?? "?"} 升级啦！</div>
      ${skinLines ? `<div class="levelup-skins">${skinLines}</div>` : ""}
      <button class="levelup-btn">太棒了！</button>
    </div>`;
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.onclick = e => {
    if (e.target === overlay || e.target.closest(".levelup-btn")) close();
  };
  celebrate();
}

/* ---------------- 宠物加载与面板 ---------------- */
async function loadPetView() {
  if (!studentId) return { pet: null };
  try {
    const res = await api(`/api/pet/${studentId}`, null, "GET");
    petCache = res.pet || null;
    renderPetAvatar(petCache);
    return res;
  } catch (_) {
    return { pet: null };
  }
}

async function openPetPanel() {
  const res = await loadPetView();
  if (!res || !res.pet) {
    toast("宠物还没醒呢，先去学一会儿吧～");
    return;
  }
  const pet = res.pet;
  const moodMsg = res.mood_message || "";
  const xpPct = pet.exp_to_next ? Math.min(100, Math.round((pet.exp / pet.exp_to_next) * 100)) : 0;
  const skinInfo = PET_SKIN_INFO[pet.current_skin] || PET_SKIN_INFO.default;

  const skinBtns = Object.entries(PET_SKIN_INFO)
    .map(([id, info]) => {
      const unlocked = (pet.unlocked_skins || []).includes(id);
      const active = pet.current_skin === id;
      return `<button class="pet-skin-btn ${active ? "active" : ""} ${unlocked ? "" : "locked"}"
                data-skin="${id}" ${unlocked ? "" : "disabled"}>
                <span class="skin-emoji">${info.emoji}</span>
                <span class="skin-name">${info.name}</span>
                <span class="skin-lv">${unlocked ? "Lv." + info.lv : "Lv." + info.lv + " 解锁"}</span>
              </button>`;
    }).join("");

  $("#pet-panel").innerHTML = `
    <button class="close-x" onclick="closePetPanel()">×</button>
    <div class="pet-panel-face">
      <div class="pet-panel-emoji">${petFaceEmoji(pet)}</div>
      <div class="pet-meta">
        <div class="pet-name">${escapeHtml(pet.name || "")}</div>
        <div class="pet-level">Lv.${pet.level || 1} · ${escapeHtml(skinInfo.name)}</div>
        <div class="pet-xp-bar"><div class="pet-xp-fill" style="width:${xpPct}%"></div></div>
        <div class="pet-xp-labels"><span>${pet.exp} / ${pet.exp_to_next} XP</span><span>累计 ${pet.total_xp_earned || 0} XP</span></div>
      </div>
    </div>
    <div class="pet-mood-line">${escapeHtml(moodMsg)}</div>
    <div class="pet-talent-line" id="pet-talent-line" style="display:none"></div>

    <div class="pet-actions">
      <button id="btn-pet-feed">🍬 喂食</button>
      <button id="btn-pet-interact">💬 摸摸</button>
    </div>

    <div class="skin-title">🎨 皮肤</div>
    <div class="pet-skin-grid">${skinBtns}</div>

    <div class="skin-title">📝 改名</div>
    <div class="pet-rename-row">
      <input id="pet-rename-input" maxlength="10" placeholder="给宠物起个新名字" value="${escapeHtml(pet.name || "")}">
      <button class="btn-primary" onclick="renamePet()" style="padding:8px 14px;border-radius:12px;font-size:13px">保存</button>
    </div>

    <div class="skin-title">🗣 讲解课堂（讲给小圆和宠物听，答对也能巩固）</div>
    <div class="teach-box">
      <textarea id="teach-input" placeholder="把刚才的思路讲出来，比如：先算括号里的，再约分……"></textarea>
      <div class="teach-hint">完整讲解 +50 XP，还会获得小圆的评价。</div>
      <button class="btn-primary" onclick="submitTeach()" style="width:100%;padding:10px;border-radius:12px;font-size:14px">讲好啦，发给小圆 🎤</button>
      <div class="teach-feedback" id="teach-feedback"></div>
    </div>
  `;

  $("#btn-pet-feed").onclick = manualFeed;
  $("#btn-pet-interact").onclick = petInteract;
  document.querySelectorAll(".pet-skin-btn").forEach(btn => {
    btn.onclick = () => changePetSkin(btn.dataset.skin);
  });

  try {
    const idRes = await api(`/api/student/${studentId}`, null, "GET");
    if (idRes && idRes.identity) {
      renderIdentityInPanel(idRes.identity);
    }
  } catch (_) { /* 身份可选 */ }

  // 弹出待展示天赋话术
  if (petTalentQueue.length) {
    const line = $("#pet-talent-line");
    line.style.display = "";
    line.textContent = "🌟 " + petTalentQueue.pop();
  }
  $("#pet-overlay").classList.remove("hidden");
  $("#pet-overlay").onclick = (e) => { if (e.target === e.currentTarget) closePetPanel(); };
}

function closePetPanel() {
  $("#pet-overlay").classList.add("hidden");
}

/* ---------------- 身份展示（规格 11.4） ---------------- */
function renderIdentityInPanel(identity) {
  if (!identity) return;
  const badges = identity.badges || [];
  const badgeRow = badges.length
    ? `<div class="identity-badge-row">${badges.map(b => `<span class="identity-badge">${escapeHtml(b)}</span>`).join("")}</div>`
    : "";
  // 在面板中插入身份标签行
  const moodLine = document.querySelector(".pet-mood-line");
  if (moodLine && !document.querySelector("#identity-in-panel")) {
    moodLine.insertAdjacentHTML("afterend", `
      <div id="identity-in-panel" style="margin:0 0 10px">
        <span class="identity-tag">🏅 ${escapeHtml(identity.title || "新手")}</span>
        ${badgeRow}
      </div>`);
  }
}

/* ---------------- 喂食 / 互动 / 改名 / 皮肤 ---------------- */
async function manualFeed() {
  try {
    const res = await api(`/api/pet/${studentId}/feed`,
      { xp_amount: 5, source: "manual", message: "手动投喂" });
    if (res && res.pet) {
      petCache = res.pet;
      renderPetAvatar(res.pet);
      toast("🍬 宠物吃得很开心！+5 XP");
      if (res.leveled_up) { toast(`🎉 宠物升级到 Lv.${res.new_level}！`, 3500); celebrate(); }
      openPetPanel();
    }
  } catch (e) {
    toast("喂食失败：" + (e.message || "未知错误"));
  }
}

async function petInteract() {
  try {
    const res = await api(`/api/pet/${studentId}/interact`, null, "GET");
    if (res && res.message) toast("🐾 宠物：" + res.message, 2600);
    return res;
  } catch (_) { return null; }
}

/* 宠物头像点击 → 随机互动语音 + 对应 CSS 动画（规格 3.7） */
function playPetInteract() {
  petInteract().then(res => {
    if (!res || !res.animation) return;
    const box = $("#pet-avatar");
    if (!box) return;
    const cls = "pet-anim-" + res.animation;
    box.classList.add(cls);
    setTimeout(() => box.classList.remove(cls), 500);
  }).catch(() => {});
}

async function renamePet() {
  const input = $("#pet-rename-input");
  const name = (input && input.value || "").trim();
  if (!name) { toast("先想个名字吧～"); return; }
  try {
    const res = await api(`/api/pet/${studentId}/rename`, { name });
    if (res && res.name) {
      toast(`改好啦，以后就叫「${res.name}」！`);
      openPetPanel();
    }
  } catch (e) {
    toast("改名失败：" + (e.message || "名字需1-10个字符"));
  }
}

async function changePetSkin(skinId) {
  try {
    await api(`/api/pet/${studentId}/skin`, { skin_id: skinId });
    toast("✨ 皮肤换好啦！");
    openPetPanel();
  } catch (e) {
    toast("皮肤切换失败：" + (e.message || "未解锁"));
  }
}

/* ---------------- 讲解课堂（规格 11.3：I-11.3 输出>输入） ---------------- */
async function submitTeach() {
  const ta = $("#teach-input");
  const content = (ta && ta.value || "").trim();
  const fb = $("#teach-feedback");
  if (!content) { toast("先写点内容再发吧～"); return; }
  try {
    const res = await api(`/api/teach/${studentId}`, { content, topic_id: "" });
    if (fb) {
      fb.textContent = "💬 " + (res.feedback || "收到！");
    }
    if (res.pet_feed) {
      petXpFloat(res.pet_feed.xp_gained || 0);
      if (res.pet_feed.leveled_up) { toast(`🎉 宠物升级到 Lv.${res.pet_feed.new_level}！`, 3500); celebrate(); }
      loadPetView();
    }
    if (ta) ta.value = "";
    toast(`讲解已收录，质量评分 ${Math.round((res.quality || 0) * 100)} 分`);
  } catch (e) {
    toast("提交失败：" + (e.message || "未知错误"));
  }
}