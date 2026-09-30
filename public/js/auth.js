const API_BASE = "http://127.0.0.1:8000/api/auth";

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    
    const data = await res.json();
    if (res.ok && data.success) {
      localStorage.setItem("helix_token", data.access_token);
      localStorage.setItem("helix_user_id", data.user_id);
      localStorage.setItem("helix_user", JSON.stringify(data.user));
      window.location.href = "/dashboard";
    } else {
      alert("Login failed: " + (data.detail || "Invalid Credentials"));
    }
  } catch (err) {
    console.error(err);
    alert("Connection error to server.");
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const payload = {
    full_name: document.getElementById("fullName").value,
    email: document.getElementById("email").value,
    password: document.getElementById("password").value,
    age: parseInt(document.getElementById("age").value, 10),
    birthday: document.getElementById("birthday").value,
    gender: document.getElementById("gender").value
  };

  try {
    const res = await fetch(`${API_BASE}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok && data.success) {
      alert("Registration successful! Redirecting to login...");
      window.location.href = "/";
    } else {
      alert("Registration failed: " + (data.detail || "Error occurred"));
    }
  } catch (err) {
    console.error(err);
    alert("Connection error to server.");
  }
}
