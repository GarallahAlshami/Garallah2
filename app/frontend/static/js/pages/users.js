/* صفحة إدارة المستخدمين + سجل النظام */
(function (global) {
  "use strict";

  let initialized = false;
  let rolesCache = null;
  let searchTimer = null;

  const PERMISSION_LABELS = {
    "dashboard:view": "عرض لوحة التحكم",
    "students:view": "عرض الطلاب",
    "students:manage": "إدارة الطلاب (إضافة/تعديل/حذف)",
    "predict:run": "تشغيل التنبؤ",
    "explain:view": "عرض تفسير SHAP",
    "batch:run": "التحليل الجماعي",
    "models:view": "عرض مقارنة النماذج",
    "reports:view": "عرض التقارير",
    "reports:create": "إنشاء التقارير",
    "users:view": "عرض المستخدمين",
    "users:manage": "إدارة المستخدمين",
    "logs:view": "عرض سجل النظام",
  };

  async function load() {
    if (!initialized) {
      document.getElementById("addUserBtn").addEventListener("click", function () { openForm(null); });
      document.getElementById("userSearch").addEventListener("input", function (e) {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () { fetchUsers(e.target.value.trim()); }, 320);
      });
      initialized = true;
    }
    await Promise.all([fetchUsers(""), renderRoles()]);
  }

  async function fetchUsers(search) {
    const table = document.getElementById("usersTable");
    table.innerHTML = "<tbody>" + UI.empty(7, "جارٍ التحميل...") + "</tbody>";
    const users = await API.request("/api/users?search=" + encodeURIComponent(search || ""));
    const roleLabels = { admin: "مدير النظام", advisor: "مرشد أكاديمي" };

    let html = "<thead><tr><th>المستخدم</th><th>الاسم الكامل</th><th>البريد الإلكتروني</th>" +
      "<th>الدور</th><th>الحالة</th><th>آخر دخول</th><th>إجراءات</th></tr></thead><tbody>";
    if (!users.length) {
      html += UI.empty(7, "لا يوجد مستخدمون مطابقون.");
    } else {
      users.forEach(function (u) {
        html += "<tr><td><code>" + API.escapeHtml(u.username) + "</code></td>" +
          "<td>" + API.escapeHtml(u.full_name) + "</td>" +
          "<td>" + API.escapeHtml(u.email) + "</td>" +
          '<td><span class="badge badge-neutral">' + API.escapeHtml(roleLabels[u.role] || u.role) + "</span></td>" +
          "<td>" + (u.is_active
            ? '<span class="badge badge-low">مفعّل</span>'
            : '<span class="badge badge-high">معطّل</span>') + "</td>" +
          "<td>" + API.formatDate(u.last_login_at) + "</td>" +
          '<td class="row-actions">' +
            '<button class="btn btn-xs" data-edit="' + u.id + '">تعديل</button>' +
            '<button class="btn btn-xs ' + (u.is_active ? "btn-danger-soft" : "") + '" data-toggle="' + u.id +
              '" data-active="' + u.is_active + '">' + (u.is_active ? "تعطيل" : "تفعيل") + "</button>" +
          "</td></tr>";
      });
    }
    table.innerHTML = html + "</tbody>";

    table.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () {
        const user = users.filter(function (u) { return String(u.id) === b.dataset.edit; })[0];
        openForm(user);
      });
    });
    table.querySelectorAll("[data-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        const isActive = b.dataset.active === "true";
        UI.confirm(isActive ? "سيتم تعطيل هذا المستخدم ومنعه من الدخول. متابعة؟"
                            : "سيتم إعادة تفعيل هذا المستخدم. متابعة؟", async function () {
          try {
            await API.request("/api/users/" + b.dataset.toggle + "/toggle-active", { method: "POST" });
            API.toast("تم تحديث حالة المستخدم.", "success");
            fetchUsers(document.getElementById("userSearch").value.trim());
          } catch (err) { API.toast(err.message, "error"); }
        });
      });
    });
  }

  async function renderRoles() {
    if (!rolesCache) rolesCache = await API.request("/api/users/roles");
    const all = Object.keys(PERMISSION_LABELS);
    let html = "<thead><tr><th>الصلاحية</th>" +
      rolesCache.roles.map(function (r) { return "<th>" + API.escapeHtml(r.label) + "</th>"; }).join("") +
      "</tr></thead><tbody>";
    all.forEach(function (p) {
      html += "<tr><td>" + PERMISSION_LABELS[p] + "</td>" +
        rolesCache.roles.map(function (r) {
          return "<td>" + (r.permissions.indexOf(p) !== -1
            ? '<span class="perm-yes">✔</span>' : '<span class="perm-no">—</span>') + "</td>";
        }).join("") + "</tr>";
    });
    document.getElementById("rolesTable").innerHTML = html + "</tbody>";
  }

  async function openForm(user) {
    const isEdit = !!user;
    const html = '<form id="userForm"><div class="form-grid">' +
      '<label class="field"><span>اسم المستخدم</span><input name="username" value="' +
        API.escapeHtml(isEdit ? user.username : "") + '" ' + (isEdit ? "readonly" : "required minlength=3") + " /></label>" +
      '<label class="field"><span>البريد الإلكتروني</span><input type="email" name="email" value="' +
        API.escapeHtml(isEdit ? user.email : "") + '" required /></label>' +
      '<label class="field"><span>الاسم الكامل</span><input name="full_name" value="' +
        API.escapeHtml(isEdit ? user.full_name : "") + '" required /></label>' +
      '<label class="field"><span>الدور</span><select name="role">' +
        '<option value="advisor"' + (isEdit && user.role === "advisor" ? " selected" : "") + ">مرشد أكاديمي</option>" +
        '<option value="admin"' + (isEdit && user.role === "admin" ? " selected" : "") + ">مدير النظام</option>" +
      "</select></label>" +
      '<label class="field"><span>' + (isEdit ? "كلمة مرور جديدة (اتركها فارغة لعدم التغيير)" : "كلمة المرور") +
        '</span><input type="password" name="password" ' + (isEdit ? "" : "required") + ' minlength="8" /></label>' +
      "</div>" +
      '<p class="muted small">يجب ألا تقل كلمة المرور عن 8 أحرف وأن تحتوي على حرف كبير وحرف صغير ورقم.</p></form>';

    UI.modal(isEdit ? "تعديل مستخدم" : "إضافة مستخدم جديد", html,
      '<button class="btn btn-primary" id="saveUser">حفظ</button><button class="btn" data-close>إلغاء</button>');
    document.querySelectorAll("#modalRoot [data-close]").forEach(function (el) {
      el.addEventListener("click", UI.closeModal);
    });

    document.getElementById("saveUser").addEventListener("click", async function () {
      const form = document.getElementById("userForm");
      if (!form.reportValidity()) return;
      const payload = {};
      new FormData(form).forEach(function (v, k) { if (v !== "") payload[k] = v; });
      try {
        if (isEdit) {
          delete payload.username;
          await API.request("/api/users/" + user.id, { method: "PUT", body: payload });
          API.toast("تم تحديث بيانات المستخدم.", "success");
        } else {
          await API.request("/api/users", { method: "POST", body: payload });
          API.toast("تمت إضافة المستخدم.", "success");
        }
        UI.closeModal();
        fetchUsers("");
      } catch (err) { API.toast(err.message, "error"); }
    });
  }

  /* ------------------------------ سجل النظام ------------------------------ */
  async function loadLogs() {
    const table = document.getElementById("logsTable");
    table.innerHTML = "<tbody>" + UI.empty(6, "جارٍ التحميل...") + "</tbody>";
    const rows = await API.request("/api/users/logs?limit=200");
    let html = "<thead><tr><th>التاريخ</th><th>المستخدم</th><th>العملية</th>" +
      "<th>الكيان</th><th>التفاصيل</th><th>المستوى</th></tr></thead><tbody>";
    if (!rows.length) {
      html += UI.empty(6, "السجل فارغ.");
    } else {
      rows.forEach(function (r) {
        html += "<tr><td>" + API.formatDate(r.created_at) + "</td>" +
          "<td>" + API.escapeHtml(r.username || "—") + "</td>" +
          "<td><code>" + API.escapeHtml(r.action) + "</code></td>" +
          "<td>" + API.escapeHtml(r.entity || "—") + "</td>" +
          '<td class="log-details">' + API.escapeHtml(r.details || "—") + "</td>" +
          '<td><span class="badge badge-' + (r.level === "warning" ? "medium" : r.level === "error" ? "high" : "neutral") +
            '">' + API.escapeHtml(r.level) + "</span></td></tr>";
      });
    }
    table.innerHTML = html + "</tbody>";
  }

  global.PageUsers = { load: load, loadLogs: loadLogs };
})(window);
