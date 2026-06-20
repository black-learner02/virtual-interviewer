/* ═══════════════════════════════════════════════════
   PrepSpark — Shared State & Config
   ═══════════════════════════════════════════════════ */

const API = 'http://localhost:5000';

const state = {
  token: localStorage.getItem('ps_token') || null,
  user: JSON.parse(localStorage.getItem('ps_user') || 'null'),
  sessionId: null,
  currentQIndex: 1,
  currentQText: '',
  currentQType: 'intro',
  minQ: 5,          // Minimum questions before interview can end
  maxQ: 10,         // Hard cap on questions
  language: 'en',   // ISO 639-1 code for the current session
  hasResume: false,
  hasJD: false,
  mediaStream: null,
  mediaRecorder: null,
  recordedChunks: [],
  isRecording: false,
  recordTimer: null,
  recSeconds: 0,
  isSpeaking: false,
};

function authHeaders() {
  return { 'Authorization': `Bearer ${state.token}` };
}

function saveSession() {
  localStorage.setItem('ps_token', state.token);
  localStorage.setItem('ps_user', JSON.stringify(state.user));
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('ps_token');
  localStorage.removeItem('ps_user');
}