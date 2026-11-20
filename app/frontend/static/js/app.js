/* الهيكل العام للتطبيق: التوجيه بين الصفحات، الجلسة، الأدوات المشتركة */
(function () {
  "use strict";

  const PAGE_TITLES = {
    dashboard: "لوحة التحكم",
    students: "إدارة الطلاب",
    predict: "التنبؤ بخطر التسرب",
    shap: "التفسير (SHAP)",
    batch: "التحليل الجماعي",
    models: "مقارنة النماذج",
    reports: "مركز التقارير",
    users: "إدارة المستخدمين",
    logs: "سجل النظام",
  };

  const state = { user: null, permissions: [], page: "dashboard", schema: null };
  window.AppState = state;

  /* ------------------------- أدوات مشتركة للصفحات ------------------------- */
  window.UI = {
    loading: function (target, message) {
      const node = typeof target === "string" ? document.getElementById(target) : target;
      if (node) {
        node.innerHTML =
          '<div class="loading-box"><span class="spinner spinner-dark"></span>' +
          (message || "جارٍ التحميل...") + "</div>";
      }
    },
    error: function (target, message) {
      const node = typeof target === "string" ? document.getElementById(target) : target;
      if (node) {
        node.innerHTML = '<div class="alert alert-error">' + API.escapeHtml(message) + "</div>";
      }
    },
    empty: function (colspan, message) {
      return '<tr><td colspan="' + colspan + '"><div class="table-empty">' +
        API.escapeHtml(message) + "</div></td></tr>";
    },
    modal: function (title, bodyHtml, footHtml) {
      const root = document.getElementById("modalRoot");
      root.innerHTML =
        '<div class="modal-backdrop" data-close-backdrop>' +
          '<div class="modal" role="dialog" aria-modal="true">' +
            '<div class="modal-head"><h3>' + API.escapeHtml(title) + "</h3>" +
              '<button class="close-x" data-close aria-label="إغلاق">&times;</button></div>' +
            '<div class="modal-body">' + bodyHtml + "</div>" +
            (footHtml ? '<div class="modal-foot">' + footHtml + "</div>" : "") +
          "</div></div>";
      root.querySelectorAll("[data-close]").forEach(function (el) {
        el.addEventListener("click", window.UI.closeModal);
      });
      const backdrop = root.querySelector("[data-close-backdrop]");
      backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) window.UI.closeModal();
      });
      document.addEventListener("keydown", escClose);
      return root.querySelector(".modal");
    },
    closeModal: function () {
      document.getElementById("modalRoot").innerHTML = "";
      document.removeEventListener("keydown", escClose);
    },
    confirm: function (message, onConfirm) {
      window.UI.modal(
        "تأكيد العملية",
        '<p>' + API.escapeHtml(message) + "</p>",
        '<button class="btn btn-danger" id="confirmYes">تأكيد</button>' +
        '<button class="btn" data-close>إلغاء</button>'
      );
      document.getElementById("confirmYes").addEventListener("click", function () {
        window.UI.closeModal();
        onConfirm();
      });
      document.querySelectorAll("#modalRoot [data-close]").forEach(function (el) {
        el.addEventListener("click", window.UI.closeModal);
      });
    },
    can: function (permission) {
      return state.permissions.indexOf(permission) !== -1;
    },
  };

  function escClose(e) {
    if (e.key === "Escape") window.UI.closeModal();
  }

  /* ------------------------------- التوجيه ------------------------------- */
  const PAGE_LOADERS = {
    dashboard: function () { return window.PageDashboard.load(); },
    students: function () { return window.PageStudents.load(); },
    predict: function () { return window.PagePredict.load(); },
    shap: function () { return window.PageShap.load(); },
    batch: function () { return window.PageBatch.load(); },
    models: function () { return window.PageModels.load(); },
    reports: function () { return window.PageReports.load(); },
    users: function () { return window.PageUsers.load(); },
    logs: function () { return window.PageUsers.loadLogs(); },
  };

  function navigate(page) {
    if (!PAGE_LOADERS[page]) page = "dashboard";
    state.page = page;

    document.querySelectorAll(".page").forEach(function (el) { el.classList.remove("active"); });
    const target = document.getElementById("page-" + page);
    if (target) target.classList.add("active");

    document.querySelectorAll(".nav-item").forEach(function (el) {
      el.classList.toggle("active", el.dataset.page === page);
    });

    document.getElementById("pageTitle").textContent = PAGE_TITLES[page] || "";
    document.getElementById("sidebar").classList.remove("open");
    location.hash = page;

    Promise.resolve(PAGE_LOADERS[page]()).catch(function (err) {
      API.toast(err.message || "تعذّر تحميل الصفحة.", "error");
    });
  }
  window.navigate = navigate;

  /* ------------------------------- الإقلاع ------------------------------- */
  async function boot() {
    if (!API.getToken()) {
      location.href = "/";
      return;
    }
    try {
      const data = await API.request("/api/auth/me");
      state.user = data.user;
      state.permissions = data.permissions || [];

      document.getElementById("userName").textContent = data.user.full_name || data.user.username;
      document.getElementById("userRole").textContent = data.role_label_ar;
      document.getElementById("userAvatar").textContent =
        (data.user.full_name || data.user.username).trim().charAt(0).toUpperCase();

      if (data.user.role === "admin") {
        document.querySelectorAll("[data-admin]").forEach(function (el) { el.hidden = false; });
      }
    } catch (err) {
      API.clearToken();
      location.href = "/";
      return;
    }

    document.querySelectorAll(".nav-item").forEach(function (el) {
      el.addEventListener("click", function () { navigate(el.dataset.page); });
    });
    document.querySelectorAll("[data-goto]").forEach(function (el) {
      el.addEventListener("click", function () { navigate(el.dataset.goto); });
    });

    document.getElementById("menuToggle").addEventListener("click", function () {
      document.getElementById("sidebar").classList.toggle("open");
    });
    document.getElementById("refreshBtn").addEventListener("click", function () {
      navigate(state.page);
      API.toast("تم تحديث البيانات.", "success");
    });
    document.getElementById("logoutBtn").addEventListener("click", async function () {
      try { await API.request("/api/auth/logout", { method: "POST" }); } catch (e) { /* تجاهل */ }
      API.clearToken();
      sessionStorage.clear();
      location.href = "/";
    });

    window.addEventListener("hashchange", function () {
      const page = location.hash.replace("#", "");
      if (page && page !== state.page) navigate(page);
    });

    navigate(location.hash.replace("#", "") || "dashboard");
  }

  /* --------------------- تحميل مخطط الحقول مرة واحدة --------------------- */
  window.loadSchema = async function () {
    if (state.schema) return state.schema;
    state.schema = await API.request("/api/students/schema");
    return state.schema;
  };

  document.addEventListener("DOMContentLoaded", boot);
})();
