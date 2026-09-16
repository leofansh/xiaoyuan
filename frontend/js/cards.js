/* V3.0 P1 · 卡片收集系统前端 (cards.js)
 * - CollectionWall：成长墙→收藏页（星光值/完成率/卡片网格/兑换皮肤）
 * - CardRevealModal：SSE card_drop 翻牌动画（史诗/传说特效）
 * - CardDetailModal：点击卡片翻转查看详情（背面/趣闻/数量/获得时间）
 * 依赖 app.js 的 api()/$()/toast()/celebrate() 全局函数。
 */

const CARD_RARITY_LABEL = { common: "普通", rare: "稀有", epic: "史诗", legendary: "传说" };
// 星光值兑换皮肤价格（规格 4.3.4：sakura=100，其余按稀有度递进）
const SKIN_COSTS = { sakura: 100, starry: 200, golden: 300, cosmic: 500 };

let cardLibrary = null;   // 卡片库缓存

async function loadCardsLibrary() {
  if (cardLibrary) return cardLibrary;
  try {
    const res = await api("/api/cards/library", null, "GET");
    cardLibrary = res.cards || [];
  } catch (_) {
    cardLibrary = [];
  }
  return cardLibrary;
}

/* ---------------- 收藏墙渲染（成长墙视图内，规格4.4） ---------------- */
async function renderCardsView() {
  if (!studentId) return;
  const section = $("#cards-section");
  if (!section) return;
  try {
    const [lib, mine] = await Promise.all([
      loadCardsLibrary(),
      api(`/api/cards/${studentId}`, null, "GET"),
    ]);
    const pct = lib.length ? Math.round((mine.unique_cards / lib.length) * 100) : 0;
    const collected = mine.collected || {};
    section.innerHTML = `
      <h3 class="section-title">🎴 我的卡册（${mine.unique_cards}/${lib.length}）</h3>
      <div class="cards-summary">
        <span class="starlight">⭐ ${mine.starlight}</span>
        <span class="progress">完成率 ${pct}% · 集齐 ${mine.unique_cards} 张</span>
      </div>
      ${renderSkinExchange(mine)}
      <div class="cards-grid">
        ${lib.map(c => renderCardItem(c, collected)).join("")}
      </div>`;
    section.querySelectorAll(".card-item").forEach(el => {
      el.onclick = () => {
        if (el.classList.contains("locked")) { toast("这张卡还没收集到，多学学相关的知识吧！"); return; }
        el.classList.toggle("flipped");
      };
    });
  } catch (_) {
    section.innerHTML = '<div class="empty-hint">卡册暂时打不开，稍后再试～</div>';
  }
}

function renderCardItem(card, collected) {
  const info = collected[card.id];
  const owned = !!info;
  const count = info ? info.count : 0;
  return `
    <div class="card-item ${owned ? "" : "locked"} card-${card.rarity}" title="${escapeHtml(card.name)}">
      <div class="card-inner">
        <div class="card-face">
          <div class="card-icon">${owned ? card.front_icon : "❔"}</div>
          <div class="card-name">${owned ? escapeHtml(card.name) : "？？？"}</div>
          <div class="card-rarity">${owned ? CARD_RARITY_LABEL[card.rarity] || card.rarity : ""}</div>
        </div>
        <div class="card-face card-back">
          <div class="card-back-text">${owned ? escapeHtml(card.back_text) : "学完对应的知识就能解锁！"}</div>
          ${owned ? `<div class="card-back-text" style="margin-top:4px;color:var(--muted)">✨ ${escapeHtml(card.fun_fact || "")}</div>` : ""}
          ${owned ? `<div class="card-back-text" style="margin-top:4px;color:var(--accent)">×${count} · ${escapeHtml(card.obtained_from_label || (info.obtained_from || ""))}</div>` : ""}
        </div>
      </div>
      ${count > 1 ? `<span class="card-count">×${count}</span>` : ""}
    </div>`;
}

/* ---------------- 星光值兑换皮肤（规格4.3.4） ---------------- */
function renderSkinExchange(mine) {
  const ownedSkins = new Set((petCache && petCache.unlocked_skins) || []);
  const rows = Object.entries(SKIN_COSTS).map(([skinId, cost]) => {
    const info = PET_SKIN_INFO[skinId];
    if (!info) return "";
    const unlocked = ownedSkins.has(skinId);
    const affordable = mine.starlight >= cost;
    return `
      <button class="pet-skin-btn ${unlocked ? "active" : ""}" style="min-width:86px"
              data-skin-ex="${skinId}" ${unlocked || !affordable ? "disabled" : ""}>
        <span class="skin-emoji">${info.emoji}</span>
        <span class="skin-name">${info.name}</span>
        <span class="skin-lv">${unlocked ? "已拥有" : `⭐ ${cost}`}</span>
      </button>`;
  }).join("");
  return `
    <div class="skin-title">⭐ 星光值兑换皮肤（${mine.starlight} 星光）</div>
    <div class="pet-skin-grid" style="grid-template-columns:repeat(4,1fr)">
      ${rows}
    </div>`;
}

document.addEventListener("click", e => {
  const btn = e.target.closest("[data-skin-ex]");
  if (!btn || btn.disabled) return;
  exchangeSkin(btn.dataset.skinEx);
});

async function exchangeSkin(skinId) {
  const cost = SKIN_COSTS[skinId];
  if (!cost) return;
  try {
    const res = await api(`/api/cards/${studentId}/exchange`, { skin_id: skinId, cost });
    if (res && res.success) {
      toast(`🎉 星光兑换成功，已拥有「${PET_SKIN_INFO[skinId].name}」！`, 3000);
      renderCardsView();
      loadPetView();
    }
  } catch (e) {
    toast("兑换失败：" + (e.message || "星光不足"));
  }
}

/* ---------------- CardRevealModal：SSE card_drop 掉落动画 ---------------- */
function handleCardDropSSE(data) {
  if (!data || !data.card) return;
  showCardReveal(data);
  // 收藏墙已显示则刷新
  const section = $("#cards-section");
  if (section && !section.classList.contains("hidden")) renderCardsView();
  // 星光增加则同步头像侧（若有）
  if (data.starlight_gained && petCache) petXpFloat(data.starlight_gained);
}

function showCardReveal(data) {
  const card = data.card;
  const isNew = data.is_new;
  const rarity = card.rarity || "common";
  const overlay = $("#card-drop-overlay");
  if (!overlay) return;
  overlay.classList.remove("hidden");
  $("#card-drop-title").innerHTML = isNew ? "🎉 收集到新卡片！" : "重复卡片 → 星光 ⭐";
  const big = $("#card-drop-big");
  big.className = `big-card card-${rarity}`;
  big.innerHTML = `
    <div class="big-face big-face-front">
      <div class="big-icon" style="font-size:52px">${isNew ? card.front_icon : "⭐"}</div>
      <div class="big-name">${escapeHtml(card.name)}</div>
      <div class="big-text">${isNew ? escapeHtml(card.front_text) : `+${data.starlight_gained || 0} 星光`}</div>
    </div>
    <div class="big-face big-face-back">
      <div class="big-back-q">?</div>
      <div class="big-back-hint">🎴</div>
    </div>`;
  // 先显示背面（.big-card 初始 rotateY(180deg)），600ms 后翻到正面
  big.classList.remove("flipped");
  void big.offsetWidth;
  setTimeout(() => big.classList.add("flipped"), 600);
  $("#card-drop-info").innerHTML = isNew
    ? `<span class="gain">${CARD_RARITY_LABEL[rarity] || rarity}</span> · ${escapeHtml(card.back_text || "")}`
    : `第 ${(data.duplicate_count || 0) + 1} 张 · 已转化为 ${data.starlight_gained || 0} 星光（当前余额 ${data.starlight_total || 0}）`;
  overlay.onclick = closeCardDrop;
  if (rarity === "epic" || rarity === "legendary") {
    celebrate();
    toast(`💎 掉落了${CARD_RARITY_LABEL[rarity]}卡「${card.name}」！`, 3000);
  }
}

function closeCardDrop() {
  $("#card-drop-overlay").classList.add("hidden");
}