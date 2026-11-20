/* صفحة لوحة التحكم */
(function (global) {
  "use strict";

  function statCard(value, label, hint, tone) {
    return (
      '<div class="stat-card' + (tone ? " tone-" + tone : "") + '">' +
        '<span class="stat-label">' + label + "</span>" +
        '<span class="stat-value">' + value + "</span>" +
        (hint ? '<span class="stat-hint">' + hint + "</span>" : "") +
      "</div>"
    );
  }

  async function load() {
    const cards = document.getElementById("statCards");
    cards.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';

    const [summary, charts, topRisk] = await Promise.all([
      API.request("/api/dashboard/summary"),
      API.request("/api/dashboard/charts"),
      API.request("/api/dashboard/high-risk?limit=10"),
    ]);

    const warn = document.getElementById("modelWarning");
    if (!summary.model_ready) {
      warn.hidden = false;
      warn.innerHTML = "لم يتم العثور على نموذج مُدرَّب. شغّل الأمر <code>python -m app.ml.train</code> ثم أعد تحميل الصفحة.";
    } else if (summary.not_evaluated > 0) {
      warn.hidden = false;
      warn.innerHTML = "يوجد <strong>" + summary.not_evaluated + "</strong> طالبًا لم يُقيَّم بعد. " +
        'اضغط <button class="btn btn-sm btn-primary" id="dashEvaluate">تقييم كل الطلاب</button> لتشغيل التنبؤ عليهم.';
      const btn = document.getElementById("dashEvaluate");
      if (btn) btn.addEventListener("click", runAll);
    } else {
      warn.hidden = true;
    }

    cards.innerHTML =
      statCard(summary.total_students, "إجمالي الطلاب", "المسجّلون في النظام") +
      statCard(summary.low, "خطورة منخفضة", "لا يحتاجون تدخلًا عاجلًا", "low") +
      statCard(summary.medium, "خطورة متوسطة", "يحتاجون متابعة دورية", "medium") +
      statCard(summary.high, "خطورة مرتفعة", "يحتاجون تدخلًا فوريًا", "high") +
      statCard(summary.at_risk_percentage + "%", "نسبة الطلاب المعرّضين للخطر", "من الطلاب الذين تم تقييمهم") +
      statCard(API.num(summary.avg_gpa), "متوسط المعدل التراكمي", "من 4.0") +
      statCard(summary.avg_attendance + "%", "متوسط نسبة الحضور", summary.low_attendance_count + " طالبًا دون 75%") +
      statCard(summary.avg_lms_logins, "متوسط التفاعل الإلكتروني", "دخول أسبوعي لمنصة التعلم");

    /* الرسوم */
    const risk = charts.risk_distribution;
    const colorMap = { low: "#1a7f6b", medium: "#b7791f", high: "#b83227", unknown: "#a9b3c0" };
    Charts.doughnut("chartRisk",
      risk.map(function (r) { return r.label; }),
      risk.map(function (r) { return r.count; }),
      risk.map(function (r) { return colorMap[r.key] || "#a9b3c0"; }));

    Charts.groupedBar("chartMajor",
      charts.by_major.map(function (m) { return m.label; }),
      [
        { label: "إجمالي الطلاب", data: charts.by_major.map(function (m) { return m.count; }), color: "#2c5f8a" },
        { label: "خطورة مرتفعة", data: charts.by_major.map(function (m) { return m.high; }), color: "#b83227" },
      ]);

    Charts.bar("chartGpa",
      charts.gpa_distribution.map(function (g) { return g.label; }),
      charts.gpa_distribution.map(function (g) { return g.count; }),
      { label: "عدد الطلاب" });

    Charts.bar("chartAttendance",
      charts.attendance_distribution.map(function (a) { return a.label; }),
      charts.attendance_distribution.map(function (a) { return a.count; }),
      { label: "عدد الطلاب", colors: "#1a7f6b" });

    Charts.doughnut("chartEngagement",
      charts.engagement_levels.map(function (e) { return e.label; }),
      charts.engagement_levels.map(function (e) { return e.count; }),
      ["#b83227", "#b7791f", "#1a7f6b"]);

    Charts.groupedBar("chartYear",
      charts.by_year.map(function (y) { return y.label; }),
      [
        { label: "إجمالي الطلاب", data: charts.by_year.map(function (y) { return y.count; }), color: "#7aa9c9" },
        { label: "خطورة مرتفعة", data: charts.by_year.map(function (y) { return y.high; }), color: "#b83227" },
      ]);

    /* جدول أعلى الطلاب خطورة */
    const table = document.getElementById("topRiskTable");
    let html = "<thead><tr><th>رقم الطالب</th><th>الاسم</th><th>التخصص</th><th>المعدل</th>" +
      "<th>الحضور</th><th>احتمال التسرب</th><th>الخطورة</th><th></th></tr></thead><tbody>";
    if (!topRisk.length) {
      html += UI.empty(8, "لا يوجد طلاب بمستوى خطورة مرتفع حاليًا.");
    } else {
      topRisk.forEach(function (s) {
        html += "<tr>" +
          "<td><code>" + API.escapeHtml(s.student_id) + "</code></td>" +
          "<td>" + API.escapeHtml(s.full_name) + "</td>" +
          "<td>" + API.escapeHtml(s.major) + "</td>" +
          "<td>" + API.num(s.gpa) + "</td>" +
          "<td>" + API.num(s.attendance_rate, 1) + "%</td>" +
          "<td>" + progress(s.probability) + "</td>" +
          "<td>" + API.riskBadge(s.risk_level) + "</td>" +
          '<td><button class="btn btn-xs" data-shap="' + API.escapeHtml(s.student_id) + '">التفسير</button></td>' +
          "</tr>";
      });
    }
    table.innerHTML = html + "</tbody>";
    table.querySelectorAll("[data-shap]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        navigate("shap");
        document.getElementById("shapStudentId").value = btn.dataset.shap;
        document.getElementById("runShapBtn").click();
      });
    });
  }

  function progress(p) {
    const raw = (p || 0) * 100;
    const v = Math.round(raw);
    // تجنّب عرض 100% لاحتمالية أقل من الواحد الصحيح
    const label = raw >= 99.95 && raw < 100 ? "99.9" : raw.toFixed(1);
    const tone = v >= 70 ? "high" : v >= 40 ? "medium" : "low";
    return '<div class="progress"><div class="progress-bar tone-' + tone + '" style="width:' + v + '%"></div>' +
      '<span class="progress-text">' + label + "%</span></div>";
  }

  async function runAll() {
    API.toast("جارٍ تقييم جميع الطلاب...");
    try {
      const res = await API.request("/api/predict/all", { method: "POST" });
      API.toast("تم تقييم " + res.processed + " طالبًا.", "success");
      load();
    } catch (err) {
      API.toast(err.message, "error");
    }
  }

  global.PageDashboard = { load: load, progress: progress, runAll: runAll };
})(window);
