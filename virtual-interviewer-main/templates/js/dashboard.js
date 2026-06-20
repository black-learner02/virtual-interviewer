/* ═══════════════════════════════════════════════════
   PrepSpark — Dashboard + Setup Module
   ═══════════════════════════════════════════════════ */

// Maps ISO 639-1 codes to flag emoji + short name for dashboard display
const LANG_FLAG_LABELS = {
  hi: '🇮🇳 Hindi',    ta: '🇮🇳 Tamil',    te: '🇮🇳 Telugu',
  bn: '🇮🇳 Bengali',  kn: '🇮🇳 Kannada',  ml: '🇮🇳 Malayalam',
  mr: '🇮🇳 Marathi',  pa: '🇮🇳 Punjabi',  gu: '🇮🇳 Gujarati',
  ur: '🇮🇳 Urdu',     en: '🌐 English',   es: '🌐 Spanish',
  fr: '🌐 French',    de: '🌐 German',    ar: '🌐 Arabic',
  ja: '🌐 Japanese',  zh: '🌐 Chinese',   ko: '🌐 Korean',
  pt: '🌐 Portuguese',ru: '🌐 Russian',   auto: '🌐 Auto',
};

// Maps file extension → format badge element ID
const RESUME_FORMAT_BADGES = {
  pdf: 'fmt-pdf', docx: 'fmt-docx', doc: 'fmt-doc',
  txt: 'fmt-txt', rtf: 'fmt-rtf',
};

function getLangLabel(code) {
  if (!code || code === 'en') return null;
  return LANG_FLAG_LABELS[code] || code.toUpperCase();
}


// ─────────────────────────────────────────────
// DASHBOARD
// ─────────────────────────────────────────────

async function loadDashboard() {
  const user = state.user;
  if (!user) return;

  const nameEl = document.getElementById('dash-name');
  const userEl = document.getElementById('dash-username');
  if (nameEl) nameEl.textContent = user.full_name || user.username;
  if (userEl) userEl.textContent = '@' + user.username;

  try {
    const res  = await fetch(`${API}/my_interviews`, { headers: authHeaders() });
    const data = await res.json();
    renderDashboard(data.interviews || []);
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

function renderDashboard(interviews) {
  const completedGrid     = document.getElementById('dash-grid');
  const inProgressGrid    = document.getElementById('dash-inprogress-grid');
  const inProgressSection = document.getElementById('dash-inprogress-section');

  if (!completedGrid) return;

  const completed  = interviews.filter(iv => iv.status === 'COMPLETED');
  const inProgress = interviews.filter(iv => iv.status !== 'COMPLETED');

  // ── IN-PROGRESS section ──
  if (inProgress.length > 0 && inProgressGrid && inProgressSection) {
    inProgressSection.style.display = 'block';
    inProgressGrid.innerHTML = '';
    inProgress.forEach(iv => {
      const card = document.createElement('div');
      card.className = 'dash-card resumable';
      const date     = new Date(iv.start_time).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
      });
      const answered  = iv.response_count || 0;
      const langLabel = getLangLabel(iv.language);
      const langPill  = langLabel
        ? `<span style="font-size:11px;font-family:'DM Mono',monospace;
                        color:var(--accent-2);background:rgba(255,255,255,0.04);
                        border:1px solid rgba(255,255,255,0.07);border-radius:100px;
                        padding:1px 8px;margin-left:6px;">${langLabel}</span>`
        : '';
      const contextPills = [
        iv.has_resume ? `<span style="font-size:10px;font-family:'DM Mono',monospace;color:var(--accent-2);background:rgba(100,220,150,0.08);border:1px solid rgba(100,220,150,0.2);border-radius:100px;padding:1px 7px;">📄 Resume</span>` : '',
        iv.has_jd    ? `<span style="font-size:10px;font-family:'DM Mono',monospace;color:var(--warn);background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.2);border-radius:100px;padding:1px 7px;">💼 JD</span>` : '',
      ].filter(Boolean).join('');

      card.innerHTML = `
        <div class="dash-card-tag" style="background:rgba(245,166,35,0.12);color:var(--warn);">In Progress</div>
        <div class="dash-card-name">${iv.candidate_name}${langPill}</div>
        <div class="dash-card-role">${iv.target_role}</div>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px;">
          <span class="dash-card-date">${date} · ${answered} questions answered</span>
          ${contextPills}
        </div>
        <div class="dash-card-resume-btn">▶ Resume Session</div>
      `;
      card.onclick = () => resumeInterview(iv.session_id);
      inProgressGrid.appendChild(card);
    });
  } else if (inProgressSection) {
    inProgressSection.style.display = 'none';
  }

  // ── COMPLETED section ──
  completedGrid.innerHTML = `
    <div class="dash-card new-interview-card" onclick="goToSetup()">
      <div class="new-interview-icon">＋</div>
      <div class="new-interview-label">Start a Practice Session</div>
    </div>
  `;

  if (completed.length === 0) {
    completedGrid.innerHTML += `
      <div style="grid-column:1/-1;text-align:center;padding:48px 0;color:var(--text-dim);
                  font-size:14px;font-family:'DM Mono',monospace;">
        No completed sessions yet. Start your first practice!
      </div>
    `;
  }

  completed.forEach(iv => {
    const card = document.createElement('div');
    card.className = 'dash-card';
    const date  = new Date(iv.start_time).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
    const scoreDisplay = iv.avg_score != null
      ? `<div class="dash-card-score" style="color:${iv.avg_score >= 7 ? 'var(--accent-2)' : iv.avg_score >= 5 ? 'var(--warn)' : 'var(--danger)'}">${iv.avg_score}</div>`
      : '';
    const langLabel = getLangLabel(iv.language);
    const langPill  = langLabel
      ? `<span style="font-size:11px;font-family:'DM Mono',monospace;
                      color:var(--text-muted);background:rgba(255,255,255,0.04);
                      border:1px solid rgba(255,255,255,0.07);border-radius:100px;
                      padding:1px 8px;margin-left:6px;">${langLabel}</span>`
      : '';
    const contextPills = [
      iv.has_resume ? `<span style="font-size:10px;font-family:'DM Mono',monospace;color:var(--accent-2);background:rgba(100,220,150,0.08);border:1px solid rgba(100,220,150,0.2);border-radius:100px;padding:1px 7px;">📄 Resume</span>` : '',
      iv.has_jd    ? `<span style="font-size:10px;font-family:'DM Mono',monospace;color:var(--warn);background:rgba(245,166,35,0.08);border:1px solid rgba(245,166,35,0.2);border-radius:100px;padding:1px 7px;">💼 JD</span>` : '',
    ].filter(Boolean).join('');

    card.innerHTML = `
      ${scoreDisplay}
      <div class="dash-card-tag tag-practice">Completed</div>
      <div class="dash-card-name">${iv.candidate_name}${langPill}</div>
      <div class="dash-card-role">${iv.target_role}</div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px;">
        <span class="dash-card-date">${date} · #${iv.session_id}</span>
        ${contextPills}
      </div>
    `;
    card.onclick = () => loadReport(iv.session_id);
    completedGrid.appendChild(card);
  });
}

function goToSetup() {
  if (state.user) {
    const nameEl = document.getElementById('setup-name');
    const roleEl = document.getElementById('setup-role');
    if (nameEl) nameEl.value = state.user.full_name || '';
    if (roleEl) roleEl.value = '';
  }

  const langEl = document.getElementById('setup-language');
  if (langEl) langEl.value = 'en';

  const errEl = document.getElementById('setup-error');
  if (errEl) errEl.style.display = 'none';

  // Always reset the resume panel when opening setup fresh
  clearResume();
  clearJD();

  showPage('setup-page');
}


// ─────────────────────────────────────────────
// RESUME UPLOAD — all logic lives here so it
// actually runs (HTML fragment scripts don't
// execute when injected via innerHTML).
// ─────────────────────────────────────────────

async function uploadResumeFile(event) {
  const file = event.target.files[0];
  // Reset immediately so the same file can be re-selected later
  event.target.value = '';
  if (!file) return;

  const ext = file.name.split('.').pop().toLowerCase();

  // ── Client-side size guard (5 MB) ──
  if (file.size > 5 * 1024 * 1024) {
    _showResumeStatus('error', '⚠ File too large. Maximum size is 5 MB.');
    return;
  }

  // Allowed types
  const allowed = ['pdf', 'docx', 'doc', 'txt', 'rtf'];
  if (!allowed.includes(ext)) {
    _showResumeStatus('error', `⚠ Unsupported format ".${ext}". Please upload a PDF, DOCX, DOC, TXT, or RTF file.`);
    return;
  }

  // Highlight the matching format badge
  _highlightFormatBadge(ext);
  _hideResumeStatus();
  _setUploading(true);

  // ── .txt: read directly in the browser, no server needed ──
  if (ext === 'txt') {
    const reader = new FileReader();
    reader.onload = e => {
      document.getElementById('setup-resume').value = e.target.result;
      _setUploading(false);
      _showResumeStatus('success', `✓ ${file.name} loaded`);
    };
    reader.onerror = () => {
      _setUploading(false);
      _showResumeStatus('error', '⚠ Could not read the file. Please try again.');
    };
    reader.readAsText(file);
    return;
  }

  // ── PDF / DOCX / DOC / RTF: send to Flask /extract_resume ──
  try {
    const fd = new FormData();
    fd.append('file', file, file.name);

    const res  = await fetch(`${API}/extract_resume`, {
      method:  'POST',
      headers: authHeaders(),   // intentionally no Content-Type — browser sets multipart boundary
      body:    fd
    });
    const data = await res.json();

    _setUploading(false);

    if (!res.ok) {
      _showResumeStatus('error', `⚠ ${data.error || 'Extraction failed. Try a different file or paste your resume manually.'}`);
      return;
    }

    document.getElementById('setup-resume').value = data.text;
    _showResumeStatus('success', `✓ ${data.filename}  ·  ${data.char_count.toLocaleString()} characters extracted`);

  } catch (err) {
    _setUploading(false);
    _showResumeStatus('error', '⚠ Network error. Is the server running? You can paste your resume text manually.');
    console.error('Resume upload error:', err);
  }
}

function clearResume() {
  const ta = document.getElementById('setup-resume');
  if (ta) ta.value = '';

  _hideResumeStatus();
  _setUploading(false);

  // Reset all format badges to inactive
  Object.values(RESUME_FORMAT_BADGES).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'fmt-badge';
  });

  // Reset button label
  const btn = document.getElementById('resume-upload-btn');
  if (btn) btn.textContent = '📎 Upload File';
}

function clearJD() {
  const ta = document.getElementById('setup-jd');
  if (ta) ta.value = '';
}

// ── Private helpers ──

function _setUploading(loading) {
  const spinner = document.getElementById('resume-upload-spinner');
  const btn     = document.getElementById('resume-upload-btn');
  if (loading) {
    if (spinner) spinner.style.display = 'inline';
    if (btn)     btn.style.pointerEvents = 'none';
    if (btn)     btn.style.opacity = '0.5';
  } else {
    if (spinner) spinner.style.display = 'none';
    if (btn)     btn.style.pointerEvents = 'auto';
    if (btn)     btn.style.opacity = '1';
    if (btn)     btn.textContent = '📎 Replace File';
  }
}

function _showResumeStatus(type, msg) {
  const bar = document.getElementById('resume-status-bar');
  if (!bar) return;

  const isSuccess = type === 'success';
  bar.style.display      = 'flex';
  bar.style.background   = isSuccess ? 'rgba(100,220,150,0.08)' : 'rgba(255,80,80,0.08)';
  bar.style.border       = isSuccess ? '1px solid rgba(100,220,150,0.25)' : '1px solid rgba(255,80,80,0.25)';
  bar.style.color        = isSuccess ? 'var(--accent-2)'                  : '#ff6b6b';
  bar.textContent        = msg;
}

function _hideResumeStatus() {
  const bar = document.getElementById('resume-status-bar');
  if (bar) bar.style.display = 'none';
}

function _highlightFormatBadge(ext) {
  // Clear all first
  Object.values(RESUME_FORMAT_BADGES).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'fmt-badge';
  });
  // Activate the matching one
  const targetId = RESUME_FORMAT_BADGES[ext];
  if (targetId) {
    const el = document.getElementById(targetId);
    if (el) el.className = 'fmt-badge fmt-badge-active';
  }
}


// ─────────────────────────────────────────────
// RESUME INTERRUPTED INTERVIEW
// ─────────────────────────────────────────────

async function resumeInterview(sessionId) {
  try {
    const res  = await fetch(`${API}/resume_interview?session_id=${sessionId}`, {
      headers: authHeaders()
    });
    const data = await res.json();
    if (!res.ok) { toast(data.error || 'Could not resume session.', 'error'); return; }

    state.sessionId     = data.session_id;
    state.currentQIndex = data.next_question_index;
    state.currentQText  = data.next_question;
    state.currentQType  = data.next_question_type;
    state.minQ          = data.min_questions || 5;
    state.maxQ          = data.max_questions || 10;
    state.hasResume     = data.has_resume || false;
    state.hasJD         = data.has_jd || false;
    state.language      = data.language || 'en';

    const nameEl = document.getElementById('setup-name');
    const roleEl = document.getElementById('setup-role');
    if (nameEl) nameEl.value = data.candidate_name;
    if (roleEl) roleEl.value = data.target_role;

    showPage('interview-page');
    setupInterviewUI({
      session_id:     data.session_id,
      question_index: data.next_question_index,
      question:       data.next_question,
      question_type:  data.next_question_type,
      language:       data.language || 'en',
      has_resume:     data.has_resume || false,
      has_jd:         data.has_jd || false,
    });

    if (data.completed_responses && data.completed_responses.length > 0) {
      data.completed_responses.forEach(r => {
        addToTranscript(r.question_index, r.question_text, r.question_type || 'technical', r.transcript);
      });
    }

    if (data.audio_b64) {
      await playAudio(data.audio_b64);
    } else {
      enableRecording();
    }

    toast(`Resuming from question ${data.next_question_index}…`, 'success');
  } catch (e) {
    toast('Failed to resume session. Is the server running?', 'error');
    console.error(e);
  }
}