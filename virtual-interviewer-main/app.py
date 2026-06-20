import io

from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import re
import base64
import json
import database

from services.audio_service import AudioService
from services.video_service import VideoService
from services.timeline_service import TimelineService
from services.llm_service import LLMService
from services.tts_service import TTSService
from resume_extractor import extract_text as extract_resume_text
from report_generator import build_graphs, build_pdf

app = Flask(__name__)
CORS(app, supports_credentials=True)

database.init_db()

print("🚀 Booting PrepSpark…")
audio_svc    = AudioService()
video_svc    = VideoService()
timeline_svc = TimelineService()
llm_svc      = LLMService()
tts_svc      = TTSService()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Dynamic question limits — imported from llm_service for consistency
from services.llm_service import MIN_QUESTIONS, MAX_QUESTIONS

SUPPORTED_LANGUAGES = {
    'hi', 'ta', 'te', 'bn', 'kn', 'ml', 'mr', 'pa', 'gu', 'ur', 'or', 'as',
    'en', 'es', 'fr', 'de', 'ar', 'ja', 'zh', 'ko', 'pt', 'ru', 'it', 'nl',
    'tr', 'vi', 'th', 'id', 'auto'
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        user_id = database.validate_token(token)
        if not user_id:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def speak(text: str, language: str = 'en') -> str | None:
    """TTS → base64 MP3. Returns None if unavailable."""
    try:
        audio_bytes = tts_svc.synthesize(text, voice="onyx", language=language)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"⚠️  TTS failed (non-fatal): {e}")
    return None


def _validate_language(lang_code: str) -> str:
    code = (lang_code or 'en').strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        print(f"⚠️  Unknown language code '{code}', defaulting to 'en'.")
        return 'en'
    return code


def _build_interview_log(responses: list) -> list:
    log = []
    for r in responses:
        try:
            audio_m = json.loads(r.get("audio_metrics") or "{}")
        except Exception:
            audio_m = {}
        try:
            video_m = json.loads(r.get("video_metrics") or "{}")
        except Exception:
            video_m = {}
        log.append({
            "question_index": r.get("question_index"),
            "question_type":  r.get("question_type", "technical"),
            "question":       r.get("question_text"),
            "transcript":     r.get("transcript"),
            "ai_score":       r.get("ai_score", 0),
            "ai_feedback":    r.get("ai_feedback", ""),
            "audio_metrics":  audio_m,
            "video_metrics":  video_m,
        })
    return log


def _complete_session(session_id: str, session_info: dict):
    """
    Called once after the final question is answered.
    1. Generates LLM narrative report.
    2. Generates structured analytics data (for graphs).
    3. Generates 6 graph images.
    4. Assembles and stores a PDF report.
    5. Marks session COMPLETED.
    """
    try:
        print(f"📄 Generating report for session {session_id}…")
        _, responses = database.get_full_session_data(session_id)
        interview_log = _build_interview_log(responses)

        language        = session_info.get('language', 'en')
        resume_text     = session_info.get('resume_text') or None
        job_description = session_info.get('job_description') or None
        target_role     = session_info.get('target_role', 'Professional')

        # ── Step 1: LLM narrative report ──
        print("  → Generating narrative report…")
        detailed_report = llm_svc.generate_final_report(
            interview_log,
            language=language,
            resume_text=resume_text,
            job_description=job_description
        )

        full_payload = {
            "candidate":       session_info["candidate_name"],
            "role":            target_role,
            "session_id":      session_id,
            "start_time":      session_info.get("start_time", ""),
            "language":        language,
            "has_resume":      bool(resume_text),
            "has_jd":          bool(job_description),
            "total_questions": len(interview_log),
            "responses":       interview_log,
            "report":          detailed_report
        }
        database.save_report(session_id, full_payload)

        # ── Step 2: Analytics data (for graphs) ──
        print("  → Generating analytics…")
        analytics = llm_svc.generate_report_analytics(
            interview_log,
            target_role=target_role,
            resume_text=resume_text,
            job_description=job_description,
            language=language
        )

        # ── Step 3: Generate graph images ──
        print("  → Generating graphs…")
        graphs = build_graphs(interview_log, analytics)

        # ── Step 4: Build PDF ──
        print("  → Building PDF…")
        session_meta = {
            "candidate_name": session_info["candidate_name"],
            "target_role":    target_role,
            "company_name":   session_info.get("company_name", ""),
            "session_id":     session_id,
            "start_time":     session_info.get("start_time", ""),
            "language":       language,
            "total_questions": len(interview_log),
        }
        pdf_bytes = build_pdf(
            session_info=session_meta,
            analytics=analytics,
            report=detailed_report,
            responses=interview_log,
            graphs=graphs
        )
        database.save_pdf_report(session_id, pdf_bytes, analytics)

        # ── Step 5: Inject graph base64 into JSON payload for frontend display ──
        full_payload["analytics"] = analytics
        full_payload["graphs_b64"] = {k: base64.b64encode(v).decode() for k, v in graphs.items()}
        database.save_report(session_id, full_payload)

        database.mark_session_completed(session_id)
        print(f"✅ Session {session_id} COMPLETED — {len(interview_log)} questions, "
              f"PDF {len(pdf_bytes)//1024}KB, {len(graphs)} graphs.")

    except Exception as e:
        print(f"⚠️  Report generation failed: {e}")
        import traceback; traceback.print_exc()
        # Still mark completed even if PDF/graphs fail, so user can see text report
        try:
            database.mark_session_completed(session_id)
        except Exception:
            pass


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    data      = request.get_json() or {}
    username  = data.get('username', '').strip()
    email     = data.get('email', '').strip()
    password  = data.get('password', '')
    full_name = data.get('full_name', '').strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400
    if len(username) < 3 or len(username) > 30:
        return jsonify({"error": "Username must be 3–30 characters."}), 400
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "Username: letters, numbers, underscores only."}), 400
    if not re.match(r'^[\w\.\-]+@[\w\.\-]+\.\w{2,}$', email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    success, result = database.register_user(username, email, password, full_name)
    if not success:
        return jsonify({"error": result}), 409
    return jsonify({"message": "Account created! Please log in."}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data       = request.get_json() or {}
    identifier = data.get('username_or_email', '').strip()
    password   = data.get('password', '')
    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400
    success, result = database.login_user(identifier, password)
    if not success:
        return jsonify({"error": result}), 401
    return jsonify({
        "message": "Login successful.",
        "token":   result["token"],
        "user": {
            "user_id":   result["user_id"],
            "username":  result["username"],
            "full_name": result["full_name"]
        }
    })


@app.route('/auth/logout', methods=['POST'])
@require_auth
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    database.logout_user(token)
    return jsonify({"message": "Logged out."})


@app.route('/auth/me', methods=['GET'])
@require_auth
def get_me():
    return jsonify({"user_id": request.user_id})


# ─────────────────────────────────────────────
# RESUME TEXT EXTRACTION
# ─────────────────────────────────────────────

# Max file size: 5 MB — enough for any resume, prevents abuse
RESUME_MAX_BYTES = 5 * 1024 * 1024
RESUME_ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}

@app.route('/extract_resume', methods=['POST'])
@require_auth
def extract_resume():
    """
    Accepts a resume file upload and returns the extracted plain text.
    Supported: PDF, DOCX, DOC, TXT, RTF.
    The frontend pastes this text into the resume textarea.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({"error": "Empty filename."}), 400

    _, ext = os.path.splitext(f.filename.lower())
    if ext not in RESUME_ALLOWED_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported file type '{ext}'. Please upload a PDF, DOCX, DOC, TXT, or RTF file."
        }), 415

    file_bytes = f.read()
    if len(file_bytes) > RESUME_MAX_BYTES:
        return jsonify({"error": "File too large. Maximum resume size is 5 MB."}), 413
    if len(file_bytes) == 0:
        return jsonify({"error": "The uploaded file is empty."}), 400

    text, error = extract_resume_text(file_bytes, f.filename)
    if error:
        return jsonify({"error": error}), 422

    return jsonify({
        "text":       text,
        "char_count": len(text),
        "filename":   f.filename
    })


# ─────────────────────────────────────────────
# START NEW INTERVIEW
# ─────────────────────────────────────────────

@app.route('/start_interview', methods=['POST'])
@require_auth
def start_interview():
    data            = request.get_json() or {}
    name            = data.get('name', 'Candidate').strip() or 'Candidate'
    role            = data.get('role', 'Software Developer').strip() or 'Software Developer'
    language        = _validate_language(data.get('language', 'en'))
    resume_text     = (data.get('resume_text') or '').strip() or None
    job_description = (data.get('job_description') or '').strip() or None

    # Truncate to keep DB and prompts lean
    if resume_text:
        resume_text = resume_text[:5000]
    if job_description:
        job_description = job_description[:3000]

    session_id = str(uuid.uuid4())[:8]
    database.create_session(
        session_id, name, role,
        user_id=request.user_id,
        language=language,
        resume_text=resume_text,
        job_description=job_description
    )

    print(f"🌐 Starting interview | lang={language} | role={role} "
          f"| resume={'yes' if resume_text else 'no'} "
          f"| jd={'yes' if job_description else 'no'}")

    first_question = llm_svc.generate_opening_question(
        name, role,
        resume_text=resume_text,
        job_description=job_description,
        language=language
    )

    audio_b64 = speak(first_question, language=language)

    return jsonify({
        "session_id":       session_id,
        "question":         first_question,
        "question_index":   1,
        "question_type":    "intro",
        "min_questions":    MIN_QUESTIONS,
        "max_questions":    MAX_QUESTIONS,
        "language":         language,
        "has_resume":       bool(resume_text),
        "has_jd":           bool(job_description),
        "audio_b64":        audio_b64
    })


# ─────────────────────────────────────────────
# RESUME INTERVIEW (continue interrupted session)
# ─────────────────────────────────────────────

@app.route('/resume_interview', methods=['GET'])
@require_auth
def resume_interview():
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if session_info.get('status') == 'COMPLETED':
        return jsonify({"error": "This session is already completed."}), 400

    language        = session_info.get('language', 'en')
    resume_text     = session_info.get('resume_text') or None
    job_description = session_info.get('job_description') or None

    answered_indices = {r['question_index'] for r in responses}
    next_index = 1
    for i in range(1, MAX_QUESTIONS + 1):
        if i not in answered_indices:
            next_index = i
            break

    chat_history = database.get_chat_history(session_id)

    # Determine next question type from chat history coverage
    types_covered = [item.get('q_type', '') for item in chat_history]
    if not types_covered:
        next_q_type = 'intro'
    elif 'intro' not in types_covered:
        next_q_type = 'intro'
    elif 'behavioural' not in types_covered and len(types_covered) >= 3:
        next_q_type = 'behavioural'
    elif resume_text and 'resume_probe' not in types_covered and len(types_covered) >= 2:
        next_q_type = 'resume_probe'
    else:
        next_q_type = 'technical'

    print(f"🔄 Resuming session {session_id} at Q{next_index} [{next_q_type}] | lang={language}…")
    try:
        llm_result = llm_svc.generate_resume_question(
            target_role=session_info['target_role'],
            q_index=next_index,
            q_type=next_q_type,
            chat_history=chat_history,
            language=language,
            resume_text=resume_text,
            job_description=job_description
        )
        next_question = llm_result.get(
            'question',
            f"Let's continue. Can you tell me about your experience with {session_info['target_role']} projects?"
        )
        next_q_type = llm_result.get('q_type', next_q_type)
    except Exception as e:
        print(f"⚠️  LLM resume question failed: {e}")
        next_question = f"Welcome back! Continuing from question {next_index}. Can you tell me about a challenging project you've worked on?"

    audio_b64 = speak(next_question, language=language)

    completed = []
    for r in responses:
        completed.append({
            "question_index": r["question_index"],
            "question_text":  r["question_text"],
            "question_type":  r.get("question_type", "technical"),
            "transcript":     r.get("transcript", ""),
        })

    return jsonify({
        "session_id":          session_id,
        "candidate_name":      session_info["candidate_name"],
        "target_role":         session_info["target_role"],
        "language":            language,
        "has_resume":          bool(resume_text),
        "has_jd":              bool(job_description),
        "next_question_index": next_index,
        "next_question":       next_question,
        "next_question_type":  next_q_type,
        "min_questions":       MIN_QUESTIONS,
        "max_questions":       MAX_QUESTIONS,
        "completed_responses": completed,
        "audio_b64":           audio_b64
    })


# ─────────────────────────────────────────────
# SUBMIT RESPONSE
# ─────────────────────────────────────────────

@app.route('/submit_response', methods=['POST'])
@require_auth
def submit_response():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided."}), 400

    session_id     = request.form.get('session_id', '').strip()
    current_q_text = request.form.get('question_text', '').strip()
    current_q_type = request.form.get('question_type', 'technical').strip()

    try:
        current_q_index = int(request.form.get('question_index', 1))
    except ValueError:
        return jsonify({"error": "Invalid question_index."}), 400

    if not session_id or not current_q_text:
        return jsonify({"error": "session_id and question_text are required."}), 400

    session_info, _ = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if session_info.get('status') == 'COMPLETED':
        return jsonify({"error": "This session is already completed."}), 400

    language        = session_info.get('language', 'en')
    resume_text     = session_info.get('resume_text') or None
    job_description = session_info.get('job_description') or None

    video_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_{current_q_index}.webm")
    request.files['video'].save(video_path)

    try:
        print(f"▶️  Processing Q{current_q_index} [{current_q_type}] — session {session_id} | lang={language}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_video = pool.submit(video_svc.analyze, video_path)
            f_audio = pool.submit(audio_svc.analyze, video_path, language)
            video_data = f_video.result()
            audio_data = f_audio.result()
        timeline = timeline_svc.fuse(audio_data, video_data)

        transcript     = audio_data.get('transcript', '')
        global_metrics = audio_data.get('global_metrics', {
            'wpm': 0, 'avg_pitch_hz': 0, 'pitch_variance': 0,
            'jitter_percent': 0, 'duration_seconds': 0
        })
        video_summary = video_data.get('summary', {})
        video_summary['timeline_snippet'] = timeline[:5]

        chat_history = database.get_chat_history(session_id) if current_q_index > 1 else []

        print("🧠 AI evaluation…")
        llm_result = llm_svc.analyze_response(
            transcript=transcript,
            timeline=timeline,
            audio_summary=global_metrics,
            video_summary=video_summary,
            current_question=current_q_text,
            current_q_type=current_q_type,
            chat_history=chat_history,
            target_role=session_info['target_role'],
            current_q_index=current_q_index,
            language=language,
            resume_text=resume_text,
            job_description=job_description
        )

        ai_feedback        = llm_result.get('feedback', 'No feedback generated.')
        ai_score           = llm_result.get('score', 0)
        next_question      = llm_result.get('next_question', '')
        next_q_type        = llm_result.get('next_q_type', 'technical')
        interview_complete = llm_result.get('interview_complete', False)

        # Force completion at max questions
        if current_q_index >= MAX_QUESTIONS:
            interview_complete = True

        database.save_response(
            session_id=session_id,
            q_index=current_q_index,
            question=current_q_text,
            question_type=current_q_type,
            transcript=transcript,
            audio_metrics=global_metrics,
            video_metrics=video_summary,
            timeline=timeline,
            ai_feedback=ai_feedback,
            ai_score=ai_score
        )

    except Exception as e:
        print(f"🔥 Processing error: {e}")
        import traceback; traceback.print_exc()
        if os.path.exists(video_path):
            os.remove(video_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

    # ── Interview complete ──
    if interview_complete:
        _complete_session(session_id, session_info)
        return jsonify({
            "status":            "completed",
            "message":           "Session complete.",
            "closing_message":   next_question,
            "transcript":        transcript,
            "questions_answered": current_q_index
        })

    # ── More questions remaining ──
    next_index = current_q_index + 1
    audio_b64  = speak(next_question, language=language)
    return jsonify({
        "status":           "next_question",
        "next_question":    next_question,
        "next_index":       next_index,
        "next_type":        next_q_type,
        "feedback_preview": ai_feedback,
        "audio_b64":        audio_b64,
        "transcript":       transcript
    })


# ─────────────────────────────────────────────
# GET REPORT
# ─────────────────────────────────────────────

@app.route('/generate_report', methods=['GET'])
@require_auth
def get_report():
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403

    if session_info.get('status') != 'COMPLETED':
        return jsonify({
            "error":  "This session is not yet complete.",
            "status": session_info.get('status', 'IN_PROGRESS')
        }), 400

    report = database.get_stored_report(session_id)
    if not report:
        print(f"⚠️  Report missing for completed session {session_id}. Regenerating…")
        language        = session_info.get('language', 'en')
        resume_text     = session_info.get('resume_text') or None
        job_description = session_info.get('job_description') or None
        interview_log   = _build_interview_log(responses)
        detailed_report = llm_svc.generate_final_report(
            interview_log,
            language=language,
            resume_text=resume_text,
            job_description=job_description
        )
        analytics = llm_svc.generate_report_analytics(
            interview_log, target_role=session_info["target_role"],
            resume_text=resume_text, job_description=job_description
        )
        graphs = build_graphs(interview_log, analytics)
        report = {
            "candidate":       session_info["candidate_name"],
            "role":            session_info["target_role"],
            "session_id":      session_id,
            "start_time":      session_info.get("start_time", ""),
            "language":        language,
            "has_resume":      bool(resume_text),
            "has_jd":          bool(job_description),
            "total_questions": len(interview_log),
            "responses":       interview_log,
            "report":          detailed_report,
            "analytics":       analytics,
            "graphs_b64":      {k: base64.b64encode(v).decode() for k, v in graphs.items()},
        }
        database.save_report(session_id, report)

    return jsonify(report)


# ─────────────────────────────────────────────
# DOWNLOAD PDF REPORT
# ─────────────────────────────────────────────

@app.route('/download_report', methods=['GET'])
@require_auth
def download_report():
    """
    Streams the stored PDF for a completed session.
    If the PDF hasn't been generated yet (e.g. generation failed),
    it regenerates it on demand.
    """
    from flask import send_file
    session_id = request.args.get('session_id', '').strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session_info, responses = database.get_full_session_data(session_id)
    if not session_info:
        return jsonify({"error": "Session not found."}), 404
    if session_info.get('user_id') != request.user_id:
        return jsonify({"error": "Access denied."}), 403
    if session_info.get('status') != 'COMPLETED':
        return jsonify({"error": "Session is not yet completed."}), 400

    pdf_bytes, analytics = database.get_pdf_report(session_id)

    # Regenerate if not cached
    if not pdf_bytes:
        print(f"⚠️  PDF missing for {session_id}. Regenerating…")
        try:
            language        = session_info.get('language', 'en')
            resume_text     = session_info.get('resume_text') or None
            job_description = session_info.get('job_description') or None
            target_role     = session_info.get('target_role', 'Professional')
            interview_log   = _build_interview_log(responses)

            stored_report   = database.get_stored_report(session_id)
            detailed_report = stored_report.get('report', {}) if stored_report else {}

            analytics = llm_svc.generate_report_analytics(
                interview_log, target_role=target_role,
                resume_text=resume_text, job_description=job_description
            )
            graphs     = build_graphs(interview_log, analytics)
            session_meta = {
                "candidate_name": session_info["candidate_name"],
                "target_role":    target_role,
                "session_id":     session_id,
                "start_time":     session_info.get("start_time", ""),
                "language":       language,
                "total_questions": len(interview_log),
            }
            pdf_bytes = build_pdf(
                session_info=session_meta,
                analytics=analytics,
                report=detailed_report,
                responses=interview_log,
                graphs=graphs
            )
            database.save_pdf_report(session_id, pdf_bytes, analytics)
        except Exception as e:
            print(f"🔥 PDF regeneration failed: {e}")
            import traceback; traceback.print_exc()
            return jsonify({"error": f"PDF generation failed: {str(e)}"}), 500

    candidate_name = session_info.get('candidate_name', 'candidate').replace(' ', '_')
    filename       = f"PrepSpark_Report_{candidate_name}_{session_id}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@app.route('/my_interviews', methods=['GET'])
@require_auth
def my_interviews():
    interviews = database.get_user_interviews(request.user_id)
    return jsonify({"interviews": interviews})


if __name__ == '__main__':
    app.run(debug=True, port=5000)