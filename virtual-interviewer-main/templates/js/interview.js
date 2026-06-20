/* ═══════════════════════════════════════════════════
   PrepSpark — Interview Room
   Dynamic question count, resume + JD aware.
   ═══════════════════════════════════════════════════ */

const Q_TYPE_LABELS = {
  intro:        'Introduction',
  technical:    'Technical',
  behavioural:  'Behavioural',
  resume_probe: 'Resume Deep-Dive',
  closing:      'Closing'
};

const LANG_LABELS = {
  hi: 'हिन्दी', ta: 'தமிழ்', te: 'తెలుగు', bn: 'বাংলা',
  kn: 'ಕನ್ನಡ', ml: 'മലയാളം', mr: 'मराठी', pa: 'ਪੰਜਾਬੀ',
  gu: 'ગુજરાતી', ur: 'اردو', en: 'English', es: 'Español',
  fr: 'Français', de: 'Deutsch', ar: 'العربية', ja: '日本語',
  zh: '中文', ko: '한국어', pt: 'Português', ru: 'Русский',
  auto: 'Auto',
};

// ─── Camera (on-demand) ───────────────────────────

async function openCamera() {
  state.mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  const video = document.getElementById('candidate-video');
  if (video) video.srcObject = state.mediaStream;

  const standby = document.getElementById('iv-camera-standby');
  if (standby) standby.classList.add('hidden');

  setSensorBadge('sen-camera', 'Active', 'badge-ok');
  setSensorBadge('sen-mic',    'Active', 'badge-ok');
}

function closeCamera() {
  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach(t => t.stop());
    state.mediaStream = null;
  }
  const video = document.getElementById('candidate-video');
  if (video) video.srcObject = null;

  const standby = document.getElementById('iv-camera-standby');
  if (standby) standby.classList.remove('hidden');

  const frame = document.getElementById('iv-video-frame');
  if (frame) frame.classList.remove('recording-active');

  setSensorBadge('sen-camera', 'Standby', '');
  setSensorBadge('sen-mic',    'Standby', '');
}

function setSensorBadge(id, text, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className   = 'sensor-badge' + (cls ? ' ' + cls : '');
}

// ─── Start New Interview ───────────────────────────

async function startInterview() {
  const name            = document.getElementById('setup-name')?.value.trim();
  const role            = document.getElementById('setup-role')?.value.trim();
  const language        = document.getElementById('setup-language')?.value || 'en';
  const resumeText      = document.getElementById('setup-resume')?.value.trim() || '';
  const jobDescription  = document.getElementById('setup-jd')?.value.trim() || '';
  const errEl           = document.getElementById('setup-error');
  if (errEl) errEl.style.display = 'none';

  if (!name || !role) {
    showError(errEl, 'Please enter your name and the target role.');
    return;
  }

  try {
    const res  = await fetch(`${API}/start_interview`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body:    JSON.stringify({ name, role, language, resume_text: resumeText, job_description: jobDescription })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }

    state.sessionId     = data.session_id;
    state.currentQIndex = 1;
    state.currentQText  = data.question;
    state.currentQType  = 'intro';
    state.minQ          = data.min_questions || 5;
    state.maxQ          = data.max_questions || 10;
    state.language      = data.language || language;
    state.hasResume     = data.has_resume || false;
    state.hasJD         = data.has_jd || false;

    showPage('interview-page');
    setupInterviewUI(data);

    if (data.audio_b64) {
      await playAudio(data.audio_b64);
    } else {
      enableRecording();
    }
  } catch (e) {
    showError(errEl, 'Failed to start session. Is the server running?');
    console.error(e);
  }
}

// ─── UI Setup ─────────────────────────────────────

function setupInterviewUI(data) {
  const sessionBadge = document.getElementById('session-badge');
  const navRole      = document.getElementById('nav-role');
  const setupRole    = document.getElementById('setup-role');
  const setupName    = document.getElementById('setup-name');
  const nameTag      = document.getElementById('iv-candidate-name');

  if (sessionBadge) sessionBadge.textContent = '#' + data.session_id;
  if (navRole && setupRole) navRole.textContent = setupRole.value;
  if (nameTag && setupName) nameTag.textContent = setupName.value || 'You';

  updateLanguageBadge(data.language || state.language);
  updateContextBadges(data.has_resume || state.hasResume, data.has_jd || state.hasJD);

  updateQuestionCard(data.question_index, data.question, data.question_type || 'intro');
  buildQPips(data.question_index);

  const log = document.getElementById('transcript-log');
  if (log) log.innerHTML = '<div class="iv-transcript-empty">Your answers will appear here after each submission.</div>';

  setHint('The AI interviewer will speak each question. Recording activates automatically when they finish.');
}

function updateLanguageBadge(langCode) {
  if (!langCode) return;
  const label = LANG_LABELS[langCode] || langCode.toUpperCase();
  let badge = document.getElementById('iv-lang-badge');
  if (!badge) {
    badge = document.createElement('span');
    badge.id = 'iv-lang-badge';
    badge.style.cssText = [
      'font-family:"DM Mono",monospace', 'font-size:11px',
      'color:var(--text-muted)', 'background:rgba(255,255,255,0.05)',
      'border:1px solid rgba(255,255,255,0.08)', 'border-radius:100px',
      'padding:2px 10px', 'letter-spacing:0.03em',
    ].join(';');
    const sessionBadge = document.getElementById('session-badge');
    if (sessionBadge && sessionBadge.parentNode) {
      sessionBadge.parentNode.insertBefore(badge, sessionBadge);
    }
  }
  badge.textContent = '🌐 ' + label;
}

function updateContextBadges(hasResume, hasJD) {
  // Remove old badges if present
  ['iv-resume-badge', 'iv-jd-badge'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });

  const sessionBadge = document.getElementById('session-badge');
  if (!sessionBadge || !sessionBadge.parentNode) return;

  if (hasResume) {
    const b = document.createElement('span');
    b.id = 'iv-resume-badge';
    b.title = 'Resume-tailored questions active';
    b.style.cssText = [
      'font-family:"DM Mono",monospace', 'font-size:11px',
      'color:var(--accent-2)', 'background:rgba(100,220,150,0.08)',
      'border:1px solid rgba(100,220,150,0.2)', 'border-radius:100px',
      'padding:2px 10px', 'letter-spacing:0.03em',
    ].join(';');
    b.textContent = '📄 Resume';
    sessionBadge.parentNode.insertBefore(b, sessionBadge);
  }

  if (hasJD) {
    const b = document.createElement('span');
    b.id = 'iv-jd-badge';
    b.title = 'Job description context active';
    b.style.cssText = [
      'font-family:"DM Mono",monospace', 'font-size:11px',
      'color:var(--warn)', 'background:rgba(245,166,35,0.08)',
      'border:1px solid rgba(245,166,35,0.2)', 'border-radius:100px',
      'padding:2px 10px', 'letter-spacing:0.03em',
    ].join(';');
    b.textContent = '💼 JD';
    sessionBadge.parentNode.insertBefore(b, sessionBadge);
  }
}

function updateQuestionCard(index, text, type) {
  const labelEl       = document.getElementById('q-label-text');
  const typeTag       = document.getElementById('q-type-tag');
  const textEl        = document.getElementById('q-text');
  const progressLabel = document.getElementById('iv-progress-label');
  const qCard         = document.getElementById('question-card');

  // Dynamic label — no hardcoded total
  const label = `Question ${index}`;
  if (labelEl)       labelEl.textContent       = label;
  if (progressLabel) progressLabel.textContent = label;
  if (textEl)        textEl.textContent        = text;
  if (typeTag) {
    typeTag.textContent = Q_TYPE_LABELS[type] || type;
    typeTag.className   = `iv-q-type-badge ${type}`;
  }
  if (qCard) qCard.className = 'iv-question-card';
}

/**
 * Dynamic pip row.
 * Filled = answered, Active = current, Empty = upcoming (show 2 ahead as placeholders).
 */
function buildQPips(current) {
  const container = document.getElementById('q-pips');
  if (!container) return;
  container.innerHTML = '';

  const showUpTo = current + 2; // show 2 future placeholders
  for (let i = 1; i <= showUpTo; i++) {
    const pip = document.createElement('div');
    if (i < current) {
      pip.className = 'q-pip done';
      pip.title = 'Answered';
    } else if (i === current) {
      pip.className = 'q-pip active';
      pip.title = 'Current question';
    } else {
      pip.className = 'q-pip';
      pip.title = 'Upcoming';
      pip.style.opacity = i === current + 1 ? '0.4' : '0.2';
    }
    container.appendChild(pip);
  }

  // Add adaptive hint after min questions
  if (current >= state.minQ) {
    const hint = document.createElement('span');
    hint.style.cssText = 'font-size:10px;color:var(--accent-2);font-family:"DM Mono",monospace;margin-left:8px;opacity:0.8;';
    hint.textContent = '✓ Adapting to your answers';
    container.appendChild(hint);
  }
}

function setHint(html) {
  const el = document.getElementById('sidebar-hint');
  if (el) el.innerHTML = html;
}

// ─── TTS Playback ─────────────────────────────────

async function playAudio(base64mp3) {
  const recordBtn = document.getElementById('btn-record');
  if (recordBtn) recordBtn.disabled = true;

  const qCard = document.getElementById('question-card');
  if (qCard) qCard.classList.add('speaking');

  setHint('The AI interviewer is speaking — recording activates when they finish.');

  return new Promise((resolve) => {
    const done = () => {
      if (qCard) qCard.classList.remove('speaking');
      enableRecording();
      resolve();
    };
    try {
      const bytes = atob(base64mp3);
      const arr   = new Uint8Array(bytes.length);
      for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
      const blob  = new Blob([arr], { type: 'audio/mpeg' });
      const url   = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); done(); };
      audio.onerror = () => { done(); };
      audio.play().catch(() => done());
    } catch (e) {
      done();
    }
  });
}

function enableRecording() {
  const recordBtn = document.getElementById('btn-record');
  if (recordBtn) recordBtn.disabled = false;
  setHint('Press <strong>Start Recording</strong> to answer. When done, click <strong>Stop</strong> then <strong>Submit Answer</strong>.');
}

// ─── Recording ────────────────────────────────────

function toggleRecord() {
  if (state.isRecording) stopRecord();
  else startRecord();
}

async function startRecord() {
  try {
    await openCamera();
  } catch (e) {
    toast('Camera/microphone access denied. Please allow permissions.', 'error');
    return;
  }

  state.recordedChunks = [];
  let options = {};
  try {
    options = { mimeType: 'video/webm;codecs=vp9,opus' };
    new MediaRecorder(state.mediaStream, options);
  } catch (_) { options = {}; }

  state.mediaRecorder = new MediaRecorder(state.mediaStream, options);
  state.mediaRecorder.ondataavailable = e => {
    if (e.data.size > 0) state.recordedChunks.push(e.data);
  };
  state.mediaRecorder.start(100);
  state.isRecording = true;

  const btn       = document.getElementById('btn-record');
  const labelEl   = document.getElementById('btn-record-label');
  const recBadge  = document.getElementById('rec-indicator');
  const timerEl   = document.getElementById('timer-badge');
  const submitBtn = document.getElementById('btn-submit');
  const frame     = document.getElementById('iv-video-frame');

  if (btn)       btn.classList.add('recording');
  if (labelEl)   labelEl.textContent = 'Stop Recording';
  if (recBadge)  recBadge.classList.add('active');
  if (timerEl)   timerEl.textContent = '0:00';
  if (submitBtn) submitBtn.classList.remove('visible');
  if (frame)     frame.classList.add('recording-active');

  setHint('Recording in progress — speak clearly and at a natural pace.');

  state.recSeconds  = 0;
  state.recordTimer = setInterval(() => {
    state.recSeconds++;
    const m = Math.floor(state.recSeconds / 60);
    const s = state.recSeconds % 60;
    if (timerEl) timerEl.textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }, 1000);
}

function stopRecord() {
  if (!state.mediaRecorder) return;
  state.mediaRecorder.stop();
  state.isRecording = false;
  clearInterval(state.recordTimer);

  closeCamera();

  const btn       = document.getElementById('btn-record');
  const labelEl   = document.getElementById('btn-record-label');
  const recBadge  = document.getElementById('rec-indicator');
  const submitBtn = document.getElementById('btn-submit');

  if (btn)       btn.classList.remove('recording');
  if (labelEl)   labelEl.textContent = 'Re-record';
  if (recBadge)  recBadge.classList.remove('active');
  if (submitBtn) submitBtn.classList.add('visible');

  setHint('Happy with your answer? Click <strong>Submit Answer</strong>. Or press <strong>Re-record</strong> to redo it.');
}

// ─── Submit Response ──────────────────────────────

async function submitResponse() {
  if (state.recordedChunks.length === 0) {
    toast('Please record your answer first.', 'error');
    return;
  }

  const blob = new Blob(state.recordedChunks, { type: 'video/webm' });
  const fd   = new FormData();
  fd.append('video',          blob, 'response.webm');
  fd.append('session_id',     state.sessionId);
  fd.append('question_index', state.currentQIndex);
  fd.append('question_text',  state.currentQText);
  fd.append('question_type',  state.currentQType);

  showProcessing();

  try {
    const res  = await fetch(`${API}/submit_response`, {
      method:  'POST',
      headers: authHeaders(),
      body:    fd
    });
    const data = await res.json();
    hideProcessing();

    if (!res.ok) { toast(data.error || 'Submission failed.', 'error'); return; }

    addToTranscript(state.currentQIndex, state.currentQText, state.currentQType, data.transcript || '');

    if (data.status === 'completed') {
      // Show closing message if the LLM provided one
      if (data.closing_message) {
        const qCard  = document.getElementById('question-card');
        const textEl = document.getElementById('q-text');
        const typeTag = document.getElementById('q-type-tag');
        if (textEl)  textEl.textContent  = data.closing_message;
        if (typeTag) { typeTag.textContent = 'Session Complete'; typeTag.className = 'iv-q-type-badge closing'; }
        if (qCard)   qCard.className = 'iv-question-card';
      }
      toast(`Session complete! ${data.questions_answered} questions answered. Loading your report…`, 'success');
      closeCamera();
      setTimeout(() => loadReport(state.sessionId), 2000);

    } else {
      const nextIndex = data.next_index;
      const nextType  = data.next_type || 'technical';

      state.currentQIndex  = nextIndex;
      state.currentQText   = data.next_question;
      state.currentQType   = nextType;
      state.recordedChunks = [];

      updateQuestionCard(nextIndex, data.next_question, nextType);
      buildQPips(nextIndex);

      const submitBtn = document.getElementById('btn-submit');
      const recordBtn = document.getElementById('btn-record');
      const labelEl   = document.getElementById('btn-record-label');
      const timerEl   = document.getElementById('timer-badge');

      if (submitBtn) submitBtn.classList.remove('visible');
      if (recordBtn) recordBtn.disabled = true;
      if (labelEl)   labelEl.textContent = 'Start Recording';
      if (timerEl)   timerEl.textContent = '0:00';

      if (data.audio_b64) {
        await playAudio(data.audio_b64);
      } else {
        enableRecording();
      }
    }
  } catch (e) {
    hideProcessing();
    toast('Network error submitting response.', 'error');
    console.error(e);
  }
}

// ─── Transcript ───────────────────────────────────

function addToTranscript(qIndex, question, qType, transcript) {
  const log = document.getElementById('transcript-log');
  if (!log) return;

  const emptyEl = log.querySelector('.iv-transcript-empty');
  if (emptyEl) emptyEl.remove();

  const typeColors = {
    intro:        'var(--accent-2)',
    technical:    'var(--accent)',
    behavioural:  'var(--warn)',
    resume_probe: '#a78bfa',
    closing:      'var(--text-muted)'
  };
  const color     = typeColors[qType] || 'var(--accent)';
  const typeLabel = Q_TYPE_LABELS[qType] || qType;

  const item = document.createElement('div');
  item.className = 'iv-transcript-item';
  item.innerHTML = `
    <div class="iv-transcript-item-meta">
      <span class="iv-transcript-item-q" style="color:${color}">Q${qIndex}</span>
      <span style="font-size:10px;font-family:'DM Mono',monospace;color:${color};
                   background:rgba(255,255,255,0.04);padding:1px 7px;
                   border-radius:100px;border:1px solid rgba(255,255,255,0.06);">
        ${typeLabel}
      </span>
    </div>
    <div class="iv-transcript-item-text">${transcript || '(No transcription recorded)'}</div>
  `;
  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
}