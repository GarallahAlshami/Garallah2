/* ==========================================================================
   طبقة الاتصال بواجهة البرمجة (API) + أدوات مشتركة
   ========================================================================== */
(function (global) {
  "use strict";

  const TOKEN_KEY = "ews_token";

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(token, remember) {
    clearToken();
    (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
  }

  function clearToken() {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  }

  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.name = "ApiError";
      this.status = status;
    }
  }

  async function request(path, options) {
    options = options || {};
    const headers = Object.assign({}, options.headers || {});
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    let response;
    try {
      response = await fetch(path, {
        method: options.method || "GET",
        headers: headers,
        body: options.body instanceof FormData ? options.body
          : (options.body ? JSON.stringify(options.body) : undefined),
        credentials: "same-origin",
      });
    } catch (err) {
      throw new ApiError("تعذّر الاتصال بالخادم. تأكد من أن النظام قيد التشغيل.", 0);
    }

    if (response.status === 401) {
      clearToken();
      if (!location.pathname.endsWith("/") && location.pathname !== "/") {
        location.href = "/?expired=1";
      }
      throw new ApiError("انتهت صلاحية الجلسة. يرجى تسجيل الدخول مجددًا.", 401);
    }

    if (options.raw) {
      if (!response.ok) throw new ApiError(await readError(response), response.status);
      return response;
    }

    if (!response.ok) throw new ApiError(await readError(response), response.status);
    if (response.status === 204) return null;
    const type = response.headers.get("content-type") || "";
    return type.includes("application/json") ? response.json() : response.text();
  }

  async function readError(response) {
    try {
      const data = await response.json();
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg || d).join(" | ");
      return "حدث خطأ غير متوقع (" + response.status + ").";
    } catch (e) {
      return "حدث خطأ غير متوقع (" + response.status + ").";
    }
  }

  async function download(path, fallbackName) {
    const response = await request(path, { raw: true });
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const name = match ? match[1] : (fallbackName || "download");
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    return name;
  }

  /* ------------------------------- أدوات ------------------------------- */
  const RISK_AR = { low: "منخفض", medium: "متوسط", high: "مرتفع" };

  function riskBadge(level) {
    if (!level) return '<span class="badge badge-neutral">لم يُقيَّم</span>';
    return '<span class="badge badge-' + level + '">' + (RISK_AR[level] || level) + "</span>";
  }

  function pct(value, digits) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    const raw = Number(value) * 100;
    const d = digits === undefined ? 1 : digits;
    // لا تُعرض 100% إلا عند اليقين التام، وكذلك 0% إلا عند الصفر التام
    if (raw > 0 && Number(raw.toFixed(d)) === 0) return (0.1).toFixed(d) + "%";
    if (raw < 100 && Number(raw.toFixed(d)) === 100) return (99.9).toFixed(d) + "%";
    return raw.toFixed(d) + "%";
  }

  function num(value, digits) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatDate(value) {
    if (!value) return "—";
    const d = new Date(value.endsWith && value.endsWith("Z") ? value : value + "Z");
    if (isNaN(d.getTime())) return String(value);
    return d.toLocaleString("ar-EG", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function toast(message, kind) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const item = document.createElement("div");
    item.className = "toast " + (kind || "");
    item.textContent = message;
    stack.appendChild(item);
    setTimeout(() => {
      item.style.opacity = "0";
      setTimeout(() => item.remove(), 250);
    }, kind === "error" ? 6000 : 3800);
  }

  global.API = {
    request, download, getToken, setToken, clearToken, ApiError,
    riskBadge, pct, num, escapeHtml, formatDate, toast, RISK_AR,
  };
})(window);
