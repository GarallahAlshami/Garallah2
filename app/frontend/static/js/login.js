/* صفحة تسجيل الدخول */
(function () {
  "use strict";

  const form = document.getElementById("loginForm");
  const errorBox = document.getElementById("loginError");
  const button = document.getElementById("loginBtn");
  const spinner = button.querySelector(".spinner");
  const label = button.querySelector(".btn-label");
  const toggle = document.getElementById("togglePassword");
  const passwordInput = document.getElementById("password");

  if (new URLSearchParams(location.search).get("expired")) {
    showError("انتهت صلاحية الجلسة السابقة. يرجى تسجيل الدخول مرة أخرى.");
  }

  toggle.addEventListener("click", function () {
    const isPassword = passwordInput.type === "password";
    passwordInput.type = isPassword ? "text" : "password";
    toggle.textContent = isPassword ? "إخفاء" : "إظهار";
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function setLoading(state) {
    button.disabled = state;
    spinner.hidden = !state;
    label.textContent = state ? "جارٍ التحقق..." : "دخول";
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorBox.hidden = true;

    const identifier = document.getElementById("identifier").value.trim();
    const password = passwordInput.value;

    if (identifier.length < 3) return showError("يرجى إدخال اسم مستخدم أو بريد إلكتروني صحيح.");
    if (!password) return showError("يرجى إدخال كلمة المرور.");

    setLoading(true);
    try {
      const data = await API.request("/api/auth/login", {
        method: "POST",
        body: { identifier: identifier, password: password },
      });
      API.setToken(data.access_token, false);
      sessionStorage.setItem("ews_user", JSON.stringify(data.user));
      sessionStorage.setItem("ews_permissions", JSON.stringify(data.permissions));
      location.href = "/app";
    } catch (err) {
      showError(err.message || "تعذّر تسجيل الدخول.");
      setLoading(false);
    }
  });
})();
