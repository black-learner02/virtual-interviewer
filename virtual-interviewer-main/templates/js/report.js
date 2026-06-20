/* ═══════════════════════════════════════════════════
   PrepSpark — Report Module
   Renders text report + embedded graph images.
   Provides PDF download via /download_report endpoint.
   ═══════════════════════════════════════════════════ */

const Q_TYPE_MAP = {
  1: 'intro', 2: 'technical', 3: 'technical',
  4: 'technical', 5: 'behavioural'
};

const SKIP_REPORT_KEYS = new Set([
  'recommendation', 'Recommendation', 'verdict', 'Verdict',
  'hiring_recommendation', 'executive_summary', 'Executive Summary',
  'summary', 'Summary'
]);

const INSIGHT_LABELS = {
  technical_depth:        'Technical Depth',
  technical_analysis:     'Technical Analysis',
  behavioral_signals:     'Behavioural Signals',
  behavioural_signals:    'Behavioural Signals',
  behavioral_analysis:    'Behavioural Analysis',
  communication:          'Communication Style',
  communication_style:    'Communication Style',
  key_observations:       'Key Observations',
  strengths:              'Strengths',
  Strengths:              'Strengths',
  areas_for_improvement:  'Areas to Improve',
  weaknesses:             'Weaknesses',
  content_analysis:       'Content Analysis',
  mental_state:           'Mental State',
  coaching_tips:          'Coaching Tips',
  resume_vs_reality:      'Resume vs Reality',
  jd_fit_analysis:        'Job Description Fit',
};

const GRAPH_META = {
  skill_radar:          { title: 'Skill Match Radar',            desc: 'Candidate skill strengths vs job requirements' },
  jd_match_bar:         { title: 'Resume vs JD Match',           desc: 'Required skills, preferred skills, and experience match %' },
  emotion_timeline:     { title: 'Emotion Timeline',             desc: 'Emotional state across the interview' },
  answer_quality:       { title: 'Answer Quality Breakdown',     desc: 'Clarity, technical depth, relevance, and confidence scored 0–10' },
  emotion_distribution: { title: 'Emotion Distribution',         desc: 'Overall emotional breakdown across all answers' },
  confidence_progress:  { title: 'Confidence Progress',          desc: 'Assessment confidence building as the interview progresses' },
};

const LANG_DISPLAY = {
  hi:'Hindi', ta:'Tamil', te:'Telugu', bn:'Bengali', kn:'Kannada',
  ml:'Malayalam', mr:'Marathi', pa:'Punjabi', gu:'Gujarati', ur:'Urdu',
  en:'English', es:'Spanish', fr:'French', de:'German', ar:'Arabic',
  ja:'Japanese', zh:'Chinese', ko:'Korean', pt:'Portuguese', ru:'Russian',
};


// ─────────────────────────────────────────────
// LOAD & RENDER
// ─────────────────────────────────────────────

async function loadReport(sessionId) {
  showPage('report-page');

  // Reset
  document.getElementById('rpt-title').textContent = 'Loading report…';
  document.getElementById('score-grid').innerHTML   = '';
  document.getElementById('analysis-grid').innerHTML = '';
  document.getElementById('qa-history').innerHTML   = '';
  document.getElementById('executive-summary-body').textContent = '';
  document.getElementById('graphs-grid').innerHTML  = '';
  document.getElementById('graphs-section').style.display = 'none';

  const dlBtn = document.getElementById('btn-download-pdf');
  if (dlBtn) { dlBtn.style.display = 'none'; dlBtn.dataset.sessionId = sessionId; }

  const existingBadge = document.getElementById('rpt-lang-badge');
  if (existingBadge) existingBadge.remove();

  try {
    const res  = await fetch(`${API}/generate_report?session_id=${sessionId}`, {
      headers: authHeaders()
    });
    const data = await res.json();

    if (!res.ok) {
      document.getElementById('rpt-title').textContent = 'Error loading report';
      toast(data.error || 'Failed to load report.', 'error');
      return;
    }
    renderReport(data);
  } catch (e) {
    document.getElementById('rpt-title').textContent = 'Error loading report';
    toast('Network error loading report.', 'error');
    console.error(e);
  }
}

function renderReport(data) {
  const { candidate, role, session_id, start_time, responses,
          report, language, graphs_b64, analytics } = data;

  // ── Header ──
  document.getElementById('rpt-title').textContent = candidate;
  document.getElementById('rpt-role').textContent  = role;
  document.getElementById('rpt-date').textContent  = start_time
    ? new Date(start_time).toLocaleDateString('en-US',
        { year:'numeric', month:'long', day:'numeric' })
    : 'Unknown date';
  document.getElementById('rpt-session').textContent = '#' + session_id;

  if (language && language !== 'en') {
    const langText  = LANG_DISPLAY[language] || language.toUpperCase();
    const langBadge = document.createElement('span');
    langBadge.id    = 'rpt-lang-badge';
    langBadge.style.cssText = [
      'display:inline-block','font-family:"DM Mono",monospace','font-size:11px',
      'color:var(--accent-2)','background:rgba(255,255,255,0.04)',
      'border:1px solid rgba(255,255,255,0.08)','border-radius:100px',
      'padding:2px 10px','margin-left:8px','vertical-align:middle',
    ].join(';');
    langBadge.textContent = '🌐 ' + langText;
    const sessionEl = document.getElementById('rpt-session');
    if (sessionEl?.parentNode) sessionEl.parentNode.insertBefore(langBadge, sessionEl.nextSibling);
  }

  // ── Show download button ──
  const dlBtn = document.getElementById('btn-download-pdf');
  if (dlBtn) {
    dlBtn.style.display     = 'flex';
    dlBtn.dataset.sessionId = session_id;
  }

  // ── Verdict ──
  const verdictRaw = (
    report?.recommendation || report?.Recommendation ||
    report?.verdict || report?.Verdict || ''
  ).toString().trim();

  const banner = document.getElementById('verdict-banner');
  const icon   = document.getElementById('verdict-icon');
  const vTitle = document.getElementById('verdict-title');
  const vSub   = document.getElementById('verdict-sub');

  banner.className = 'verdict-banner';
  if (!verdictRaw) {
    banner.classList.add('verdict-neutral');
    icon.textContent   = '📋';
    vTitle.textContent = 'Practice Session Complete';
    vSub.textContent   = 'Review the detailed feedback below.';
  } else {
    const v = verdictRaw.toLowerCase();
    const isHire   = (v.includes('hire') || v.includes('yes') || v.includes('strong') || v.includes('ready')) && !v.includes('no hire');
    const isNoHire = v.includes('no hire') || v.includes('not recommend') || v.includes('reject') || v.includes('more practice') || v.includes('weak');
    if (isHire) {
      banner.classList.add('verdict-hire');
      icon.textContent   = '✅';
      vTitle.textContent = 'Strong Fit — Interview-Ready';
    } else if (isNoHire) {
      banner.classList.add('verdict-no-hire');
      icon.textContent   = '📌';
      vTitle.textContent = 'Weak Fit — More Practice Needed';
    } else {
      banner.classList.add('verdict-training');
      icon.textContent   = '📈';
      vTitle.textContent = 'Moderate Fit — Keep Practising';
    }
    vSub.textContent = verdictRaw;
  }

  // ── Executive Summary ──
  const execSummary = report?.executive_summary || report?.['Executive Summary'] || null;
  const summaryEl   = document.getElementById('executive-summary-body');
  if (execSummary && typeof execSummary === 'string') {
    summaryEl.textContent = execSummary;
  } else {
    document.getElementById('exec-summary-section').style.display = 'none';
  }

  // ── Question Scores ──
  const scoreGrid = document.getElementById('score-grid');
  scoreGrid.innerHTML = '';
  let totalScore = 0;
  responses.forEach(r => {
    const s   = r.ai_score || 0;
    totalScore += s;
    const cls = s >= 8 ? 'high' : s >= 5 ? 'mid' : 'low';
    const qType = (r.question_type || Q_TYPE_MAP[r.question_index] || 'technical');
    const card  = document.createElement('div');
    card.className = 'score-card';
    card.innerHTML = `
      <div class="score-q-label">Q${r.question_index} · ${qType}</div>
      <div class="score-number ${cls}">${s}<span style="font-size:18px;opacity:0.4">/10</span></div>
      <div class="score-bar ${cls}" style="width:0" data-w="${s*10}%"></div>
    `;
    scoreGrid.appendChild(card);
  });
  const avg    = responses.length ? (totalScore / responses.length).toFixed(1) : 0;
  const avgCls = avg >= 8 ? 'high' : avg >= 5 ? 'mid' : 'low';
  const overallCard = document.createElement('div');
  overallCard.className = 'score-card';
  overallCard.innerHTML = `
    <div class="score-q-label">Overall Avg</div>
    <div class="score-number ${avgCls}">${avg}<span style="font-size:18px;opacity:0.4">/10</span></div>
    <div class="score-bar ${avgCls}" style="width:0" data-w="${avg*10}%"></div>
  `;
  scoreGrid.appendChild(overallCard);
  setTimeout(() => {
    document.querySelectorAll('.score-bar').forEach(b => { b.style.width = b.dataset.w; });
  }, 120);

  // ── Graphs ──
  if (graphs_b64 && Object.keys(graphs_b64).length > 0) {
    renderGraphs(graphs_b64);
  }

  // ── AI Insights ──
  const analysisGrid = document.getElementById('analysis-grid');
  analysisGrid.innerHTML = '';
  if (report && typeof report === 'object') {
    Object.entries(report).forEach(([key, value]) => {
      if (SKIP_REPORT_KEYS.has(key) || !value) return;
      const label = INSIGHT_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      let content = '';
      if (typeof value === 'string') {
        content = value;
      } else if (Array.isArray(value)) {
        content = value.map(item => typeof item === 'string' ? `• ${item}` : `• ${JSON.stringify(item)}`).join('\n');
      } else if (typeof value === 'object') {
        content = Object.entries(value).map(([k, v]) => `${k.replace(/_/g,' ')}: ${v}`).join('\n');
      }
      if (!content) return;
      const card = document.createElement('div');
      card.className = 'analysis-card';
      card.innerHTML = `
        <div class="analysis-card-title">${label}</div>
        <div class="analysis-card-body">${content}</div>
      `;
      analysisGrid.appendChild(card);
    });
  }
  if (analysisGrid.children.length === 0) {
    document.getElementById('insights-section').style.display = 'none';
  }

  // ── Q&A Transcript ──
  const qaHistory = document.getElementById('qa-history');
  qaHistory.innerHTML = '';
  responses.forEach(r => {
    const s          = r.ai_score || 0;
    const scoreColor = s >= 8 ? 'var(--score-high)' : s >= 5 ? 'var(--score-mid)' : 'var(--score-low)';
    const qType      = (r.question_type || Q_TYPE_MAP[r.question_index] || 'technical');
    const qTypeLabel = { intro:'Introduction', technical:'Technical', behavioural:'Behavioural',
                         resume_probe:'Resume Deep-Dive' }[qType] || qType;
    const qTypeClass = { intro:'intro', technical:'technical', behavioural:'behavioural',
                         resume_probe:'resume_probe' }[qType] || 'technical';
    let chips = '';
    try {
      const am = typeof r.audio_metrics === 'string' ? JSON.parse(r.audio_metrics) : (r.audio_metrics || {});
      if (am.wpm)                    chips += `<span class="beh-chip">${am.wpm} WPM</span>`;
      if (am.jitter_percent != null) chips += `<span class="beh-chip">Jitter ${am.jitter_percent}%</span>`;
      if (am.avg_pitch_hz)           chips += `<span class="beh-chip">${am.avg_pitch_hz} Hz</span>`;
    } catch(e) {}
    try {
      const vm = typeof r.video_metrics === 'string' ? JSON.parse(r.video_metrics) : (r.video_metrics || {});
      if (vm.eye_contact_percent != null) chips += `<span class="beh-chip">Eye contact ${vm.eye_contact_percent}%</span>`;
      if (vm.dominant_emotion)            chips += `<span class="beh-chip">${vm.dominant_emotion}</span>`;
    } catch(e) {}

    const item = document.createElement('div');
    item.className = 'qa-item';
    item.innerHTML = `
      <div class="qa-header" onclick="toggleQA(this)">
        <div class="qa-header-left">
          <div class="qa-q-meta">
            <span class="qa-q-num">Question ${r.question_index}</span>
            <span class="qa-q-type ${qTypeClass}">${qTypeLabel}</span>
          </div>
          <div class="qa-q-text">${r.question || '—'}</div>
        </div>
        <div class="qa-score-pill" style="color:${scoreColor}">${s}/10</div>
      </div>
      <div class="qa-body">
        <div class="qa-section-label">Your Answer</div>
        <div class="qa-transcript">${r.transcript || '(No transcription recorded)'}</div>
        <div class="qa-section-label">AI Feedback</div>
        <div class="qa-feedback">${r.ai_feedback || '—'}</div>
        ${chips ? `<div class="behavioral-chips">${chips}</div>` : ''}
      </div>
    `;
    qaHistory.appendChild(item);
  });
}

function toggleQA(header) {
  header.nextElementSibling.classList.toggle('open');
}


// ─────────────────────────────────────────────
// GRAPHS
// ─────────────────────────────────────────────

function renderGraphs(graphs_b64) {
  const section = document.getElementById('graphs-section');
  const grid    = document.getElementById('graphs-grid');
  if (!section || !grid) return;

  grid.innerHTML = '';
  let rendered   = 0;

  const order = [
    'skill_radar', 'jd_match_bar',
    'emotion_timeline', 'answer_quality',
    'emotion_distribution', 'confidence_progress',
  ];

  order.forEach(key => {
    const b64 = graphs_b64[key];
    if (!b64) return;

    const meta  = GRAPH_META[key] || { title: key, desc: '' };
    const card  = document.createElement('div');
    card.className = 'graph-card';
    card.innerHTML = `
      <div class="graph-card-title">${meta.title}</div>
      <div class="graph-card-desc">${meta.desc}</div>
      <img class="graph-img" src="data:image/png;base64,${b64}"
           alt="${meta.title}" loading="lazy">
    `;
    grid.appendChild(card);
    rendered++;
  });

  if (rendered > 0) {
    section.style.display = 'block';
  }
}


// ─────────────────────────────────────────────
// PDF DOWNLOAD
// ─────────────────────────────────────────────

async function downloadPDF() {
  const btn       = document.getElementById('btn-download-pdf');
  const labelEl   = document.getElementById('btn-download-label');
  const iconEl    = document.getElementById('btn-download-icon');
  const sessionId = btn?.dataset?.sessionId;
  if (!sessionId) return;

  // Show loading state
  if (labelEl) labelEl.textContent = 'Generating PDF…';
  if (iconEl)  iconEl.textContent  = '⏳';
  if (btn)     btn.disabled        = true;

  try {
    const res = await fetch(`${API}/download_report?session_id=${sessionId}`, {
      headers: authHeaders()
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      toast(err.error || 'PDF download failed.', 'error');
      return;
    }

    // Trigger browser download
    const blob     = await res.blob();
    const url      = URL.createObjectURL(blob);
    const a        = document.createElement('a');
    const filename = res.headers.get('Content-Disposition')
                      ?.match(/filename="?([^"]+)"?/)?.[1]
                    || `PrepSpark_Report_${sessionId}.pdf`;
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast('PDF downloaded successfully!', 'success');

  } catch (e) {
    toast('Network error. Could not download PDF.', 'error');
    console.error(e);
  } finally {
    if (labelEl) labelEl.textContent = 'Download Report PDF';
    if (iconEl)  iconEl.textContent  = '⬇';
    if (btn)     btn.disabled        = false;
  }
}