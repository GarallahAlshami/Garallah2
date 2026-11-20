/* صفحة مقارنة النماذج */
(function (global) {
  "use strict";

  const METRICS = [
    { key: "accuracy", label: "الدقة (Accuracy)" },
    { key: "precision", label: "الإحكام (Precision)" },
    { key: "recall", label: "الاستدعاء (Recall)" },
    { key: "f1", label: "المتوسط التوافقي (F1-Score)" },
    { key: "auc_roc", label: "المساحة تحت المنحنى (AUC-ROC)" },
  ];

  async function load() {
    const container = document.getElementById("modelsContent");
    UI.loading(container, "جارٍ تحميل نتائج المقارنة...");
    const [data, info] = await Promise.all([
      API.request("/api/models/comparison"),
      API.request("/api/models/info"),
    ]);

    const doc = data.documented;
    let html = "";

    /* ---- النتائج الموثقة ---- */
    html += '<div class="card"><div class="card-head"><h3>النتائج الموثقة في تقرير المشروع</h3>' +
      '<span class="badge badge-neutral">ثابتة — لا تتغيّر</span></div>' +
      '<p class="muted small">' + API.escapeHtml(data.documented_note || "") + "</p>" +
      metricTable(doc.logistic_regression, doc.xgboost) +
      '<div class="chart-box"><canvas id="chartDocumented"></canvas></div></div>';

    /* ---- نتائج التشغيل ---- */
    const rt = data.runtime;
    if (rt && rt.xgboost && rt.xgboost.metrics) {
      html += '<div class="card"><div class="card-head"><h3>نتائج التشغيل الحالي (بيانات هذا التثبيت)</h3>' +
        '<span class="badge badge-neutral">محسوبة آنيًا</span></div>' +
        '<p class="muted small">تُحسب هذه القيم من تدريب النموذج على مجموعة البيانات الموجودة فعليًا في هذا التثبيت، ' +
        "وتُعرض بشفافية إلى جانب النتائج الموثقة في التقرير للمقارنة.</p>" +
        metricTable(rt.logistic_regression.metrics, rt.xgboost.metrics) +
        '<div class="chart-box"><canvas id="chartRuntime"></canvas></div></div>';

      html += '<div class="grid grid-2">' +
        '<div class="card"><div class="card-head"><h3>منحنى ROC</h3></div>' +
          '<div class="chart-box"><canvas id="chartRoc"></canvas></div></div>' +
        '<div class="card"><div class="card-head"><h3>مصفوفة الالتباس (XGBoost)</h3></div>' +
          confusionTable(rt.xgboost.confusion_matrix) +
          '<div class="card-head" style="margin-top:1rem"><h3>مصفوفة الالتباس (Logistic Regression)</h3></div>' +
          confusionTable(rt.logistic_regression.confusion_matrix) +
        "</div></div>";
    } else {
      html += '<div class="alert alert-warn">لم يتم تدريب النماذج بعد في هذا التثبيت. ' +
        "نفّذ الأمر <code>python -m app.ml.train</code> لعرض نتائج التشغيل الحالي.</div>";
    }

    /* ---- مسار المعالجة ومعلومات النموذج ---- */
    html += '<div class="grid grid-2">' +
      '<div class="card"><div class="card-head"><h3>مسار المعالجة والنمذجة</h3></div><ol class="steps">' +
        info.pipeline.map(function (s) { return "<li>" + API.escapeHtml(s) + "</li>"; }).join("") +
      "</ol></div>" +
      '<div class="card"><div class="card-head"><h3>معلومات النموذج</h3></div><div class="kv">' +
        PageStudents.kv("عدد الخصائص المستخدمة", info.features.count) +
        PageStudents.kv("خصائص رقمية", info.features.numeric.length) +
        PageStudents.kv("خصائص تصنيفية", info.features.categorical.length) +
        PageStudents.kv("حد الخطورة المتوسطة", info.risk_thresholds.medium) +
        PageStudents.kv("حد الخطورة المرتفعة", info.risk_thresholds.high) +
        PageStudents.kv("نموذج XGBoost متوفر", info.xgboost_available ? "نعم" : "لا") +
        PageStudents.kv("نموذج Logistic Regression متوفر", info.logistic_regression_available ? "نعم" : "لا") +
        (info.metadata.trained_at ? PageStudents.kv("تاريخ التدريب", API.formatDate(info.metadata.trained_at)) : "") +
        (info.metadata.n_rows ? PageStudents.kv("عدد السجلات المستخدمة", info.metadata.n_rows) : "") +
      "</div></div></div>";

    html += '<div class="note-box"><strong>الخلاصة:</strong> يتفوّق نموذج XGBoost على الانحدار اللوجستي في جميع ' +
      "مقاييس الأداء، لقدرته على التقاط العلاقات غير الخطية والتفاعلات بين المتغيرات (مثل تفاعل انخفاض المعدل " +
      "مع ضعف الحضور وقلة التفاعل الإلكتروني)، وهو ما يجعله النموذج المعتمد في هذا النظام.</div>";

    container.innerHTML = html;

    /* ---- الرسوم ---- */
    Charts.groupedBar("chartDocumented",
      METRICS.map(function (m) { return m.label; }),
      [
        { label: "Logistic Regression", data: METRICS.map(function (m) { return doc.logistic_regression[m.key]; }), color: "#7aa9c9" },
        { label: "XGBoost", data: METRICS.map(function (m) { return doc.xgboost[m.key]; }), color: "#2c5f8a" },
      ]);

    if (rt && rt.xgboost && rt.xgboost.metrics) {
      Charts.groupedBar("chartRuntime",
        METRICS.map(function (m) { return m.label; }),
        [
          { label: "Logistic Regression", data: METRICS.map(function (m) { return rt.logistic_regression.metrics[m.key]; }), color: "#7aa9c9" },
          { label: "XGBoost", data: METRICS.map(function (m) { return rt.xgboost.metrics[m.key]; }), color: "#1a7f6b" },
        ]);

      Charts.rocChart("chartRoc", [
        { label: "Logistic Regression", fpr: rt.logistic_regression.roc_curve.fpr, tpr: rt.logistic_regression.roc_curve.tpr },
        { label: "XGBoost", fpr: rt.xgboost.roc_curve.fpr, tpr: rt.xgboost.roc_curve.tpr },
      ]);
    }
  }

  function metricTable(lr, xgb) {
    let html = '<div class="table-wrap"><table class="data metric-table"><thead><tr><th>المقياس</th>' +
      "<th>Logistic Regression</th><th>XGBoost</th><th>الأفضل</th></tr></thead><tbody>";
    METRICS.forEach(function (m) {
      const a = lr[m.key], b = xgb[m.key];
      const better = b >= a ? "XGBoost" : "Logistic Regression";
      html += "<tr><td>" + m.label + "</td>" +
        "<td>" + a.toFixed(4).replace(/0+$/, "").replace(/\.$/, ".0") + "</td>" +
        "<td><strong>" + b.toFixed(4).replace(/0+$/, "").replace(/\.$/, ".0") + "</strong></td>" +
        '<td><span class="badge badge-low">' + better + "</span></td></tr>";
    });
    return html + "</tbody></table></div>";
  }

  function confusionTable(cm) {
    if (!cm) return "";
    return '<div class="table-wrap"><table class="data cm-table"><thead><tr><th></th>' +
      "<th>تنبؤ: غير معرّض</th><th>تنبؤ: معرّض للتسرب</th></tr></thead><tbody>" +
      "<tr><th>فعلي: غير معرّض</th><td class='cm-ok'>" + cm[0][0] + "</td><td class='cm-bad'>" + cm[0][1] + "</td></tr>" +
      "<tr><th>فعلي: معرّض للتسرب</th><td class='cm-bad'>" + cm[1][0] + "</td><td class='cm-ok'>" + cm[1][1] + "</td></tr>" +
      "</tbody></table></div>";
  }

  global.PageModels = { load: load };
})(window);
