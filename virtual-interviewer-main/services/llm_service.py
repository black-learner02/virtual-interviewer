import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
MIN_QUESTIONS = 5   # LLM cannot end the session before this many answers
MAX_QUESTIONS = 15  # Session is force-ended at this count regardless


class LLMService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    # ─────────────────────────────────────────────
    # LANGUAGE SUPPORT
    # ─────────────────────────────────────────────

    LANGUAGE_NAMES = {
        'hi': 'Hindi', 'ta': 'Tamil', 'te': 'Telugu', 'bn': 'Bengali',
        'kn': 'Kannada', 'ml': 'Malayalam', 'mr': 'Marathi', 'pa': 'Punjabi',
        'gu': 'Gujarati', 'ur': 'Urdu', 'or': 'Odia', 'as': 'Assamese',
        'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
        'ar': 'Arabic', 'ja': 'Japanese', 'zh': 'Chinese', 'ko': 'Korean',
        'pt': 'Portuguese', 'ru': 'Russian', 'it': 'Italian', 'nl': 'Dutch',
        'tr': 'Turkish', 'vi': 'Vietnamese', 'th': 'Thai', 'id': 'Indonesian',
    }

    def _lang_name(self, code: str) -> str:
        return self.LANGUAGE_NAMES.get(code.lower(), 'English')

    def _lang_instruction(self, language: str) -> str:
        lang_name = self._lang_name(language)
        if language.lower() == 'en':
            return ""
        return (
            f"LANGUAGE INSTRUCTION: You MUST write all response text in {lang_name}.\n"
            f"This includes feedback, questions, summaries, and any prose fields.\n"
            f"JSON keys must remain in English exactly as specified.\n"
            f"Only the VALUES of string fields should be in {lang_name}.\n"
            f"Do NOT mix languages. Do NOT fall back to English.\n\n"
        )

    # ─────────────────────────────────────────────
    # CONTEXT BUILDERS
    # ─────────────────────────────────────────────

    def _build_context_block(self, resume_text: str = None,
                              job_description: str = None) -> str:
        """Builds the resume/JD context block injected into every prompt."""
        parts = []
        if resume_text and resume_text.strip():
            truncated = resume_text.strip()[:3000]
            parts.append(f"CANDIDATE RESUME:\n{truncated}")
        if job_description and job_description.strip():
            truncated = job_description.strip()[:2000]
            parts.append(f"JOB DESCRIPTION:\n{truncated}")
        if parts:
            return "\n\n".join(parts) + "\n\n"
        return ""

    def _build_history_text(self, chat_history: list) -> str:
        if not chat_history:
            return ""
        text = "CONVERSATION SO FAR:\n"
        for item in chat_history:
            q = item.get('q_text', '')
            t = item.get('q_type', 'technical')
            a = (item.get('transcript', '') or '')[:300]
            text += f"- [{t.upper()}] Q: {q}\n  A: {a}\n"
        return text

    # ─────────────────────────────────────────────
    # OPENING QUESTION
    # ─────────────────────────────────────────────

    def generate_opening_question(self, candidate_name: str, target_role: str,
                                   resume_text: str = None,
                                   job_description: str = None,
                                   language: str = 'en') -> str:
        """Generates a warm, personalised opening greeting for the interview."""
        lang_name = self._lang_name(language)
        lang_instruction = self._lang_instruction(language)
        context_block = self._build_context_block(resume_text, job_description)

        # Build a personalised hook if resume is available
        resume_hint = ""
        if resume_text and resume_text.strip():
            resume_hint = (
                "You have access to the candidate's resume — weave one specific, "
                "concrete detail from it (a project, a company, a technology they listed) "
                "naturally into your opening to show you've read it. This makes the greeting "
                "feel personal, not generic."
            )

        prompt = f"""{lang_instruction}You are an AI interviewer for PrepSpark. Generate a warm, professional opening greeting for a mock interview.

{context_block}Candidate name: {candidate_name}
Target role: {target_role}

{resume_hint}

The greeting should:
- Welcome the candidate by their first name
- Mention the role they are practising for
- Ask them to introduce themselves and their background (if resume provided, ask them to walk you through the highlights)
- Be 2-3 sentences, natural and friendly
- Be written entirely in {lang_name}

Respond with ONLY the greeting text. No JSON, no labels, no extra commentary."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"❌ Opening question error: {e}")
            return (
                f"Hello {candidate_name}, welcome to your PrepSpark practice session "
                f"for the {target_role} role. "
                f"Let's start — please tell me about yourself and your background."
            )

    # ─────────────────────────────────────────────
    # ANALYSE RESPONSE + GENERATE NEXT QUESTION
    # ─────────────────────────────────────────────

    def analyze_response(self, transcript, timeline, audio_summary, video_summary,
                         current_question, current_q_type, chat_history,
                         target_role, current_q_index, language: str = 'en',
                         resume_text: str = None, job_description: str = None):
        """
        Evaluates the candidate's answer and either generates the next question
        or signals that the interview is complete.

        Dynamic completion logic:
        - After MIN_QUESTIONS answered: LLM may decide to end if coverage is sufficient.
        - At MAX_QUESTIONS: always ends.

        Returns a dict with keys:
          feedback        : str  — coaching feedback
          next_question   : str  — next question text (or closing if complete)
          next_q_type     : str  — 'intro' | 'technical' | 'behavioural' | 'resume_probe'
          score           : int  — 1-10
          interview_complete : bool
        """
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)
        context_block = self._build_context_block(resume_text, job_description)
        history_text = self._build_history_text(chat_history)

        # ── Build timeline string ──
        timeline_str = ""
        for event in timeline[:20]:
            t = event.get('timestamp', '')
            if event.get('event') == "LONG_PAUSE":
                timeline_str += f"[{t}] SILENCE ({event.get('duration', '')}s)\n"
            else:
                beh = event.get('behavior', {})
                timeline_str += (
                    f"[{t}] Eyes={beh.get('eye_contact', 'Screen')}, "
                    f"Face={beh.get('expression', 'Neutral')}\n"
                )

        force_complete = (current_q_index >= MAX_QUESTIONS)
        can_complete   = (current_q_index >= MIN_QUESTIONS)

        # ── Coverage checklist for the LLM to reason about ──
        types_covered = [item.get('q_type', '') for item in chat_history]
        has_intro       = 'intro'       in types_covered
        has_technical   = 'technical'   in types_covered or 'resume_probe' in types_covered
        has_behavioural = 'behavioural' in types_covered

        coverage_note = (
            f"Coverage so far — Intro: {'✓' if has_intro else '✗'}, "
            f"Technical: {'✓' if has_technical else '✗'}, "
            f"Behavioural: {'✓' if has_behavioural else '✗'}."
        )

        has_resume = bool(resume_text and resume_text.strip())
        has_jd     = bool(job_description and job_description.strip())

        if force_complete:
            completion_instruction = (
                "IMPORTANT: This is the FINAL question (max limit reached). "
                "Set interview_complete to true. "
                "next_question must be a warm closing message (not another question). "
                "next_q_type should be 'closing'."
            )
        elif can_complete:
            completion_instruction = f"""
COMPLETION DECISION: You have collected {current_q_index} answers. {coverage_note}
{"Resume claims have been probed." if has_resume else "No resume was provided."}
{"Job description requirements have been addressed." if has_jd else "No job description was provided."}

Set interview_complete to TRUE if ALL of the following are satisfied:
  1. Intro/background has been covered.
  2. At least 2-3 technical questions have been asked and answered.
  3. At least 1 behavioural/situational question has been asked.
  4. If resume was provided: at least 1-2 specific resume claims have been probed.
  5. If job description was provided: core required skills have been tested.
  6. You have enough signal to evaluate fit for the {target_role} role.

Set interview_complete to FALSE and continue if there are meaningful gaps still to explore.
When continuing, choose the MOST VALUABLE next question type: 'technical', 'behavioural', or 'resume_probe'.
'resume_probe' = a targeted question about a specific experience or claim from the candidate's resume.
"""
        else:
            completion_instruction = (
                f"IMPORTANT: Only {current_q_index} of a minimum {MIN_QUESTIONS} questions answered. "
                "Set interview_complete to false. Continue the interview. "
                f"{coverage_note} "
                "Choose the most appropriate next question type: 'technical', 'behavioural', or 'resume_probe'."
            )

        # ── Next question type guidance ──
        next_q_guidance = {
            'technical': (
                f"Ask ONE specific, progressively harder technical question for a {target_role} role. "
                f"Focus on problem-solving, system design, algorithms, or role-specific tools. "
                f"Do NOT repeat topics already covered."
            ),
            'behavioural': (
                "Ask ONE behavioural question using STAR format. "
                "Examples: handling a difficult deadline, resolving a team conflict, "
                "learning something new under pressure, a project you are proud of. "
                "Pick the one most relevant to prior answers and the role."
            ),
            'resume_probe': (
                "Pick ONE specific claim, project, technology, or achievement from the candidate's resume "
                "and ask a probing follow-up to verify depth and authenticity. "
                "Example: 'You mentioned X project — walk me through the technical challenges you faced.' "
                "Be specific; reference the actual resume detail."
            ),
            'intro': "Ask a natural self-introduction or background follow-up."
        }

        prompt = f"""{lang_instruction}You are an expert AI interviewer at PrepSpark evaluating a candidate for a {target_role} role.

{context_block}{history_text}

CURRENT ANSWER:
Question {current_q_index} [{current_q_type}]: "{current_question}"
Candidate's answer: "{transcript}"

BEHAVIOURAL DATA:
{timeline_str if timeline_str else "(No timeline data)"}
Acoustics: WPM={audio_summary.get('wpm', 'N/A')}, Jitter={audio_summary.get('jitter_percent', 'N/A')}%
Eye contact: {video_summary.get('eye_contact_percent', 'N/A')}%, Emotion: {video_summary.get('dominant_emotion', 'Neutral')}

EVALUATION RULES:
1. Score 1-10 on: technical accuracy, depth, clarity, relevance to the role.
2. If resume/JD provided, factor in how well the answer matches stated experience and role requirements.
3. Feedback must be coaching-style (constructive, 2-3 sentences) in {lang_name}.
4. Do NOT say "great answer", "well done", or reveal the numeric score in feedback.
5. If answer is vague or contradicts the resume, note it specifically.

{completion_instruction}

Next question guidance (use this if interview_complete is false):
{json.dumps(next_q_guidance, indent=2)}

Respond ONLY with valid JSON (no markdown, no code fences):
{{
  "feedback": "2-3 sentences of honest coaching feedback in {lang_name}",
  "next_question": "The next question OR a closing message (in {lang_name})",
  "next_q_type": "technical | behavioural | resume_probe | intro | closing",
  "score": 7,
  "interview_complete": false
}}"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)

            # Force override if at max questions
            if force_complete:
                result['interview_complete'] = True

            # Safety net: if marked complete but closing text looks like a question, override
            if result.get('interview_complete'):
                nq = result.get('next_question', '')
                suspicious_starts = ('tell me', 'can you', 'describe', 'explain',
                                     'what is', 'what are', 'how would', 'walk me',
                                     'could you', 'give me', 'have you')
                if any(nq.lower().startswith(s) for s in suspicious_starts):
                    result['next_question'] = self._generate_closing_message(language)
                result['next_q_type'] = 'closing'

            return result

        except Exception as e:
            print(f"❌ AI analyze_response error: {e}")
            is_last = force_complete or (can_complete and current_q_index >= MIN_QUESTIONS)
            return {
                "feedback": "Could not analyse this response due to a system error.",
                "next_question": (
                    self._generate_closing_message(language)
                    if is_last else
                    f"Let's continue. For a {target_role} role, can you walk me through "
                    f"how you would approach designing a scalable, fault-tolerant system?"
                ),
                "next_q_type": "closing" if is_last else "technical",
                "score": 0,
                "interview_complete": is_last
            }

    def _generate_closing_message(self, language: str) -> str:
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)
        prompt = (
            f"{lang_instruction}Write a short 1-2 sentence closing message for a mock interview app "
            f"telling the candidate their practice session is complete and their detailed report is ready to view. "
            f"Be warm and encouraging. Write only in {lang_name}. No JSON, no labels."
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return (
                "That wraps up our practice session! Your report is ready — "
                "head over to review your scores and personalised coaching tips."
            )

    # ─────────────────────────────────────────────
    # RESUME INTERVIEW (continue interrupted session)
    # ─────────────────────────────────────────────

    def generate_resume_question(self, target_role: str, q_index: int,
                                  q_type: str, chat_history: list,
                                  language: str = 'en',
                                  resume_text: str = None,
                                  job_description: str = None) -> dict:
        """Generates the next question when a candidate resumes an interrupted session."""
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)
        context_block = self._build_context_block(resume_text, job_description)
        history_text = self._build_history_text(chat_history)

        type_instructions = {
            'intro':        "Ask a natural self-introduction or background question.",
            'technical':    f"Ask ONE concrete technical question for a {target_role} role (algorithms, system design, tools). Make it relevant to any resume/JD context provided.",
            'behavioural':  "Ask ONE STAR-format behavioural question relevant to the role.",
            'resume_probe': "Pick ONE specific claim or project from the candidate's resume and ask a pointed follow-up to verify depth and authenticity.",
        }.get(q_type, "Ask a relevant technical question.")

        prompt = f"""{lang_instruction}You are an AI interviewer at PrepSpark. A candidate is resuming practice for a {target_role} role at question {q_index}.

{context_block}{history_text}
Generate question {q_index} (type: {q_type}).
{type_instructions}
Rules: 1-2 sentences, flows naturally from prior answers, no greeting or 'welcome back'.
The question MUST be written in {lang_name}.

Respond ONLY with JSON: {{"question": "Your question here in {lang_name}",  "q_type": "{q_type}"}}"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Resume question error: {e}")
            return {"question": "Can you describe a challenging technical problem you solved recently and walk me through your approach?", "q_type": q_type}

    # ─────────────────────────────────────────────
    # FINAL REPORT
    # ─────────────────────────────────────────────

    def generate_final_report(self, interview_log: list, language: str = 'en',
                               resume_text: str = None,
                               job_description: str = None) -> dict:
        """
        Generates the executive performance report once, after the interview ends.
        Incorporates resume and JD context for a more personalised analysis.
        """
        lang_instruction = self._lang_instruction(language)
        lang_name = self._lang_name(language)
        context_block = self._build_context_block(resume_text, job_description)

        total_q = len(interview_log)

        lean_log = []
        for r in interview_log:
            lean_log.append({
                "question_index": r.get("question_index"),
                "question_type":  r.get("question_type"),
                "question":       r.get("question"),
                "transcript":     (r.get("transcript") or "")[:400],
                "ai_score":       r.get("ai_score", 0),
                "ai_feedback":    r.get("ai_feedback", ""),
                "audio_metrics":  {
                    "wpm":            r.get("audio_metrics", {}).get("wpm"),
                    "jitter_percent": r.get("audio_metrics", {}).get("jitter_percent"),
                },
                "video_metrics": {
                    "eye_contact_percent": r.get("video_metrics", {}).get("eye_contact_percent"),
                    "dominant_emotion":    r.get("video_metrics", {}).get("dominant_emotion"),
                }
            })

        resume_analysis_instruction = ""
        if resume_text and resume_text.strip():
            resume_analysis_instruction = (
                "\n- resume_vs_reality: Analyse how well the candidate's answers matched the "
                "claims on their resume. Note any gaps, exaggerations, or strong verifications. "
                f"Write in {lang_name}."
            )

        jd_fit_instruction = ""
        if job_description and job_description.strip():
            jd_fit_instruction = (
                "\n- jd_fit_analysis: Evaluate how well the candidate's demonstrated skills and "
                "experience align with the job description requirements. Highlight matched strengths "
                f"and unaddressed gaps. Write in {lang_name}."
            )

        prompt = f"""{lang_instruction}You are an expert interview coach at PrepSpark generating a post-session performance report.

{context_block}INTERVIEW DATA ({total_q} questions):
{json.dumps(lean_log, indent=2)}

IMPORTANT: JSON keys must stay in English exactly as shown below.
Only the VALUES (the text content) must be written in {lang_name}.

Generate a JSON report with EXACTLY these keys:
{{
  "executive_summary": "2-3 plain sentences on overall performance, key strength, and the single most important thing to improve. Write in {lang_name}.",
  "recommendation": "One of exactly: 'Interview-Ready' | 'Getting There — Keep Practising' | 'More Practice Recommended'",
  "technical_depth": "Prose analysis of technical answers — what concepts were demonstrated, what was missing, and how it matches the target role. Write in {lang_name}.",
  "communication_style": "Prose analysis of clarity, confidence, WPM, and jitter if data available. Write in {lang_name}.",
  "behavioural_signals": "Prose analysis of eye contact, emotion patterns, and composure observed. Write in {lang_name}.",
  "strengths": ["plain string in {lang_name}", "plain string in {lang_name}", "plain string in {lang_name}"],
  "areas_for_improvement": ["plain string in {lang_name}", "plain string in {lang_name}", "plain string in {lang_name}"],
  "coaching_tips": "3-4 specific, actionable tips to improve before a real interview. Write in {lang_name}."{resume_analysis_instruction}{jd_fit_instruction}
}}

Rules:
- All string values = plain prose in {lang_name}. No nested objects inside strings.
- strengths and areas_for_improvement = JSON arrays of plain strings only.
- Be honest and encouraging — this is practice, not rejection.
- Only include resume_vs_reality if a resume was provided; only include jd_fit_analysis if a JD was provided.
- Output ONLY the JSON object, no markdown fences."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ Report generation error: {e}")
            return {
                "error": str(e),
                "executive_summary": "Report generation encountered an error. Please try again.",
                "recommendation": "More Practice Recommended"
            }

    # ─────────────────────────────────────────────
    # REPORT ANALYTICS  (structured data for graphs)
    # ─────────────────────────────────────────────

    def generate_report_analytics(self, interview_log: list,
                                   target_role: str,
                                   resume_text: str = None,
                                   job_description: str = None,
                                   language: str = 'en') -> dict:
        """
        Generates structured analytics data used to draw the 6 report graphs.

        Returns a dict with:
          skills_from_resume   : list[str]
          skills_from_jd       : list[str]
          skills_matched        : list[str]
          skills_missing        : list[str]
          projects_detected     : list[str]
          experience_summary    : str
          skill_match           : list[{skill, candidate_score, jd_requirement}]
          jd_match              : {required_skills_pct, preferred_skills_pct,
                                   experience_pct, overall_fit_pct}
          answer_quality        : list[{q_index, clarity, technical_depth,
                                        relevance, confidence}]
        """
        context_block = self._build_context_block(resume_text, job_description)

        lean_log = [
            {
                'q_index': r.get('question_index'),
                'q_type':  r.get('question_type'),
                'question': r.get('question', '')[:200],
                'answer':   (r.get('transcript') or '')[:300],
                'score':    r.get('ai_score', 0),
                'feedback': (r.get('ai_feedback') or '')[:150],
            }
            for r in interview_log
        ]

        has_resume = bool(resume_text and resume_text.strip())
        has_jd     = bool(job_description and job_description.strip())

        prompt = f"""You are a senior technical recruiter analysing an interview for a {target_role} role.

{context_block}INTERVIEW LOG:
{json.dumps(lean_log, indent=2)}

Generate a structured JSON analytics object. Follow these rules:
- JSON keys must be EXACTLY as listed below.
- All text values in English regardless of interview language.
- Be realistic — derive scores from the actual interview answers provided.

Return ONLY valid JSON (no markdown, no code fences):
{{
  "skills_from_resume": ["skill1", "skill2"],
  "skills_from_jd": ["skill1", "skill2"],
  "skills_matched": ["skill1", "skill2"],
  "skills_missing": ["skill1", "skill2"],
  "projects_detected": ["project name or description"],
  "experience_summary": "2-3 sentence summary of candidate's demonstrated experience",
  "skill_match": [
    {{"skill": "Python", "candidate_score": 7, "jd_requirement": 9}},
    {{"skill": "System Design", "candidate_score": 5, "jd_requirement": 8}},
    {{"skill": "Communication", "candidate_score": 7, "jd_requirement": 7}},
    {{"skill": "Problem Solving", "candidate_score": 6, "jd_requirement": 8}},
    {{"skill": "Domain Knowledge", "candidate_score": 6, "jd_requirement": 7}}
  ],
  "jd_match": {{
    "required_skills_pct": 70,
    "preferred_skills_pct": 55,
    "experience_pct": 65,
    "overall_fit_pct": 63
  }},
  "answer_quality": [
    {{"q_index": 1, "clarity": 7, "technical_depth": 5, "relevance": 8, "confidence": 7}}
  ]
}}

Rules:
- skill_match: include 5–8 skills relevant to the {target_role} role.
  candidate_score = how well the candidate demonstrated this skill (1–10, from their answers).
  jd_requirement  = how important this skill is for the role (1–10).
  {"If no JD provided, infer reasonable requirements for a " + target_role + " role." if not has_jd else ""}
  {"If no resume, infer candidate_score from interview answers only." if not has_resume else ""}
- jd_match percentages: realistic estimates based on available evidence.
  {"Set all to 0 and note no JD was provided if job_description is absent." if not has_jd else ""}
- answer_quality: one entry per question in the interview log.
  Score each dimension 1–10 based on the actual answer content.
- skills_from_resume: extract from resume text if provided, else empty array.
- skills_from_jd: extract from JD if provided, else empty array.
- projects_detected: notable projects/products mentioned in resume or answers.
- Output ONLY the JSON. No explanatory text."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            # Ensure required keys exist with safe defaults
            defaults = {
                'skills_from_resume': [], 'skills_from_jd': [],
                'skills_matched': [], 'skills_missing': [],
                'projects_detected': [], 'experience_summary': '',
                'skill_match': [], 'jd_match': {
                    'required_skills_pct': 0, 'preferred_skills_pct': 0,
                    'experience_pct': 0, 'overall_fit_pct': 0
                },
                'answer_quality': [],
            }
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data

        except Exception as e:
            print(f"❌ Analytics generation error: {e}")
            # Return safe fallback from raw scores
            aq = [{'q_index': r.get('question_index', i+1),
                   'clarity': r.get('ai_score', 5),
                   'technical_depth': max((r.get('ai_score', 5) - 1), 1),
                   'relevance': r.get('ai_score', 5),
                   'confidence': max((r.get('ai_score', 5) - 1), 1)}
                  for i, r in enumerate(interview_log)]
            avg = sum(r.get('ai_score', 5) for r in interview_log) / max(len(interview_log), 1)
            pct = int((avg / 10) * 100)
            return {
                'skills_from_resume': [], 'skills_from_jd': [],
                'skills_matched': [], 'skills_missing': [],
                'projects_detected': [], 'experience_summary': '',
                'skill_match': [
                    {'skill': 'Technical Knowledge', 'candidate_score': int(avg), 'jd_requirement': 8},
                    {'skill': 'Communication',        'candidate_score': int(avg), 'jd_requirement': 7},
                    {'skill': 'Problem Solving',      'candidate_score': int(avg), 'jd_requirement': 8},
                ],
                'jd_match': {
                    'required_skills_pct': pct, 'preferred_skills_pct': max(pct-10, 0),
                    'experience_pct': pct, 'overall_fit_pct': pct,
                },
                'answer_quality': aq,
            }