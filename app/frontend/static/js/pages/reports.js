/* صفحة مركز التقارير */
(function (global) {
  "use strict";

  const TYPE_LABELS = {
    student: "تقرير طالب",
    high_risk: "تقرير الطلاب مرتفعي الخطورة",
    statistics: "تقرير إحصائي شامل",
    students_export: "تصدير بيانات الطلاب",
  };

  async function load() {
    const caps = await API.request("/api/reports/capabilities");
    renderCards(caps);
    await renderHistory();
  }

  function renderCards(caps) {
    const pdfBtn = function (path, name) {
      return caps.pdf
        ? '<button class="btn btn-primary btn-sm" data-dl="' + path + '&fmt=pdf" data-name="' + name + '.pdf">تنزيل PDF</button>'
        : '<button class="btn btn-sm" disabled title="مكتبة reportlab غير مثبتة">PDF غير متاح</button>';
    };

    document.getElementById("reportCards").innerHTML =
      '<div class="card report-card"><div class="card-head"><h3>تقرير طالب فردي</h3></div>' +
        "<p>تقرير مفصّل يشمل بيانات الطالب، ونتيجة التنبؤ، وعوامل الخطر المفسَّرة بـ SHAP، والتوصيات المقترحة.</p>" +
        '<input type="search" id="reportStudentId" placeholder="أدخل رقم الطالب" />' +
        '<div class="btn-row">' +
          '<button class="btn btn-primary btn-sm" id="studentPdf"' + (caps.pdf ? "" : " disabled") + ">تنزيل PDF</button>" +
          '<button class="btn btn-sm" id="studentCsv">تنزيل CSV</button>' +
        "</div></div>" +

      '<div class="card report-card"><div class="card-head"><h3>تقرير الطلاب مرتفعي الخطورة</h3></div>' +
        "<p>قائمة بجميع الطلاب المصنّفين ضمن مستوى الخطورة المرتفع مرتّبة تنازليًا حسب احتمال التسرب.</p>" +
        '<div class="btn-row">' +
          pdfBtn("/api/reports/high-risk?x=1", "high_risk_report") +
          '<button class="btn btn-sm" data-dl="/api/reports/high-risk?fmt=csv" data-name="high_risk.csv">تنزيل CSV</button>' +
        "</div></div>" +

      '<div class="card report-card"><div class="card-head"><h3>تقرير إحصائي شامل</h3></div>' +
        "<p>إحصاءات النظام الكاملة: توزيع مستويات الخطورة، المتوسطات الأكاديمية، والتوزيع حسب التخصص.</p>" +
        '<div class="btn-row">' +
          pdfBtn("/api/reports/statistics?x=1", "statistics_report") +
          '<button class="btn btn-sm" data-dl="/api/reports/statistics?fmt=csv" data-name="statistics.csv">تنزيل CSV</button>' +
        "</div></div>" +

      '<div class="card report-card"><div class="card-head"><h3>تصدير بيانات الطلاب</h3></div>' +
        "<p>تصدير كامل لبيانات جميع الطلاب المسجّلين مع آخر نتيجة تنبؤ لكل طالب بصيغة CSV.</p>" +
        '<div class="btn-row">' +
          '<button class="btn btn-sm" data-dl="/api/reports/students/export" data-name="students.csv">تنزيل CSV</button>' +
        "</div></div>" +

      (caps.pdf ? "" :
        '<div class="alert alert-warn" style="grid-column:1/-1">تصدير PDF غير متاح لأن مكتبة <code>reportlab</code> غير مثبتة. ' +
        "نفّذ <code>pip install reportlab arabic-reshaper python-bidi</code> لتفعيله.</div>");

    document.querySelectorAll("[data-dl]").forEach(function (btn) {
      btn.addEventListener("click", function () { doDownload(btn.dataset.dl, btn.dataset.name, btn); });
    });
    document.getElementById("studentPdf").addEventListener("click", function () { studentReport("pdf"); });
    document.getElementById("studentCsv").addEventListener("click", function () { studentReport("csv"); });
  }

  function studentReport(fmt) {
    const id = document.getElementById("reportStudentId").value.trim();
    if (!id) return API.toast("يرجى إدخال رقم الطالب.", "error");
    doDownload("/api/reports/student/" + encodeURIComponent(id) + "?fmt=" + fmt,
      "report_" + id + "." + fmt);
  }

  async function doDownload(path, name, btn) {
    const original = btn ? btn.textContent : null;
    if (btn) { btn.disabled = true; btn.textContent = "جارٍ الإنشاء..."; }
    try {
      await API.download(path, name);
      API.toast("تم إنشاء التقرير وتنزيله.", "success");
      renderHistory();
    } catch (err) {
      API.toast(err.message, "error");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = original; }
    }
  }

  async function renderHistory() {
    const table = document.getElementById("reportsTable");
    const rows = await API.request("/api/reports/history?limit=30");
    let html = "<thead><tr><th>النوع</th><th>العنوان</th><th>اسم الملف</th><th>الصيغة</th><th>تاريخ الإنشاء</th></tr></thead><tbody>";
    if (!rows.length) {
      html += UI.empty(5, "لم يتم إنشاء أي تقرير بعد.");
    } else {
      rows.forEach(function (r) {
        html += "<tr><td>" + API.escapeHtml(TYPE_LABELS[r.report_type] || r.report_type) + "</td>" +
          "<td>" + API.escapeHtml(r.title) + "</td>" +
          "<td><code>" + API.escapeHtml(r.file_name) + "</code></td>" +
          '<td><span class="badge badge-neutral">' + API.escapeHtml((r.file_format || "").toUpperCase()) + "</span></td>" +
          "<td>" + API.formatDate(r.created_at) + "</td></tr>";
      });
    }
    table.innerHTML = html + "</tbody>";
  }

  global.PageReports = { load: load };
})(window);
