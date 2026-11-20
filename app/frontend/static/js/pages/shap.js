/* صفحة الذكاء الاصطناعي القابل للتفسير (SHAP) */
(function (global) {
  "use strict";

  let initialized = false;
  let importanceLoaded = false;

  async function load() {
    if (!initialized) {
      document.getElementById("runShapBtn").addEventListener("click", runStudent);
      document.getElementById("shapStudentId").addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); runStudent(); }
      });
      document.getElementById("reloadImportanceBtn").addEventListener("click", function () {
        importanceLoaded = false;
        loadImportance();
      });
      initialized = true;
    }
    if (!importanceLoaded) await loadImportance();
  }

  async function loadImportance() {
    try {
      const data = await API.request("/api/explain/importance?top_k=15");
      const features = data.features.slice().reverse();
      Charts.bar("chartImportance",
        features.map(function (f) { return f.feature_ar; }),
        features.map(function (f) { return f.mean_abs_shap; }),
        { horizontal: true, label: "متوسط |SHAP|", colors: "#2c5f8a" });
      importanceLoaded = true;
    } catch (err) {
      API.toast(err.message, "error");
    }
  }

  async function runStudent() {
    const id = document.getElementById("shapStudentId").value.trim();
    if (!id) return API.toast("يرجى إدخال رقم الطالب.", "error");
    UI.loading("shapResult", "جارٍ حساب قيم SHAP ورسم مخطط الشلال...");
    try {
      const data = await API.request("/api/explain/student/" + encodeURIComponent(id) + "?top_k=12");
      render(id, data);
    } catch (err) {
      UI.error("shapResult", err.message);
    }
  }

  function render(id, data) {
    const container = document.getElementById("shapResult");
    const up = data.increasing_risk || [];
    const down = data.decreasing_risk || [];

    let html =
      '<div class="grid grid-3" style="margin-bottom:1rem">' +
        card("القيمة الأساسية (Base value)", data.base_value.toFixed(3), "متوسط مخرجات النموذج قبل النظر لبيانات الطالب") +
        card("القيمة النهائية (Output)", data.output_value.toFixed(3), "مخرج النموذج لهذا الطالب بعد جمع تأثيرات المتغيرات") +
        card("عدد العوامل المؤثرة", (data.top_factors || []).length, up.length + " رافعة · " + down.length + " خافضة") +
      "</div>";

    html += '<div class="note-box">' + API.escapeHtml(data.narrative_ar || "") + "</div>";

    html += '<div class="grid grid-2">' +
      '<div class="card"><div class="card-head"><h3>العوامل التي رفعت الخطر</h3></div>' + factorList(up, "increase") + "</div>" +
      '<div class="card"><div class="card-head"><h3>العوامل التي خفّضت الخطر</h3></div>' + factorList(down, "decrease") + "</div>" +
      "</div>";

    html += '<div class="card"><div class="card-head"><h3>مخطط الأعمدة (SHAP Bar Plot)</h3></div>' +
      '<div class="chart-box tall"><canvas id="chartStudentShap"></canvas></div></div>';

    html += '<div class="card"><div class="card-head"><h3>مخطط الشلال (SHAP Waterfall)</h3>' +
      '<button class="btn btn-sm" id="downloadWaterfall">تنزيل الصورة</button></div>' +
      '<p class="muted small">يوضّح المخطط كيف انتقل النموذج من القيمة الأساسية إلى القرار النهائي خطوة بخطوة.</p>' +
      '<div class="shap-img"><img id="waterfallImg" alt="مخطط الشلال SHAP للطالب ' + API.escapeHtml(id) + '" /></div></div>';

    html += '<div class="card"><div class="card-head"><h3>جدول تفصيلي لجميع العوامل</h3></div>' +
      '<div class="table-wrap"><table class="data"><thead><tr><th>المتغيّر</th><th>قيمة الطالب</th>' +
      "<th>قيمة SHAP</th><th>الاتجاه</th><th>مقدار التأثير</th></tr></thead><tbody>";
    const all = (data.all_factors || []).slice(0, 25);
    const maxAbs = Math.max.apply(null, all.map(function (f) { return f.abs_shap; })) || 1;
    all.forEach(function (f) {
      html += "<tr><td>" + API.escapeHtml(f.feature_ar) + "</td><td>" + API.escapeHtml(String(f.raw_value)) + "</td>" +
        '<td class="' + f.direction + '">' + (f.shap_value > 0 ? "+" : "") + f.shap_value.toFixed(4) + "</td>" +
        "<td>" + (f.direction === "increase" ? "يرفع الخطر" : f.direction === "decrease" ? "يخفض الخطر" : "محايد") + "</td>" +
        '<td><span class="factor-bar-wrap"><span class="factor-bar ' + f.direction + '" style="width:' +
        Math.max(3, Math.round((f.abs_shap / maxAbs) * 100)) + '%"></span></span></td></tr>';
    });
    html += "</tbody></table></div></div>";

    container.innerHTML = html;

    const top = (data.top_factors || []).slice(0, 12).slice().reverse();
    Charts.divergingBar("chartStudentShap",
      top.map(function (f) { return f.feature_ar; }),
      top.map(function (f) { return f.shap_value; }));

    const img = document.getElementById("waterfallImg");
    img.src = "/api/explain/student/" + encodeURIComponent(id) + "/waterfall?top_k=12&t=" + Date.now();
    img.onerror = function () {
      img.parentElement.innerHTML = '<div class="alert alert-warn">تعذّر توليد مخطط الشلال.</div>';
    };
    document.getElementById("downloadWaterfall").addEventListener("click", function () {
      const link = document.createElement("a");
      link.href = img.src;
      link.download = "shap_waterfall_" + id + ".png";
      link.click();
    });
  }

  function card(label, value, hint) {
    return '<div class="stat-card"><span class="stat-label">' + label + '</span>' +
      '<span class="stat-value">' + value + '</span><span class="stat-hint">' + hint + "</span></div>";
  }

  function factorList(items, direction) {
    if (!items.length) {
      return '<div class="table-empty">لا توجد عوامل في هذه الفئة.</div>';
    }
    const maxAbs = Math.max.apply(null, items.map(function (f) { return f.abs_shap; })) || 1;
    let html = '<div class="factors">';
    items.forEach(function (f) {
      html += '<div class="factor-row">' +
        '<span class="factor-name">' + API.escapeHtml(f.feature_ar) + "</span>" +
        '<span class="factor-raw">' + API.escapeHtml(String(f.raw_value)) + "</span>" +
        '<span class="factor-bar-wrap"><span class="factor-bar ' + direction + '" style="width:' +
        Math.max(5, Math.round((f.abs_shap / maxAbs) * 100)) + '%"></span></span>' +
        '<span class="factor-val ' + direction + '">' + (f.shap_value > 0 ? "+" : "") + f.shap_value.toFixed(3) + "</span>" +
        "</div>";
    });
    return html + "</div>";
  }

  global.PageShap = { load: load };
})(window);
