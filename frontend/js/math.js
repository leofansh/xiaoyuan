/* 数学公式渲染模块：基于 KaTeX
 * V3.0 模块 L.8：同时处理 <<<XIAOYUAN_VIS>>> 可视化标记块（数轴/线段图）
 */

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ---------------- V3.0 模块 L.8：可视化标记块支持 ---------------- */

// 渲染单个 VIS 标记块内的 JSON → SVG HTML；解析失败或类型未知返回空串
function renderVisBlock(json) {
  var spec;
  try {
    spec = JSON.parse(json);
  } catch (e) {
    return "";
  }
  if (!spec || typeof spec !== "object") return "";
  if (spec.type === "numberline" && typeof renderNumberline === "function") {
    return renderNumberline(spec);
  }
  if (spec.type === "segment" && typeof renderSegment === "function") {
    return renderSegment(spec);
  }
  return "";
}

// 把提取出的 VIS 块 HTML 还原到占位符位置
function restoreVisBlocks(html, visHtmls) {
  for (var i = 0; i < visHtmls.length; i++) {
    html = html.replace("___VIS_" + i + "___", visHtmls[i]);
  }
  return html;
}

/**
 * 从文本中提取 VIS 标记块，返回 { protectedText, visHtmls }。
 * - 完整的 <<<XIAOYUAN_VIS>>>...<<<END_VIS>>> 块会被替换为占位符（占位符在 KaTeX/转义流程中安全）；
 * - 若存在未闭合的起始标记（流式输出中途），把可见文本截断到该标记之前，
 *   避免原始 JSON 在打完字之前闪现在屏幕上。
 */
function extractVisBlocks(text) {
  var visHtmls = [];
  // 未闭合标记 → 截断
  var startIdx = text.indexOf("<<<XIAOYUAN_VIS>>>");
  if (startIdx !== -1 && text.indexOf("<<<END_VIS>>>", startIdx) === -1) {
    text = text.slice(0, startIdx);
  }
  // 提取完整块
  var protectedText = text.replace(/<<<XIAOYUAN_VIS>>>([\s\S]*?)<<<END_VIS>>>/g, function (m, json) {
    visHtmls.push(renderVisBlock(json));
    return "___VIS_" + (visHtmls.length - 1) + "___";
  });
  return { protectedText: protectedText, visHtmls: visHtmls };
}

/**
 * 将文本中的 LaTeX 公式渲染为 HTML。
 * 支持：$...$（行内公式）、$$...$$（块级公式）
 * 非公式部分进行 HTML 转义（XSS 防护）。
 * V3.0 模块 L.8：额外支持 <<<XIAOYUAN_VIS>>> 可视化标记块。
 */
function renderMathText(text) {
  if (!text) return "";

  // V3.0 模块 L.8：先提取可视化标记块（与 KaTeX 无关，提前还原为 SVG）
  var vis = extractVisBlocks(text);
  text = vis.protectedText;

  // KaTeX 未加载时降级为转义文本（VIS 块仍正常渲染）
  if (typeof katex === "undefined") {
    return restoreVisBlocks(escapeHtml(text), vis.visHtmls);
  }

  // 先提取所有公式，用占位符保护
  var formulas = [];
  var protectedText = text;

  // 块级公式 $$...$$（贪婪匹配，允许换行）
  protectedText = protectedText.replace(/\$\$([\s\S]+?)\$\$/g, function (match, formula) {
    formulas.push({ formula: formula.trim(), display: true });
    return "___FORMULA_" + (formulas.length - 1) + "___";
  });

  // 行内公式 $...$（非贪婪，不允许换行）
  protectedText = protectedText.replace(/\$([^\n$]+?)\$/g, function (match, formula) {
    formulas.push({ formula: formula.trim(), display: false });
    return "___FORMULA_" + (formulas.length - 1) + "___";
  });

  // 转义非公式部分的 HTML
  var html = escapeHtml(protectedText);

  // 还原公式并用 KaTeX 渲染
  for (var i = 0; i < formulas.length; i++) {
    var placeholder = "___FORMULA_" + i + "___";
    var item = formulas[i];
    try {
      var rendered = katex.renderToString(item.formula, {
        throwOnError: false,
        displayMode: item.display,
        output: "html",
      });
      html = html.replace(placeholder, rendered);
    } catch (e) {
      // 渲染失败时显示原始公式文本
      html = html.replace(placeholder, '<code class="math-fallback">' + escapeHtml(item.formula) + "</code>");
    }
  }

  // 还原 VIS 块（数轴/线段图 SVG）
  html = restoreVisBlocks(html, vis.visHtmls);

  return html;
}