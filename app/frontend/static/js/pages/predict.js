/* صفحة التنبؤ بخطر التسرب */
(function (global) {
  "use strict";

  let initialized = false;

  const SAMPLE = {
    age: 21, gender: "male", region: "rural", family_income_level: "low",
    parent_education: "secondary", major: "information_systems", study_year: 3,
    gpa: 2.1, previous_gpa: 2.6, admission_score: 68, credits_completed: 62,
    failed_courses: 3, scholarship: "no", attendance_rate: 61,
    lms_logins_per_week: 2, assignment_submission_rate: 55, avg_session_minutes: 14,
    forum_posts: 1, late_submissions: 9, advisor_meetings: 0, financial_default: "yes",
    full_name: "طالب تجريبي",
  };

  async function load() {
    if (!initialized) {
      await buildManualForm();
      bind();
      initialized = true;
    }
  }

  function bind() {
    document.getElementById("runPredictBtn").addEventListener("click", runStudent);
    document.getElementById("predictStudentId").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); runStudent(); }
    });
    document.getElementById("pickStudentBtn").addEventListener("click", pickStudent);
    document.getElementById("fillSampleBtn").addEventListener("click", fillSample);
    document.getElementById("manualForm").addEventListener("submit", runManual);
  }

  async function buildManualForm() {
    const schema = await loadSchema();
    const container = document.getElementById("manualFields");
    let html = "";
    Object.keys(schema.groups).forEach(function (group) {
      schema.groups[group].forEach(function (name) {
        const label = schema.labels[name] || name;
        const categories = schema.categories[name];
        if (categories) {
          html += '<label class="field"><span>' + label + '</span><select name="' + name + '">' +
            categories.map(function (c) {
              return '<option value="' + c + '">' + API.escapeHtml(schema.value_labels[c] || c) + "</option>";
            }).join("") + "</select></label>";
        } else {
          const b = schema.bounds[name] || [0, 1000];
          const step = ["gpa", "previous_gpa", "attendance_rate", "assignment_submission_rate",
            "admission_score", "avg_session_minutes"].indexOf(name) !== -1 ? "0.01" : "1";
          html += '<label class="field"><span>' + label + '</span><input type="number" name="' + name +
            '" step="' + step + '" min="' + b[0] + '" max="' + b[1] + '" value="' + SAMPLE[name] + '" required /></label>';
        }
      });
    });
    container.innerHTML = html;
    fillSample();
  }

  function fillSample() {
    const form = document.getElementById("manualForm");
    Object.keys(SAMPLE).forEach(function (key) {
      const input = form.elements[key];
      if (input) input.value = SAMPLE[key];
    });
  }

  async function pickStudent() {
    UI.modal("اختيار طالب", '<div class="loading-box"><span class="spinner spinner-dark"></span>جارٍ التحميل...</div>');
    const data = await API.request("/api/students?page_size=50&sort_by=last_probability&sort_dir=desc");
    let html = '<input type="search" id="pickSearch" placeholder="بحث..." style="margin-bottom:.7rem;width:100%" />' +
      '<div class="table-wrap" style="max-height:420px;overflow:auto"><table class="data"><thead><tr>' +
      "<th>رقم الطالب</th><th>الاسم</th><th>المعدل</th><th>الخطورة</th><th></th></tr></thead><tbody id='pickBody'>";
    data.items.forEach(function (s) {
      html += '<tr data-name="' + API.escapeHtml((s.full_name + " " + s.student_id).toLowerCase()) + '"><td><code>' +
        API.escapeHtml(s.student_id) + "</code></td><td>" + API.escapeHtml(s.full_name) + "</td><td>" +
        API.num(s.gpa) + "</td><td>" + API.riskBadge(s.last_risk_level) + "</td>" +
        '<td><button class="btn btn-xs btn-primary" data-pick="' + API.escapeHtml(s.student_id) + '">اختيار</button></td></tr>';
    });
    html += "</tbody></table></div>";
    UI.modal("اختيار طالب", html, '<button class="btn" data-close>إغلاق</button>');
    document.querySelectorAll("#modalRoot [data-close]").forEach(function (el) {
      el.addEventListener("click", UI.closeModal);
    });
    document.getElementById("pickSearch").addEventListener("input", function (e) {
      const q = e.target.value.trim().toLowerCase();
      document.querySelectorAll("#pickBody tr").forEach(function (tr) {
        tr.style.display = tr.dataset.name.indexOf(q) === -1 ? "none" : "";
      });
    });
    document.querySelectorAll("[data-pick]").forEach(function (b) {
      b.addEventListener("click", function () {
        UI.closeModal();
        document.getElementById("predictStudentId").value = b.dataset.pick;
        runStudent();
      });
    });
  }

  async function runStudent() {
    const id = document.getElementById("predictStudentId").value.trim();
    if (!id) return API.toast("يرجى إدخال رقم الطالب.", "error");
    UI.loading("predictResult", "جارٍ تشغيل نموذج XGBoost وحساب قيم SHAP...");
    try {
      const data = await API.request("/api/predict/student/" + encodeURIComponent(id), { method: "POST" });
      document.getElementById("predictResult").innerHTML = resultHtml(data, id, data.student_name);
      wireResult(id);
    } catch (err) {
      UI.error("predictResult", err.message);
    }
  }

  async function runManual(event) {
    event.preventDefault();
    const form = event.target;
    if (!form.reportValidity()) return;
    const schema = AppState.schema;
    const payload = { full_name: "إدخال يدوي" };
    new FormData(form).forEach(function (value, key) {
      payload[key] = schema.categories[key] ? value : Number(value);
    });
    UI.loading("manualResult", "جارٍ التنبؤ...");
    try {
      const data = await API.request("/api/predict/manual", { method: "POST", body: payload });
      document.getElementById("manualResult").innerHTML = resultHtml(data, null, "إدخال يدوي");
    } catch (err) {
      UI.error("manualResult", err.message);
    }
  }

  function resultHtml(data, studentId, name) {
    const p = data.prediction;
    const tone = p.risk_level;
    let html = '<div class="result-panel tone-' + tone + '">' +
      '<div class="result-main">' +
        '<div class="result-block"><span class="result-label">النتيجة</span>' +
          '<span class="result-value">' + API.escapeHtml(p.prediction_label) + "</span></div>" +
        '<div class="result-block"><span class="result-label">احتمال التسرب</span>' +
          '<span class="result-value">' + API.pct(p.probability) + "</span></div>" +
        '<div class="result-block"><span class="result-label">مستوى الخطورة</span>' +
          '<span class="result-value">' + API.riskBadge(p.risk_level) + "</span></div>" +
        '<div class="result-block"><span class="result-label">النموذج المستخدم</span>' +
          '<span class="result-value">XGBoost</span></div>' +
      "</div>" +
      '<div class="progress big"><div class="progress-bar tone-' + tone + '" style="width:' +
        Math.round(p.probability * 100) + '%"></div><span class="progress-text">' +
        API.pct(p.probability) + "</span></div>" +
      "</div>";

    if (name) html = '<h4 class="form-section">' + API.escapeHtml(name) + "</h4>" + html;

    const ex = data.explanation || {};
    if (ex.narrative_ar) {
      html += '<div class="note-box">' + API.escapeHtml(ex.narrative_ar) + "</div>";
    }

    const factors = (ex.top_factors || []).slice(0, 8);
    if (factors.length) {
      html += '<h4 class="form-section">أهم العوامل المؤثرة في القرار (SHAP)</h4><div class="factors">';
      const maxAbs = Math.max.apply(null, factors.map(function (f) { return Math.abs(f.shap_value); })) || 1;
      factors.forEach(function (f) {
        const width = Math.max(4, Math.round((Math.abs(f.shap_value) / maxAbs) * 100));
        html += '<div class="factor-row">' +
          '<span class="factor-name">' + API.escapeHtml(f.feature_ar) + "</span>" +
          '<span class="factor-raw">' + API.escapeHtml(String(f.raw_value)) + "</span>" +
          '<span class="factor-bar-wrap"><span class="factor-bar ' + f.direction + '" style="width:' + width + '%"></span></span>' +
          '<span class="factor-val ' + f.direction + '">' + (f.shap_value > 0 ? "+" : "") + f.shap_value.toFixed(3) + "</span>" +
          '<span class="factor-dir ' + f.direction + '">' + (f.direction === "increase" ? "يرفع الخطر" : f.direction === "decrease" ? "يخفض الخطر" : "محايد") + "</span>" +
          "</div>";
      });
      html += "</div>";
    }

    const recs = data.recommendations || [];
    if (recs.length) {
      html += '<h4 class="form-section">التوصيات المقترحة (' + recs.length + ")</h4><div class=\"rec-list\">";
      recs.forEach(function (r) {
        html += '<div class="rec-card priority-' + r.priority + '">' +
          '<div class="rec-head"><strong>' + API.escapeHtml(r.title_ar) + "</strong>" +
          '<span class="badge badge-neutral">' + API.escapeHtml(r.category) + "</span></div>" +
          "<p>" + API.escapeHtml(r.action_ar) + "</p>" +
          (r.trigger_ar ? '<span class="rec-trigger">السبب: ' + API.escapeHtml(r.trigger_ar) + "</span>" : "") +
          "</div>";
      });
      html += "</div>";
    }

    if (studentId) {
      html += '<div style="margin-top:1rem"><button class="btn btn-soft" id="goShap">فتح صفحة التفسير الكاملة</button></div>';
    }
    return html;
  }

  function wireResult(studentId) {
    const btn = document.getElementById("goShap");
    if (btn) {
      btn.addEventListener("click", function () {
        navigate("shap");
        document.getElementById("shapStudentId").value = studentId;
        document.getElementById("runShapBtn").click();
      });
    }
  }

  global.PagePredict = { load: load, resultHtml: resultHtml };
})(window);
