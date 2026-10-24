// public/js/auth.js
const API_BASE = "/api/auth";

// --- 1. USER REGISTRATION HANDLER ---
async function handleRegister(e) {
  if (e) e.preventDefault();

  // Safely extract values regardless of ID naming conventions (fullName vs full_name)
  const fullNameEl = document.getElementById("fullName") || document.getElementById("full_name") || document.querySelector("input[name='full_name']");
  const emailEl = document.getElementById("email") || document.querySelector("input[type='email']");
  const passwordEl = document.getElementById("password") || document.querySelector("input[type='password']");
  const ageEl = document.getElementById("age") || document.querySelector("input[name='age']");
  const genderEl = document.getElementById("gender") || document.querySelector("select[name='gender']");
  const birthdayEl = document.getElementById("birthday") || document.getElementById("dob") || document.querySelector("input[type='date']");

  const emailVal = emailEl ? emailEl.value.trim().toLowerCase() : "";
  const passwordVal = passwordEl ? passwordEl.value : "";
  const fullNameVal = fullNameEl ? fullNameEl.value.trim() : "";
  const ageVal = ageEl && ageEl.value ? parseInt(ageEl.value, 10) : null;
  const genderVal = genderEl ? genderEl.value : "unknown";
  const birthdayVal = birthdayEl ? birthdayEl.value : null;

  if (!emailVal || !passwordVal) {
    alert("Please provide both email and password.");
    return;
  }

  const payload = {
    full_name: fullNameVal || emailVal.split("@")[0],
    email: emailVal,
    password: passwordVal,
    username: emailVal.split("@")[0],
    age: ageVal,
    gender: genderVal,
    dob: birthdayVal,
    birthday: birthdayVal
  };

  try {
    const res = await fetch(`${API_BASE}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    // Accommodates HTTP 201 Created, access_token presence, or status: 'success'
    if (res.ok && (data.access_token || data.status === "success" || data.success === true)) {
      if (data.access_token) {
        localStorage.setItem("helix_token", data.access_token);
        localStorage.setItem("helix_user_id", data.user?.id || data.user_id || "");
        localStorage.setItem("helix_user", JSON.stringify(data.user || { email: payload.email, full_name: payload.full_name }));
        localStorage.setItem("userName", data.user?.full_name || payload.full_name);
        window.location.href = "/dashboard.html";
      } else {
        alert("Registration successful! Redirecting to sign in...");
        window.location.href = "/";
      }
    } else {
      alert("Registration failed: " + (data.detail || data.message || "Invalid registration parameters."));
    }
  } catch (err) {
    console.error("Registration error:", err);
    alert("Connection error to server. Please verify backend is running.");
  }
}

// --- 2. USER LOGIN HANDLER ---
async function handleLogin(e) {
  if (e) e.preventDefault();

  const emailEl = document.getElementById("email") || document.querySelector("input[type='email']") || document.querySelector("input[name='username']");
  const passwordEl = document.getElementById("password") || document.querySelector("input[type='password']");

  const email = emailEl ? emailEl.value.trim().toLowerCase() : "";
  const password = passwordEl ? passwordEl.value : "";

  if (!email || !password) {
    alert("Please enter both email and password.");
    return;
  }

  try {
    // Attempt JSON login first
    let res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    let data = await res.json();

    // Fallback to OAuth2 form token if JSON endpoint is not matched
    if (!res.ok) {
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      res = await fetch("/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData
      });
      data = await res.json();
    }

    if (res.ok && data.access_token) {
      localStorage.setItem("helix_token", data.access_token);
      localStorage.setItem("helix_user_id", data.user?.id || data.user_id || "");
      localStorage.setItem("helix_user", JSON.stringify(data.user || { email }));
      localStorage.setItem("userName", data.user?.full_name || data.user?.username || email.split("@")[0]);
      window.location.href = "/dashboard.html";
    } else {
      alert("Login failed: " + (data.detail || "Invalid email or password."));
    }
  } catch (err) {
    console.error("Login error:", err);
    alert("Connection error to authentication server.");
  }
}

// --- 3. AUTO-ATTACH FORM LISTENERS ---
window.addEventListener("DOMContentLoaded", () => {
  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    if (window.location.pathname.includes("register")) {
      form.removeEventListener("submit", handleRegister);
      form.addEventListener("submit", handleRegister);
    } else {
      form.removeEventListener("submit", handleLogin);
      form.addEventListener("submit", handleLogin);
    }
  });
});

// Expose handlers globally for HTML onsubmit="" attributes
window.handleRegister = handleRegister;
window.handleLogin = handleLogin;