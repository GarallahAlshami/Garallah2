/* صفحة التحليل الجماعي */
(function (global) {
  "use strict";

  let initialized = false;
  const state = { batchId: null, rows: [], search: "", filter: "", sort: "probability_desc" };

  async function load() {
    if (initialized) return;
    const dropzone = document.getElementById("dropzone");
    const input = document.getElementById("batchFile");

    dropzone.addEventListener("click", function () { input.click(); });
    dropzone.addEventListener("dragover", function (e) {
      e.preventDefault(); dropzone.classList.add("dragging");
    });
    dropzone.addEventListener("dragleave", function () { dropzone.classList.remove("dragging"); });
    dropzone.addEventListener("drop", function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragging");
      if (e.dataTransfer.files.length) upload(e.dataTransfer.files[0]);
    });
    input.addEventListener("change", function () {
      if (input.files.length) upload(input.files[0]);
    });

    document.getElementById("templateBtn").addEventListener("click", async function () {
      try {
        await API.download("/api/batch/template", "batch_template.csv");
        API.toast("تم تنزيل القالب.", "success");
      } catch (err) { API.toast(err.message, "error"); }
    });
    document.getElementById("exportBatchBtn").addEventListener("click", async function () {
      if (!state.batchId) return;
      try {
        await API.download("/api/batch/" + state.batchId + "/export", "batch.csv");
        API.toast("تم تصدير النتائج.", "success");
      } catch (err) { API.toast(err.message, "error"); }
    });
    document.getElementById("batchSearch").addEventListener("input", function (e) {
      state.search = e.target.value.trim().toLowerCase(); renderTable();
    });
    document.getElementById("batchFilter").addEventListener("change", function (e) {
      state.filter = e.target.value; renderTable();
    });
    document.getElementById("batchSort").addEventListener("change", function (e) {
      state.sort = e.target.value; renderTable();
    });

    initialized = true;
  }

  async function upload(file) {
    const status = document.getElementById("batchStatus");
    if (!/\.csv$/i.test(file.name)) {
      status.innerHTML = '<div class="alert alert-error">يُقبل ملف بصيغة CSV فقط.</div>';
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      status.innerHTML = '<div class="alert alert-error">حجم الملف يتجاوز 10 ميجابايت.</div>';
      return;
    }

    status.innerHTML = '<div class="loading-box"><span class="spinner spinner-dark"></span>' +
      "جارٍ التحقق من الملف وتنظيفه ومعالجته ثم تشغيل نموذج XGBoost...</div>";
    document.getElementById("batchResults").hidden = true;

    const form = new FormData();
    form.append("file", file);

    try {
      const data = await API.request("/api/batch/analyze", { method: "POST", body: form });
      state.batchId = data.batch_id;
      state.rows = data.results;

      let msg = '<div class="alert alert-success">تم تحليل الملف <strong>' +
        API.escapeHtml(data.file_name) + "</strong> بنجاح — " + data.summary.total + " سجلًا.</div>";
      if (data.warnings && data.warnings.length) {
        msg += '<div class="alert alert-warn"><strong>ملاحظات على البيانات:</strong><ul>' +
          data.warnings.map(function (w) { return "<li>" + API.escapeHtml(w) + "</li>"; }).join("") +
          "</ul></div>";
      }
      status.innerHTML = msg;

      renderSummary(data.summary);
      renderTable();
      renderShap(data.shap);
      document.getElementById("batchResults").hidden = false;
      API.toast("اكتمل التحليل الجماعي.", "success");
    } catch (err) {
      status.innerHTML = '<div class="alert alert-error">' + API.escapeHtml(err.message) + "</div>";
    }
  }

  function renderSummary(s) {
    document.getElementById("batchStats").innerHTML =
      stat(s.total, "إجمالي السجلات", "بعد التحقق والتنظيف") +
      stat(s.low, "خطورة منخفضة", "", "low") +
      stat(s.medium, "خطورة متوسطة", "", "medium") +
      stat(s.high, "خطورة مرتفعة", "", "high") +
      stat(s.at_risk, "طلاب مصنّفون كمعرّضين للتسرب", s.at_risk_percentage + "% من الدفعة") +
      stat(API.pct(s.avg_probability), "متوسط احتمال التسرب", "عبر جميع سجلات الدفعة");
  }

  function stat(value, label, hint, tone) {
    return '<div class="stat-card' + (tone ? " tone-" + tone : "") + '">' +
      '<span class="stat-label">' + label + '</span><span class="stat-value">' + value + "</span>" +
      (hint ? '<span class="stat-hint">' + hint + "</span>" : "") + "</div>";
  }

  function renderTable() {
    let rows = state.rows.slice();
    if (state.search) {
      rows = rows.filter(function (r) {
        return String(r.student_id).toLowerCase().indexOf(state.search) !== -1;
      });
    }
    if (state.filter) {
      rows = rows.filter(function (r) { return r.risk_level === state.filter; });
    }
    const [key, dir] = state.sort.split(/_(asc|desc)$/);
    rows.sort(function (a, b) {
      const av = a[key], bv = b[key];
      const cmp = typeof av === "number" ? av - bv : String(av).localeCompare(String(bv));
      return dir === "desc" ? -cmp : cmp;
    });

    document.getElementById("batchCount").textContent =
      "عرض " + rows.length + " من " + state.rows.length + " سجلًا";

    let html = "<thead><tr><th>رقم الطالب</th><th>التنبؤ</th><th>احتمال الخطر</th>" +
      "<th>مستوى الخطورة</th></tr></thead><tbody>";
    if (!rows.length) {
      html += UI.empty(4, "لا توجد سجلات مطابقة.");
    } else {
      rows.slice(0, 500).forEach(function (r) {
        html += "<tr><td><code>" + API.escapeHtml(r.student_id) + "</code></td>" +
          "<td>" + (r.prediction === 1 ? "معرّض للتسرب" : "غير معرّض") + "</td>" +
          "<td>" + PageDashboard.progress(r.probability) + "</td>" +
          "<td>" + API.riskBadge(r.risk_level) + "</td></tr>";
      });
    }
    document.getElementById("batchTable").innerHTML = html + "</tbody>";
  }

  function renderShap(shap) {
    const box = document.getElementById("batchShap");
    if (!shap || shap.error) {
      box.innerHTML = '<div class="alert alert-warn">' +
        API.escapeHtml((shap && shap.error) || "تعذّر توليد التفسير.") + "</div>";
      return;
    }
    let html = '<h4 class="form-section">الأهمية العامة للخصائص في هذه الدفعة</h4>' +
      '<div class="chart-box"><canvas id="chartBatchImportance"></canvas></div>';

    if (shap.top_case) {
      html += '<h4 class="form-section">تفسير أعلى حالة خطورة: ' +
        API.escapeHtml(shap.top_case.student_id) + " (احتمال " + API.pct(shap.top_case.probability) + ")</h4>" +
        '<div class="chart-box"><canvas id="chartBatchTopCase"></canvas></div>';
    }
    box.innerHTML = html;

    const feats = shap.global.features.slice().reverse();
    Charts.bar("chartBatchImportance",
      feats.map(function (f) { return f.feature_ar; }),
      feats.map(function (f) { return f.mean_abs_shap; }),
      { horizontal: true, label: "متوسط |SHAP|" });

    if (shap.top_case) {
      const top = shap.top_case.top_factors.slice(0, 10).reverse();
      Charts.divergingBar("chartBatchTopCase",
        top.map(function (f) { return f.feature_ar; }),
        top.map(function (f) { return f.shap_value; }));
    }
  }

  global.PageBatch = { load: load };
})(window);
