/* V3.0 P1 · Combo 连击系统前端 (combo.js)
 * - ComboIndicator：聊天页连击指示器（🔥 xN + 里程碑进度）
 * - ComboEffect：里程碑全屏庆祝动画（×5 / ×10）
 * - SSE combo_update 事件处理 + 会话开始时回填状态
 * 依赖 app.js 的 api()/$()/toast()/celebrate() 全局函数。
 */

const COMBO_MILESTONE_TARGETS = { combo_3: 3, combo_5: 5, combo_10: 10 };

let comboState = { current: 0, best_all_time: 0, best_this_week: 0 };

/* ---------------- ComboIndicator ---------------- */
function renderComboIndicator(current) {
  const el = $("#combo-indicator");
  if (!el) return;
  if (!current) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  el.innerHTML = `🔥 <span class="combo-num">×${current}</span>`;
}

/* ---------------- ComboEffect 里程碑庆祝 ---------------- */
function showComboEffect(data) {
  if (!data || !data.milestone) return;
  const num = COMBO_MILESTONE_TARGETS[data.milestone];
  if (!num) return;
  const msg = data.message || (num === 5 ? "连击 5！奖励 +10 XP" : "连击 10！奖励 +20 XP");

  const overlay = document.createElement("div");
  overlay.className = "combo-celebrate";
  overlay.innerHTML = `
    <div class="combo-big">COMBO ×${num}</div>
    <div class="combo-sub">${escapeHtml(msg)}</div>`;
  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 2200);

  celebrate();
  if (data.xp_bonus) toast(`🎯 连击奖励 +${data.xp_bonus} XP！`, 3000);
}

/* ---------------- SSE / 初始状态 ---------------- */
function handleComboSSE(data) {
  if (!data) return;
  comboState.current = data.current != null ? data.current : comboState.current;
  renderComboIndicator(comboState.current);
  showComboEffect(data);
}

async function loadComboState() {
  if (!studentId) return;
  try {
    const res = await api(`/api/combo/${studentId}`, null, "GET");
    comboState = res || comboState;
    renderComboIndicator(comboState.current || 0);
  } catch (_) { /* 静默 */ }
}