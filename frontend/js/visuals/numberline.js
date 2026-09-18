/* 数轴可视化组件（V3.0 模块 L.8 双向有效交流）
 * 小圆回复中输出 <<<XIAOYUAN_VIS>>> 标记块时，由 math.js 的 renderMathText 调用本组件渲染。
 *
 * 标记格式（JSON，英文双引号）：
 *   {
 *     "type": "numberline",
 *     "min": -3, "max": 6,                      // 必填：数轴范围
 *     "title": "x ≤ 2 的解集",                    // 可选：标题
 *     "points": [{"pos": 2, "label": "2", "solid": true}],  // 可选：标注点（solid=true 实心点，false 空心点）
 *     "highlight": {"from": -3, "to": 2, "openStart": true, "openEnd": true}  // 可选：高亮区间（开区间端点为空心圆）
 *   }
 *
 * 说明：所有来自 LLM 的文本（标题/标签）都会经过 HTML 转义，防止 XSS。
 */

(function () {
  var VIS_CSS = "xy-vis xy-numberline";

  /* 本地转义（组件自包含，不依赖 math.js 的 escapeHtml） */
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* 选一个"好看"的刻度步长，使轴上约 6~10 个刻度 */
  function niceStep(min, max) {
    var span = max - min;
    var raw = span / 8;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step;
    if (norm < 1.5) step = 1;
    else if (norm < 3) step = 2;
    else if (norm < 7) step = 5;
    else step = 10;
    var s = step * mag;
    return s < 1e-9 ? 1 : s;
  }

  function fmtNum(v) {
    var r = Math.round(v * 1e6) / 1e6;
    return String(r);
  }

  /**
   * 渲染数轴 SVG。
   * @param {object} spec 标记块中的 JSON
   * @returns {string} SVG HTML 字符串；spec 非法时返回空串
   */
  window.renderNumberline = function (spec) {
    if (!spec || spec.type !== "numberline") return "";
    var min = Number(spec.min);
    var max = Number(spec.max);
    if (!isFinite(min) || !isFinite(max) || max <= min) return "";

    var W = 560;          // 画布宽
    var H = spec.title ? 118 : 96;  // 画布高（标题占 22px）
    var AXIS_Y = H - 34;  // 轴线 y 坐标
    var PAD = 24;         // 左右留白
    var span = max - min;
    var xOf = function (v) { return PAD + ((v - min) / span) * (W - 2 * PAD); };

    var out = [];
    out.push('<svg class="' + VIS_CSS + '" viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="数轴示意图">');

    if (spec.title) {
      out.push('<text x="' + (W / 2) + '" y="18" text-anchor="middle" class="vis-title">' + esc(spec.title) + "</text>");
    }

    // 高亮区间（画在轴线下方，作为情绪化强调带）
    var hl = spec.highlight;
    if (hl && isFinite(Number(hl.from)) && isFinite(Number(hl.to))) {
      var hFrom = Math.max(min, Number(hl.from));
      var hTo = Math.min(max, Number(hl.to));
      if (hTo > hFrom) {
        var x1 = xOf(hFrom);
        var x2 = xOf(hTo);
        out.push('<line x1="' + x1 + '" y1="' + (AXIS_Y + 1) + '" x2="' + x2 + '" y2="' + (AXIS_Y + 1) + '" class="vis-range" stroke-width="12" stroke-linecap="round"/>');
        // 区间端点：实心/空心圆标注开闭
        var mk = function (cx, open, extra) {
          return '<circle cx="' + cx + '" cy="' + (AXIS_Y + 1) + '" r="6" class="' + (open ? "vis-point-open" : "vis-point-solid") + '"' + (extra || "") + "/>";
        };
        out.push(mk(x1, !!hl.openStart));
        out.push(mk(x2, !!hl.openEnd));
      }
    }

    // 轴线 + 两端箭头
    out.push('<line x1="' + PAD + '" y1="' + AXIS_Y + '" x2="' + (W - PAD) + '" y2="' + AXIS_Y + '" class="vis-axis" stroke-width="2"/>');
    var A = 8;
    out.push('<polygon points="' + (W - PAD) + "," + AXIS_Y + " " + (W - PAD - A) + "," + (AXIS_Y - A / 2) + " " + (W - PAD - A) + "," + (AXIS_Y + A / 2) + '" class="vis-axis" fill="currentColor"/>');
    out.push('<polygon points="' + PAD + "," + AXIS_Y + " " + (PAD + A) + "," + (AXIS_Y - A / 2) + " " + (PAD + A) + "," + (AXIS_Y + A / 2) + '" class="vis-axis" fill="currentColor"/>');

    // 刻度 + 数字标签
    var step = niceStep(min, max);
    var v = Math.ceil(min / step) * step;
    for (; v <= max + step / 1e6; v += step) {
      var x = xOf(v);
      out.push('<line x1="' + x + '" y1="' + (AXIS_Y - 6) + '" x2="' + x + '" y2="' + (AXIS_Y + 6) + '" class="vis-tick" stroke-width="1.5"/>');
      out.push('<text x="' + x + '" y="' + (AXIS_Y + 20) + '" text-anchor="middle" class="vis-tick-label">' + fmtNum(v) + "</text>");
    }

    // 标注点
    var pts = Array.isArray(spec.points) ? spec.points : [];
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      if (!p || !isFinite(Number(p.pos)) || p.pos < min || p.pos > max) continue;
      var px = xOf(Number(p.pos));
      out.push('<circle cx="' + px + '" cy="' + AXIS_Y + '" r="6" class="' + (p.solid ? "vis-point-solid" : "vis-point-open") + '"/>');
      if (p.label !== undefined && p.label !== null && String(p.label) !== "") {
        out.push('<text x="' + px + '" y="' + (AXIS_Y - 12) + '" text-anchor="middle" class="vis-point-label">' + esc(p.label) + "</text>");
      }
    }

    out.push("</svg>");
    return out.join("");
  };
})();