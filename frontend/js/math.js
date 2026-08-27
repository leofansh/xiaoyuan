/* 数学公式渲染模块：基于 KaTeX */

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * 将文本中的 LaTeX 公式渲染为 HTML。
 * 支持：$...$（行内公式）、$$...$$（块级公式）
 * 非公式部分进行 HTML 转义（XSS 防护）。
 */
function renderMathText(text) {
  if (!text) return "";

  // KaTeX 未加载时降级为转义文本
  if (typeof katex === "undefined") {
    return escapeHtml(text);
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

  return html;
}
