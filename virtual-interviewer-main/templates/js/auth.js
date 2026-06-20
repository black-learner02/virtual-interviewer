/* ═══════════════════════════════════════════════════
   PrepSpark — Authentication Module
   ═══════════════════════════════════════════════════ */

function switchAuthTab(tab) {
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', (i === 0) === (tab === 'login'));
  });
  document.getElementById('login-form')?.classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form')?.classList.toggle('hidden', tab !== 'register');
}

async function handleLogin() {
  const identifier = document.getElementById('login-identifier')?.value.trim();
  const password = document.getElementById('login-password')?.value;
  const errEl = document.getElementById('login-error');
  hideError(errEl);

  if (!identifier || !password) { showError(errEl, 'Please fill in all fields.'); return; }

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username_or_email: identifier, password })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }

    state.token = data.token;
    state.user = data.user;
    saveSession();

    toast('Welcome back, ' + (data.user.full_name || data.user.username) + '!', 'success');
    await loadDashboard();
    showPage('dashboard-page');
  } catch (e) {
    showError(errEl, 'Connection failed. Is the server running?');
  }
}

async function handleRegister() {
  const fullName = document.getElementById('reg-fullname')?.value.trim();
  const username = document.getElementById('reg-username')?.value.trim();
  const email = document.getElementById('reg-email')?.value.trim();
  const password = document.getElementById('reg-password')?.value;
  const errEl = document.getElementById('register-error');
  hideError(errEl);

  if (!username || !email || !password) {
    showError(errEl, 'Please fill in all required fields.');
    return;
  }

  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password, full_name: fullName })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }

    toast('Account created! Please sign in.', 'success');
    switchAuthTab('login');
    const li = document.getElementById('login-identifier');
    if (li) li.value = username;
  } catch (e) {
    showError(errEl, 'Connection failed. Is the server running?');
  }
}

function handleLogout() {
  fetch(`${API}/auth/logout`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${state.token}` }
  }).catch(() => {});
  clearSession();
  showPage('auth-page');
  toast('Logged out successfully.', 'success');
}