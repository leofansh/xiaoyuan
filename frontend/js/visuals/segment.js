/* 线段图可视化组件（V3.0 模块 L.8 双向有效交流）
 * 小圆回复中输出 <<<XIAOYUAN_VIS>>> 标记块时，由 math.js 的 renderMathText 调用本组件渲染。
 * 用于行程/工程/分数应用题等数量关系的图形化表征。
 *
 * 标记格式（JSON，英文双引号）：
 *   {
 *     "type": "segment",
 *     "title": "全程 120km",                    // 可选：标题
 *     "segments": [                              // 必填：至少 1 段
 *       {"label": "已行 40km", "value": 40},
 *       {"label": "剩余 80km", "value": 80, "color": "#e8899a"}
 *     ]
 *   }
 *
 * 说明：各段宽度按 value 比例分配；color 可选（不填用主题色渐变）；所有文本经 HTML 转义防 XSS。
 */

(function () {
  var VIS_CSS = "xy-vis xy-segment";

  /* 本地转义（组件自包含，不依赖 math.js 的 escapeHtml） */
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* 根据段填充色亮度选择可读的文本颜色（深底白字，浅底深字） */
  function pickTextColor(hex) {
    var h = hex.replace("#", "");
    if (h.length === 3) h = h.split("").map(function (c) { return c + c; }).join("");
    var r = parseInt(h.slice(0, 2), 16) || 0;
    var g = parseInt(h.slice(2, 4), 16) || 0;
    var b = parseInt(h.slice(4, 6), 16) || 0;
    var lum = 0.299 * r + 0.587 * g + 0.114 * b;
    return lum > 150 ? "#4a4a4a" : "#ffffff";
  }

  /* 默认配色：主题绿色系渐变（与抹茶主题 --accent #7ca26c 呼应） */
  var DEFAULT_COLORS = ["#a8c79a", "#7ca26c", "#c8d8bd", "#5d8a4d", "#dde8d3"];

  /**
   * 渲染线段图 SVG。
   * @param {object} spec 标记块中的 JSON
   * @returns {string} SVG HTML 字符串；spec 非法时返回空串
   */
  window.renderSegment = function (spec) {
    if (!spec || spec.type !== "segment") return "";
    var segments = Array.isArray(spec.segments) ? spec.segments.filter(function (s) {
      return s && isFinite(Number(s.value)) && Number(s.value) > 0;
    }) : [];
    if (!segments.length) return "";

    // 归一化宽度
    var total = segments.reduce(function (sum, s) { return sum + Number(s.value); }, 0);
    var hasTitle = !!spec.title;

    var W = 560;
    var BAR_H = 52;
    var BAR_Y = hasTitle ? 44 : 30;
    var PAD = 20;
    var usable = W - PAD * 2;
    var H = BAR_Y + BAR_H + (segments.some(function (s) { return s.label; }) ? 30 : 8);

    var out = [];
    out.push('<svg class="' + VIS_CSS + '" viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="线段图">');

    if (hasTitle) {
      out.push('<text x="' + (W / 2) + '" y="20" text-anchor="middle" class="vis-title">' + esc(spec.title) + "</text>");
    }

    // 分段的水平条（圆角柱状，宽度按 value 比例）
    var xCursor = PAD;
    for (var i = 0; i < segments.length; i++) {
      var seg = segments[i];
      var value = Number(seg.value);
      var rawW = (value / total) * usable;
      var w = Math.max(rawW - (i + 1 < segments.length ? 4 : 0), 6);  // 段间留 4px 缝
      var color = seg.color && /^#[0-9a-fA-F]{3,8}$/.test(seg.color) ? seg.color : DEFAULT_COLORS[i % DEFAULT_COLORS.length];
      var textColor = pickTextColor(color);
      var cx = xCursor + w / 2;

      out.push('<rect x="' + xCursor + '" y="' + BAR_Y + '" width="' + w + '" height="' + BAR_H + '" rx="6" fill="' + color + '"/>');
      // 段内容：数值（段宽足够时显示在内部）
      if (w >= 44) {
        out.push('<text x="' + cx + '" y="' + (BAR_Y + BAR_H / 2 + 5) + '" text-anchor="middle" class="vis-seg-value" fill="' + textColor + '">' + esc(fmtVal(value)) + "</text>");
      }
      // 标签：段宽足够时显示在段上方，否则显示在条下方居中
      if (seg.label) {
        if (w >= 60) {
          out.push('<text x="' + cx + '" y="' + (BAR_Y - 10) + '" text-anchor="middle" class="vis-seg-label">' + esc(seg.label) + "</text>");
        } else {
          out.push('<text x="' + cx + '" y="' + (BAR_Y + BAR_H + 20) + '" text-anchor="middle" class="vis-seg-label">' + esc(seg.label) + "</text>");
        }
      }
      xCursor += rawW;
    }

    out.push("</svg>");
    return out.join("");

    function fmtVal(v) {
      var r = Math.round(v * 100) / 100;
      return String(r);
    }
  };
})();