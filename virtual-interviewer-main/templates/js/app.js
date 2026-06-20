/* ═══════════════════════════════════════════════════
   PrepSpark — App Entry Point
   Loads HTML page fragments into #app-root, then boots.
   ═══════════════════════════════════════════════════ */

const PAGES = [
  'pages/auth.html',
  'pages/dashboard.html',
  'pages/interview.html',
  'pages/report.html',
];

async function loadPages() {
  const root = document.getElementById('app-root');
  for (const src of PAGES) {
    try {
      const res = await fetch(src);
      if (!res.ok) throw new Error(`Failed to load ${src}: ${res.status}`);
      const html = await res.text();
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      // Append each child directly (not the wrapper div)
      while (wrapper.firstChild) {
        root.appendChild(wrapper.firstChild);
      }
    } catch (e) {
      console.error(`[PrepSpark] Could not load page fragment: ${src}`, e);
    }
  }
}

async function boot() {
  await loadPages();

  // ── Wire keyboard shortcuts ──
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const active = document.querySelector('.page.active');
      if (!active) return;
      const id = active.id;
      if (id === 'auth-page') {
        const loginVisible = !document.getElementById('login-form').classList.contains('hidden');
        if (loginVisible) handleLogin();
        else handleRegister();
      } else if (id === 'setup-page') {
        startInterview();
      }
    }
  });

  // ── Route to correct page ──
  if (state.token && state.user) {
    await loadDashboard();
    showPage('dashboard-page');
  } else {
    showPage('auth-page');
  }
}

// Start when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}