/* صفحة إدارة الطلاب */
(function (global) {
  "use strict";

  const state = {
    page: 1, page_size: 20, search: "", risk_level: "", major: "",
    sort_by: "student_id", sort_dir: "asc", total: 0, initialized: false,
  };

  const COLUMNS = [
    { key: "student_id", label: "رقم الطالب", sortable: true },
    { key: "full_name", label: "الاسم", sortable: true },
    { key: "major", label: "التخصص", sortable: false },
    { key: "study_year", label: "السنة", sortable: true },
    { key: "gpa", label: "المعدل", sortable: true },
    { key: "attendance_rate", label: "الحضور", sortable: true },
    { key: "last_probability", label: "احتمال التسرب", sortable: true },
    { key: "risk", label: "الخطورة", sortable: false },
    { key: "actions", label: "إجراءات", sortable: false },
  ];

  let debounceTimer = null;

  async function load() {
    if (!state.initialized) {
      await init();
      state.initialized = true;
    }
    await fetchPage();
  }

  async function init() {
    await loadSchema();

    const majors = await API.request("/api/students/meta/majors");
    const select = document.getElementById("filterMajor");
    select.innerHTML = '<option value="">كل التخصصات</option>' + majors.map(function (m) {
      return '<option value="' + API.escapeHtml(m.value) + '">' + API.escapeHtml(m.label) + " (" + m.count + ")</option>";
    }).join("");

    document.getElementById("studentSearch").addEventListener("input", function (e) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        state.search = e.target.value.trim();
        state.page = 1;
        fetchPage();
      }, 350);
    });
    document.getElementById("filterRisk").addEventListener("change", function (e) {
      state.risk_level = e.target.value; state.page = 1; fetchPage();
    });
    document.getElementById("clearStudentFilters").addEventListener("click", function () {
      clearTimeout(debounceTimer);
      Object.assign(state, { search: "", risk_level: "", major: "", page: 1 });
      document.getElementById("studentSearch").value = "";
      document.getElementById("filterRisk").value = "";
      select.value = "";
      fetchPage();
    });
    select.addEventListener("change", function (e) {
      state.major = e.target.value; state.page = 1; fetchPage();
    });
    document.getElementById("pageSize").addEventListener("change", function (e) {
      state.page_size = parseInt(e.target.value, 10); state.page = 1; fetchPage();
    });
    document.getElementById("addStudentBtn").addEventListener("click", function () { openForm(null); });
    document.getElementById("exportStudentsBtn").addEventListener("click", async function () {
      try {
        await API.download("/api/reports/students/export", "students.csv");
        API.toast("تم تنزيل ملف الطلاب.", "success");
      } catch (err) { API.toast(err.message, "error"); }
    });
    document.getElementById("predictAllBtn").addEventListener("click", function () {
      UI.confirm("سيتم تشغيل نموذج XGBoost على جميع الطلاب وتحديث مستويات الخطورة. هل تريد المتابعة؟",
        async function () {
          API.toast("جارٍ التقييم...");
          try {
            const res = await API.request("/api/predict/all", { method: "POST" });
            API.toast("تم تقييم " + res.processed + " طالبًا.", "success");
            fetchPage();
          } catch (err) { API.toast(err.message, "error"); }
        });
    });
  }

  async function fetchPage() {
    const table = document.getElementById("studentsTable");
    table.innerHTML = "<tbody>" + UI.empty(9, "جارٍ التحميل...") + "</tbody>";

    const params = new URLSearchParams({
      search: state.search, risk_level: state.risk_level, major: state.major,
      page: state.page, page_size: state.page_size,
      sort_by: state.sort_by, sort_dir: state.sort_dir,
    });
    const data = await API.request("/api/students?" + params.toString());
    state.total = data.total;
    render(data.items);
    renderPagination();
  }

  function render(items) {
    const schema = AppState.schema;
    let head = "<thead><tr>";
    COLUMNS.forEach(function (c) {
      const active = state.sort_by === c.key;
      head += "<th" + (c.sortable ? ' class="sortable' + (active ? " active" : "") + '" data-sort="' + c.key + '"' : "") + ">" +
        c.label + (c.sortable ? '<span class="sort-ind">' + (active ? (state.sort_dir === "asc" ? "▲" : "▼") : "⇅") + "</span>" : "") + "</th>";
    });
    head += "</tr></thead>";

    let body = "<tbody>";
    if (!items.length) {
      body += UI.empty(9, "لا توجد نتائج مطابقة للبحث.");
    } else {
      items.forEach(function (s) {
        body += "<tr>" +
          "<td><code>" + API.escapeHtml(s.student_id) + "</code></td>" +
          "<td>" + API.escapeHtml(s.full_name) + "</td>" +
          "<td>" + API.escapeHtml(schema.value_labels[s.major] || s.major) + "</td>" +
          "<td>" + s.study_year + "</td>" +
          "<td>" + API.num(s.gpa) + "</td>" +
          "<td>" + API.num(s.attendance_rate, 1) + "%</td>" +
          "<td>" + (s.last_probability === null || s.last_probability === undefined
            ? '<span class="muted">—</span>' : PageDashboard.progress(s.last_probability)) + "</td>" +
          "<td>" + API.riskBadge(s.last_risk_level) + "</td>" +
          '<td class="row-actions">' +
            '<button class="btn btn-xs" data-view="' + s.student_id + '">الملف</button>' +
            '<button class="btn btn-xs" data-edit="' + s.student_id + '">تعديل</button>' +
            '<button class="btn btn-xs btn-danger-soft" data-del="' + s.student_id + '">حذف</button>' +
          "</td></tr>";
      });
    }
    body += "</tbody>";

    const table = document.getElementById("studentsTable");
    table.innerHTML = head + body;

    table.querySelectorAll("[data-sort]").forEach(function (th) {
      th.addEventListener("click", function () {
        const key = th.dataset.sort;
        if (state.sort_by === key) state.sort_dir = state.sort_dir === "asc" ? "desc" : "asc";
        else { state.sort_by = key; state.sort_dir = "asc"; }
        fetchPage();
      });
    });
    table.querySelectorAll("[data-view]").forEach(function (b) {
      b.addEventListener("click", function () { openProfile(b.dataset.view); });
    });
    table.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () { openForm(b.dataset.edit); });
    });
    table.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        UI.confirm("سيتم حذف الطالب " + b.dataset.del + " نهائيًا. هل أنت متأكد؟", async function () {
          try {
            await API.request("/api/students/" + b.dataset.del, { method: "DELETE" });
            API.toast("تم حذف الطالب.", "success");
            fetchPage();
          } catch (err) { API.toast(err.message, "error"); }
        });
      });
    });
  }

  function renderPagination() {
    const pages = Math.max(1, Math.ceil(state.total / state.page_size));
    const from = state.total === 0 ? 0 : (state.page - 1) * state.page_size + 1;
    const to = Math.min(state.page * state.page_size, state.total);
    const el = document.getElementById("studentsPagination");
    el.innerHTML =
      '<span class="muted small">عرض ' + from + " - " + to + " من " + state.total + " طالبًا</span>" +
      '<span class="spacer"></span>' +
      '<button class="btn btn-sm" ' + (state.page <= 1 ? "disabled" : "") + ' data-pg="first">الأولى</button>' +
      '<button class="btn btn-sm" ' + (state.page <= 1 ? "disabled" : "") + ' data-pg="prev">السابق</button>' +
      '<span class="page-indicator">صفحة ' + state.page + " من " + pages + "</span>" +
      '<button class="btn btn-sm" ' + (state.page >= pages ? "disabled" : "") + ' data-pg="next">التالي</button>' +
      '<button class="btn btn-sm" ' + (state.page >= pages ? "disabled" : "") + ' data-pg="last">الأخيرة</button>';

    el.querySelectorAll("[data-pg]").forEach(function (b) {
      b.addEventListener("click", function () {
        const action = b.dataset.pg;
        if (action === "first") state.page = 1;
        else if (action === "prev") state.page = Math.max(1, state.page - 1);
        else if (action === "next") state.page = Math.min(pages, state.page + 1);
        else state.page = pages;
        fetchPage();
      });
    });
  }

  /* -------------------------- نموذج إضافة/تعديل -------------------------- */
  function fieldHtml(name, schema, value) {
    const label = schema.labels[name] || name;
    const categories = schema.categories[name];
    if (categories) {
      return '<label class="field"><span>' + label + "</span><select name=\"" + name + '">' +
        categories.map(function (c) {
          return '<option value="' + c + '"' + (String(value) === c ? " selected" : "") + ">" +
            API.escapeHtml(schema.value_labels[c] || c) + "</option>";
        }).join("") + "</select></label>";
    }
    const bounds = schema.bounds[name] || [0, 1000];
    const step = ["gpa", "previous_gpa", "attendance_rate", "assignment_submission_rate",
      "admission_score", "avg_session_minutes"].indexOf(name) !== -1 ? "0.01" : "1";
    return '<label class="field"><span>' + label + '</span><input type="number" name="' + name +
      '" step="' + step + '" min="' + bounds[0] + '" max="' + bounds[1] + '" value="' +
      (value === undefined || value === null ? "" : value) + '" required /></label>';
  }

  async function openForm(studentId) {
    const schema = await loadSchema();
    let student = {};
    if (studentId) student = await API.request("/api/students/" + studentId);

    let html = '<form id="studentForm">';
    html += '<div class="form-grid">' +
      '<label class="field"><span>رقم الطالب</span><input name="student_id" value="' +
        API.escapeHtml(student.student_id || "") + '" ' + (studentId ? "readonly" : "required") + ' /></label>' +
      '<label class="field"><span>الاسم الكامل</span><input name="full_name" value="' +
        API.escapeHtml(student.full_name || "") + '" required /></label>' +
      "</div>";

    Object.keys(schema.groups).forEach(function (group) {
      html += '<h4 class="form-section">' + API.escapeHtml(group) + "</h4><div class=\"form-grid\">";
      schema.groups[group].forEach(function (name) {
        html += fieldHtml(name, schema, student[name]);
      });
      html += "</div>";
    });
    html += "</form>";

    UI.modal(studentId ? "تعديل بيانات الطالب" : "إضافة طالب جديد", html,
      '<button class="btn btn-primary" id="saveStudent">حفظ</button>' +
      '<button class="btn" data-close>إلغاء</button>');
    document.querySelectorAll("#modalRoot [data-close]").forEach(function (el) {
      el.addEventListener("click", UI.closeModal);
    });

    document.getElementById("saveStudent").addEventListener("click", async function () {
      const form = document.getElementById("studentForm");
      if (!form.reportValidity()) return;
      const payload = {};
      new FormData(form).forEach(function (value, key) {
        if (schema.categories[key] || key === "student_id" || key === "full_name") payload[key] = value;
        else payload[key] = Number(value);
      });
      try {
        if (studentId) {
          delete payload.student_id;
          await API.request("/api/students/" + studentId, { method: "PUT", body: payload });
          API.toast("تم تحديث بيانات الطالب.", "success");
        } else {
          await API.request("/api/students", { method: "POST", body: payload });
          API.toast("تمت إضافة الطالب بنجاح.", "success");
        }
        UI.closeModal();
        fetchPage();
      } catch (err) { API.toast(err.message, "error"); }
    });
  }

  /* ------------------------------ ملف الطالب ------------------------------ */
  async function openProfile(studentId) {
    UI.modal("ملف الطالب", '<div class="loading-box"><span class="spinner spinner-dark"></span>جارٍ التحميل...</div>');
    const schema = await loadSchema();
    const [student, history] = await Promise.all([
      API.request("/api/students/" + studentId),
      API.request("/api/students/" + studentId + "/history"),
    ]);

    const rec = history.academic_record;
    let html =
      '<div class="profile-head">' +
        "<div><h3>" + API.escapeHtml(student.full_name) + "</h3>" +
        '<span class="muted">' + API.escapeHtml(student.student_id) + " · " +
        API.escapeHtml(schema.value_labels[student.major] || student.major) + " · السنة " + student.study_year + "</span></div>" +
        "<div>" + API.riskBadge(student.last_risk_level) + "</div>" +
      "</div>";

    html += '<h4 class="form-section">السجل الأكاديمي</h4><div class="kv">' +
      kv("المعدل التراكمي الحالي", API.num(rec.gpa)) +
      kv("المعدل السابق", API.num(rec.previous_gpa)) +
      kv("التغيّر في المعدل", (rec.gpa_change > 0 ? "+" : "") + API.num(rec.gpa_change)) +
      kv("الساعات المنجزة", rec.credits_completed) +
      kv("المواد الراسب فيها", rec.failed_courses) +
      kv("درجة القبول", API.num(rec.admission_score, 1)) +
      kv("نسبة الحضور", API.num(rec.attendance_rate, 1) + "%") +
      kv("نسبة تسليم الواجبات", API.num(rec.assignment_submission_rate, 1) + "%") +
      kv("الدخول الأسبوعي للمنصة", rec.lms_logins_per_week) +
      "</div>";

    html += '<h4 class="form-section">البيانات الديموغرافية والسلوكية</h4><div class="kv">';
    Object.keys(schema.labels).forEach(function (name) {
      if (["gpa", "previous_gpa", "credits_completed", "failed_courses", "admission_score",
           "attendance_rate", "assignment_submission_rate", "lms_logins_per_week",
           "study_year", "major"].indexOf(name) !== -1) return;
      const raw = student[name];
      const display = schema.categories[name] ? (schema.value_labels[raw] || raw) : raw;
      html += kv(schema.labels[name], API.escapeHtml(display));
    });
    html += "</div>";

    html += '<h4 class="form-section">سجل التنبؤات السابقة</h4>';
    if (!history.predictions.length) {
      html += '<div class="table-empty">لا توجد تنبؤات سابقة لهذا الطالب.</div>';
    } else {
      html += '<div class="table-wrap"><table class="data"><thead><tr><th>التاريخ</th><th>النموذج</th>' +
        "<th>النتيجة</th><th>الاحتمال</th><th>الخطورة</th><th>المصدر</th></tr></thead><tbody>";
      history.predictions.forEach(function (p) {
        html += "<tr><td>" + API.formatDate(p.created_at) + "</td><td>" + API.escapeHtml(p.model_name) + "</td>" +
          "<td>" + (p.prediction === 1 ? "معرّض للتسرب" : "غير معرّض") + "</td>" +
          "<td>" + API.pct(p.probability) + "</td><td>" + API.riskBadge(p.risk_level) + "</td>" +
          "<td>" + API.escapeHtml(p.source || "—") + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }

    UI.modal("ملف الطالب", html,
      '<button class="btn btn-primary" id="profilePredict">تشغيل التنبؤ</button>' +
      '<button class="btn" id="profileShap">عرض التفسير</button>' +
      '<button class="btn" data-close>إغلاق</button>');
    document.querySelectorAll("#modalRoot [data-close]").forEach(function (el) {
      el.addEventListener("click", UI.closeModal);
    });
    document.getElementById("profilePredict").addEventListener("click", function () {
      UI.closeModal();
      navigate("predict");
      document.getElementById("predictStudentId").value = studentId;
      document.getElementById("runPredictBtn").click();
    });
    document.getElementById("profileShap").addEventListener("click", function () {
      UI.closeModal();
      navigate("shap");
      document.getElementById("shapStudentId").value = studentId;
      document.getElementById("runShapBtn").click();
    });
  }

  function kv(label, value) {
    return '<div class="kv-row"><span class="kv-label">' + label + '</span><span class="kv-value">' + value + "</span></div>";
  }

  global.PageStudents = { load: load, openProfile: openProfile, kv: kv };
})(window);
