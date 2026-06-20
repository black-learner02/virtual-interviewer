/* ═══════════════════════════════════════════════════
   PrepSpark — UI Utilities
   ═══════════════════════════════════════════════════ */

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}

function toast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span> ${msg}`;
  container.appendChild(t);
  setTimeout(() => t.classList.add('toast-out'), 3600);
  setTimeout(() => t.remove(), 4000);
}

function showError(el, msg) {
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
}

function hideError(el) {
  if (!el) return;
  el.style.display = 'none';
}

// ─── Processing Overlay ───
const PROC_STEPS = ['step-video', 'step-audio', 'step-timeline', 'step-ai'];
let stepTimer = null;

function showProcessing() {
  const overlay = document.getElementById('processing-overlay');
  if (overlay) overlay.classList.add('active');
  PROC_STEPS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('done', 'active');
  });
  const first = document.getElementById(PROC_STEPS[0]);
  if (first) first.classList.add('active');

  let i = 0;
  clearInterval(stepTimer);
  stepTimer = setInterval(() => {
    if (i < PROC_STEPS.length) {
      if (i > 0) {
        const prev = document.getElementById(PROC_STEPS[i - 1]);
        if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
      }
      const cur = document.getElementById(PROC_STEPS[i]);
      if (cur) cur.classList.add('active');
      i++;
    }
  }, 4500);
}

function hideProcessing() {
  clearInterval(stepTimer);
  PROC_STEPS.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active'); el.classList.add('done'); }
  });
  setTimeout(() => {
    const overlay = document.getElementById('processing-overlay');
    if (overlay) overlay.classList.remove('active');
  }, 400);
}