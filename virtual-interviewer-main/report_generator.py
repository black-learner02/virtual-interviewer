"""
report_generator.py
────────────────────
Generates 6 analytics graphs + a full PDF Candidate Evaluation Report.

Required:
    pip install matplotlib reportlab pillow numpy
"""

import io
import json
import textwrap
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, HRFlowable, PageBreak, KeepTogether,
)

# ─────────────────────────────────────────────
# DESIGN TOKENS  (match the app's dark palette)
# ─────────────────────────────────────────────
C_BG       = '#0a0a0f'
C_SURFACE  = '#111118'
C_SURFACE2 = '#18181f'
C_BORDER   = '#1e1e28'
C_TEXT     = '#e8e8f0'
C_MUTED    = '#9090a8'
C_DIM      = '#4a4a5a'
C_PURPLE   = '#7c6af7'
C_GREEN    = '#22d4a3'
C_ORANGE   = '#f5a623'
C_RED      = '#f26060'
C_BLUE     = '#60a5fa'

# ─────────────────────────────────────────────
# TYPE SAFETY HELPER
# ReportLab Paragraph() requires a plain str.
# The LLM occasionally returns lists or dicts
# for fields that should be strings. This helper
# normalises any value before it touches ReportLab.
# ─────────────────────────────────────────────

def _to_str(val, sep: str = '\n') -> str:
    """
    Safely coerce any LLM-returned value to a plain string.
    - str  → returned as-is (stripped)
    - list → each item converted and joined with `sep`
    - dict → "key: value" lines joined with newline
    - None / falsy → empty string
    """
    if val is None:
        return ''
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        parts = []
        for item in val:
            if isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, dict):
                parts.append(', '.join(f'{k}: {v}' for k, v in item.items()))
            else:
                parts.append(str(item))
        return sep.join(p for p in parts if p)
    if isinstance(val, dict):
        return '\n'.join(f'{k.replace("_"," ").capitalize()}: {v}'
                         for k, v in val.items() if v)
    return str(val).strip()


EMOTION_SCORE = {
    'confident': 0.88, 'happy': 0.80, 'neutral': 0.60,
    'surprised': 0.52, 'confused': 0.40, 'nervous': 0.35,
    'fearful':   0.28, 'sad':     0.22, 'angry':   0.18, 'disgust': 0.15,
}
EMOTION_COLOR = {
    'confident': C_GREEN,   'happy': C_GREEN,  'neutral': C_MUTED,
    'surprised': C_BLUE,    'confused': C_ORANGE, 'nervous': C_ORANGE,
    'fearful': C_RED,       'sad': C_RED,      'angry': C_RED, 'disgust': C_RED,
}


def _mpl_dark():
    """Apply dark theme to all subsequent matplotlib figures."""
    plt.rcParams.update({
        'figure.facecolor':  C_BG,
        'axes.facecolor':    C_SURFACE,
        'axes.edgecolor':    C_BORDER,
        'axes.labelcolor':   C_MUTED,
        'axes.titlecolor':   C_TEXT,
        'xtick.color':       C_MUTED,
        'ytick.color':       C_MUTED,
        'grid.color':        C_BORDER,
        'grid.linewidth':    0.8,
        'text.color':        C_TEXT,
        'font.family':       'monospace',
        'font.size':         9,
        'axes.titlesize':    11,
        'axes.titlepad':     12,
        'figure.autolayout': True,
    })


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ═════════════════════════════════════════════
# GRAPH 1 — Skill Match Radar Chart
# ═════════════════════════════════════════════

def graph_skill_radar(analytics: dict) -> bytes:
    _mpl_dark()
    skill_match = analytics.get('skill_match', [])

    if not skill_match:
        # Fallback: generic radar
        skill_match = [
            {'skill': 'Technical Knowledge', 'candidate_score': 7, 'jd_requirement': 8},
            {'skill': 'Communication',        'candidate_score': 6, 'jd_requirement': 7},
            {'skill': 'Problem Solving',      'candidate_score': 7, 'jd_requirement': 8},
            {'skill': 'System Design',        'candidate_score': 5, 'jd_requirement': 7},
            {'skill': 'Code Quality',         'candidate_score': 6, 'jd_requirement': 8},
        ]

    # Limit to 8 skills for readability
    skill_match = skill_match[:8]
    labels      = [s['skill'] for s in skill_match]
    candidate   = [min(s.get('candidate_score', 5), 10) for s in skill_match]
    required    = [min(s.get('jd_requirement', 8),  10) for s in skill_match]

    N      = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    candidate_vals = candidate + [candidate[0]]
    required_vals  = required  + [required[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_SURFACE)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=8.5, color=C_TEXT)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(['2', '4', '6', '8', '10'], color=C_DIM, fontsize=7)
    ax.grid(color=C_BORDER, linewidth=0.8)
    ax.spines['polar'].set_color(C_BORDER)

    # JD requirement (background)
    ax.fill(angles, required_vals, color=C_PURPLE, alpha=0.12)
    ax.plot(angles, required_vals, color=C_PURPLE, linewidth=1.5, linestyle='--', label='JD Requirement')

    # Candidate scores
    ax.fill(angles, candidate_vals, color=C_GREEN, alpha=0.22)
    ax.plot(angles, candidate_vals, color=C_GREEN, linewidth=2.0, label='Candidate Score')

    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1),
              facecolor=C_SURFACE2, edgecolor=C_BORDER,
              labelcolor=C_TEXT, fontsize=8.5)
    ax.set_title('Skill Match Radar', color=C_TEXT, pad=20)

    return _fig_to_bytes(fig)


# ═════════════════════════════════════════════
# GRAPH 2 — Resume vs JD Match Bar Chart
# ═════════════════════════════════════════════

def graph_jd_match_bar(analytics: dict) -> bytes:
    _mpl_dark()
    jd_match = analytics.get('jd_match', {})

    categories = ['Required Skills Match', 'Preferred Skills Match', 'Experience Match']
    values = [
        jd_match.get('required_skills_pct',  70),
        jd_match.get('preferred_skills_pct', 55),
        jd_match.get('experience_pct',       65),
    ]
    bar_colors = [C_GREEN if v >= 70 else C_ORANGE if v >= 50 else C_RED for v in values]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_SURFACE)

    bars = ax.barh(categories, values, color=bar_colors, height=0.45,
                   edgecolor=C_BORDER, linewidth=0.5)

    # Value labels
    for bar, val in zip(bars, values):
        ax.text(min(val + 2, 97), bar.get_y() + bar.get_height() / 2,
                f'{val}%', va='center', color=C_TEXT, fontsize=9, fontweight='bold')

    ax.set_xlim(0, 100)
    ax.set_xlabel('Match Percentage (%)')
    ax.set_title('Resume vs Job Description Match')
    ax.axvline(70, color=C_PURPLE, linewidth=1, linestyle='--', alpha=0.6, label='Good match (70%)')
    ax.legend(facecolor=C_SURFACE2, edgecolor=C_BORDER, labelcolor=C_TEXT, fontsize=8)
    ax.grid(axis='x', alpha=0.4)
    ax.tick_params(axis='y', labelsize=9, labelcolor=C_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_BORDER)

    return _fig_to_bytes(fig)


# ═════════════════════════════════════════════
# GRAPH 3 — Emotion Timeline Line Chart
# ═════════════════════════════════════════════

def graph_emotion_timeline(responses: list) -> bytes:
    _mpl_dark()

    q_labels  = []
    em_scores = []
    em_names  = []

    for r in responses:
        vm = r.get('video_metrics', {})
        if isinstance(vm, str):
            try: vm = json.loads(vm)
            except: vm = {}
        emotion = (vm.get('dominant_emotion') or 'neutral').lower()
        score   = EMOTION_SCORE.get(emotion, 0.55)
        q_labels.append(f'Q{r.get("question_index", "?")}')
        em_scores.append(score * 100)
        em_names.append(emotion)

    if not q_labels:
        q_labels  = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
        em_scores = [60, 65, 58, 70, 72]
        em_names  = ['neutral'] * 5

    x = range(len(q_labels))

    fig, ax = plt.subplots(figsize=(8, 3.8))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_SURFACE)

    # Gradient shading under curve
    ax.fill_between(x, em_scores, alpha=0.15, color=C_PURPLE)
    ax.plot(x, em_scores, color=C_PURPLE, linewidth=2.5, zorder=3)

    # Coloured scatter points by emotion
    for i, (score, name) in enumerate(zip(em_scores, em_names)):
        c = EMOTION_COLOR.get(name, C_MUTED)
        ax.scatter(i, score, color=c, s=60, zorder=4, edgecolors=C_SURFACE2, linewidths=1)
        ax.annotate(name, (i, score), textcoords='offset points',
                    xytext=(0, 8), ha='center', fontsize=7.5, color=c, alpha=0.85)

    ax.set_xticks(list(x))
    ax.set_xticklabels(q_labels)
    ax.set_ylim(0, 105)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(['0', 'Nervous', 'Neutral', 'Calm', 'Confident'], fontsize=8)
    ax.set_xlabel('Interview Timeline')
    ax.set_ylabel('Emotional State')
    ax.set_title('Emotion Timeline Across Interview')
    ax.grid(axis='y', alpha=0.35)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_BORDER)

    return _fig_to_bytes(fig)


# ═════════════════════════════════════════════
# GRAPH 4 — Answer Quality Score Bar Chart
# ═════════════════════════════════════════════

def graph_answer_quality(analytics: dict, responses: list) -> bytes:
    _mpl_dark()
    aq = analytics.get('answer_quality', [])

    # Compute averages across all questions
    if aq:
        clarity    = sum(a.get('clarity', 5)         for a in aq) / len(aq)
        tech_depth = sum(a.get('technical_depth', 5) for a in aq) / len(aq)
        relevance  = sum(a.get('relevance', 5)       for a in aq) / len(aq)
        confidence = sum(a.get('confidence', 5)      for a in aq) / len(aq)
    else:
        # Derive from existing response data
        scores     = [r.get('ai_score', 5) for r in responses]
        avg        = sum(scores) / max(len(scores), 1)
        clarity    = avg
        tech_depth = avg * 0.95
        relevance  = avg * 1.02
        confidence = avg * 0.90

    metrics = ['Clarity', 'Technical Depth', 'Relevance', 'Confidence']
    values  = [round(clarity, 1), round(tech_depth, 1),
               round(relevance, 1), round(confidence, 1)]
    bar_cols = [C_GREEN if v >= 7 else C_ORANGE if v >= 5 else C_RED for v in values]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_SURFACE)

    x    = np.arange(len(metrics))
    bars = ax.bar(x, values, color=bar_cols, width=0.5,
                  edgecolor=C_BORDER, linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.15,
                f'{val:.1f}', ha='center', va='bottom',
                color=C_TEXT, fontsize=9, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9.5)
    ax.set_ylim(0, 11)
    ax.set_ylabel('Score (0–10)')
    ax.set_title('Answer Quality Breakdown')
    ax.axhline(7, color=C_GREEN, linewidth=0.8, linestyle='--', alpha=0.5)
    ax.axhline(5, color=C_ORANGE, linewidth=0.8, linestyle='--', alpha=0.5)
    ax.grid(axis='y', alpha=0.35)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_BORDER)

    return _fig_to_bytes(fig)


# ═════════════════════════════════════════════
# GRAPH 5 — Emotion Distribution Pie Chart
# ═════════════════════════════════════════════

def graph_emotion_distribution(responses: list) -> bytes:
    _mpl_dark()
    counts: dict[str, int] = {}

    for r in responses:
        vm = r.get('video_metrics', {})
        if isinstance(vm, str):
            try: vm = json.loads(vm)
            except: vm = {}
        emotion = (vm.get('dominant_emotion') or 'neutral').lower()
        counts[emotion] = counts.get(emotion, 0) + 1

    if not counts:
        counts = {'neutral': 3, 'confident': 1, 'nervous': 1}

    labels = list(counts.keys())
    sizes  = list(counts.values())
    pie_colors = [EMOTION_COLOR.get(lbl, C_MUTED) for lbl in labels]

    fig, ax = plt.subplots(figsize=(5.5, 5))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        colors=pie_colors,
        autopct='%1.0f%%',
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(linewidth=1.5, edgecolor=C_BG),
    )
    for at in autotexts:
        at.set_color(C_BG)
        at.set_fontsize(9)
        at.set_fontweight('bold')

    ax.legend(wedges, [lbl.capitalize() for lbl in labels],
              loc='lower center', ncol=3, bbox_to_anchor=(0.5, -0.12),
              facecolor=C_SURFACE2, edgecolor=C_BORDER,
              labelcolor=C_TEXT, fontsize=8.5)
    ax.set_title('Emotion Distribution', pad=14)

    return _fig_to_bytes(fig)


# ═════════════════════════════════════════════
# GRAPH 6 — Interview Confidence Progress
# ═════════════════════════════════════════════

def graph_confidence_progress(responses: list) -> bytes:
    _mpl_dark()

    if not responses:
        responses = [{'question_index': i, 'ai_score': 5} for i in range(1, 6)]

    q_indices = [r.get('question_index', i+1) for i, r in enumerate(responses)]
    scores    = [r.get('ai_score', 5) or 5 for r in responses]

    # Running average scaled to 0-100%
    running_confidence = []
    for i in range(len(scores)):
        avg = sum(scores[:i+1]) / (i + 1)
        pct = (avg / 10) * 100
        # Add interviewer knowledge bonus (more data → higher confidence in assessment)
        coverage_bonus = min(i * 2, 10)
        running_confidence.append(min(pct + coverage_bonus, 100))

    fig, ax = plt.subplots(figsize=(8, 3.8))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_SURFACE)

    ax.fill_between(range(len(q_indices)), running_confidence, alpha=0.18, color=C_GREEN)
    ax.plot(range(len(q_indices)), running_confidence,
            color=C_GREEN, linewidth=2.5, marker='o', markersize=6,
            markerfacecolor=C_GREEN, markeredgecolor=C_SURFACE2, zorder=4)

    # Annotate each point
    for i, (conf, score) in enumerate(zip(running_confidence, scores)):
        ax.annotate(f'{conf:.0f}%', (i, conf),
                    textcoords='offset points', xytext=(0, 8),
                    ha='center', fontsize=8, color=C_GREEN)

    ax.set_xticks(range(len(q_indices)))
    ax.set_xticklabels([f'Q{qi}' for qi in q_indices])
    ax.set_ylim(0, 110)
    ax.set_ylabel('Confidence Level (%)')
    ax.set_xlabel('Interview Progress')
    ax.set_title('Assessment Confidence Progress')

    # Threshold lines
    ax.axhline(75, color=C_GREEN,  linewidth=0.8, linestyle='--', alpha=0.45, label='Strong Fit (75%)')
    ax.axhline(50, color=C_ORANGE, linewidth=0.8, linestyle='--', alpha=0.45, label='Moderate Fit (50%)')
    ax.legend(facecolor=C_SURFACE2, edgecolor=C_BORDER, labelcolor=C_TEXT, fontsize=8)
    ax.grid(axis='y', alpha=0.35)
    for spine in ax.spines.values():
        spine.set_edgecolor(C_BORDER)

    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────
# MASTER GRAPH BUILDER
# ─────────────────────────────────────────────

def build_graphs(responses: list, analytics: dict) -> dict:
    """Generates all 6 charts. Returns {key: png_bytes}."""
    results = {}
    jobs = [
        ('skill_radar',          lambda: graph_skill_radar(analytics)),
        ('jd_match_bar',         lambda: graph_jd_match_bar(analytics)),
        ('emotion_timeline',     lambda: graph_emotion_timeline(responses)),
        ('answer_quality',       lambda: graph_answer_quality(analytics, responses)),
        ('emotion_distribution', lambda: graph_emotion_distribution(responses)),
        ('confidence_progress',  lambda: graph_confidence_progress(responses)),
    ]
    for key, fn in jobs:
        try:
            results[key] = fn()
        except Exception as e:
            print(f'⚠ Graph [{key}] failed: {e}')
    return results


# ─────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────

# ReportLab colour helpers
RL_BG      = colors.HexColor('#0d0d14')
RL_SURFACE = colors.HexColor('#14141e')
RL_PURPLE  = colors.HexColor('#7c6af7')
RL_GREEN   = colors.HexColor('#22d4a3')
RL_ORANGE  = colors.HexColor('#f5a623')
RL_RED     = colors.HexColor('#f26060')
RL_TEXT    = colors.HexColor('#e8e8f0')
RL_MUTED   = colors.HexColor('#9090a8')
RL_DIM     = colors.HexColor('#4a4a5a')
RL_WHITE   = colors.white


def _styles() -> dict:
    s = {}

    s['Title'] = ParagraphStyle('Title',
        fontName='Helvetica-Bold', fontSize=28,
        textColor=RL_TEXT, leading=34, alignment=TA_LEFT, spaceAfter=6)

    s['Subtitle'] = ParagraphStyle('Subtitle',
        fontName='Helvetica', fontSize=14,
        textColor=RL_MUTED, leading=18, alignment=TA_LEFT, spaceAfter=4)

    s['SectionHeading'] = ParagraphStyle('SectionHeading',
        fontName='Helvetica-Bold', fontSize=11,
        textColor=RL_PURPLE, leading=16, spaceBefore=18, spaceAfter=10,
        borderPad=0)

    s['Body'] = ParagraphStyle('Body',
        fontName='Helvetica', fontSize=9.5,
        textColor=RL_TEXT, leading=15, spaceAfter=6,
        alignment=TA_JUSTIFY)

    s['BodyMuted'] = ParagraphStyle('BodyMuted',
        fontName='Helvetica', fontSize=9,
        textColor=RL_MUTED, leading=14, spaceAfter=4)

    s['BulletItem'] = ParagraphStyle('BulletItem',
        fontName='Helvetica', fontSize=9,
        textColor=RL_TEXT, leading=14, spaceAfter=3,
        leftIndent=12, bulletIndent=0)

    s['Label'] = ParagraphStyle('Label',
        fontName='Helvetica-Bold', fontSize=8,
        textColor=RL_MUTED, leading=12, spaceAfter=2,
        wordWrap='CJK')

    s['Mono'] = ParagraphStyle('Mono',
        fontName='Courier', fontSize=8.5,
        textColor=RL_MUTED, leading=13, spaceAfter=4)

    s['CenteredBold'] = ParagraphStyle('CenteredBold',
        fontName='Helvetica-Bold', fontSize=10,
        textColor=RL_TEXT, leading=14, alignment=TA_CENTER)

    s['GraphCaption'] = ParagraphStyle('GraphCaption',
        fontName='Helvetica', fontSize=8,
        textColor=RL_DIM, leading=11, alignment=TA_CENTER, spaceAfter=8)

    return s


def _hr(story, color=RL_DIM, thickness=0.5):
    story.append(HRFlowable(width='100%', thickness=thickness,
                             color=color, spaceAfter=10, spaceBefore=4))


def _section_heading(story, styles, text: str):
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(text.upper(), styles['SectionHeading']))
    _hr(story, color=RL_PURPLE, thickness=0.8)


def _kv_table(data: list[tuple], col_widths=(5*cm, 11*cm)) -> Table:
    """Two-column key/value table."""
    table_data = [[Paragraph(k, ParagraphStyle('k', fontName='Helvetica-Bold',
                                                fontSize=8.5, textColor=RL_MUTED)),
                   Paragraph(str(v), ParagraphStyle('v', fontName='Helvetica',
                                                     fontSize=9, textColor=RL_TEXT))]
                  for k, v in data]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [RL_SURFACE, RL_BG]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, RL_DIM),
    ]))
    return t


def _embed_png(png_bytes: bytes, max_width_cm: float = 16) -> Optional[RLImage]:
    """Wraps PNG bytes in a ReportLab Image object."""
    if not png_bytes:
        return None
    try:
        from PIL import Image as PILImage
        pil = PILImage.open(io.BytesIO(png_bytes))
        w_px, h_px = pil.size
        aspect     = h_px / w_px
        w_pt       = max_width_cm * cm
        h_pt       = w_pt * aspect
        return RLImage(io.BytesIO(png_bytes), width=w_pt, height=h_pt)
    except Exception as e:
        print(f'⚠ Image embed error: {e}')
        return None


def _recommendation_color(rec: str):
    r = rec.lower()
    if 'strong' in r or 'ready' in r or 'hire' in r:
        return RL_GREEN, '✅  STRONG FIT'
    elif 'moderate' in r or 'getting' in r or 'practis' in r:
        return RL_ORANGE, '📈  MODERATE FIT'
    else:
        return RL_RED, '📌  WEAK FIT — MORE PRACTICE NEEDED'


# ── Page header / footer callback ──

_session_meta: dict = {}   # populated before build

def _page_header_footer(canvas, doc):
    canvas.saveState()
    W, H = A4
    # Top stripe
    canvas.setFillColor(RL_SURFACE)
    canvas.rect(0, H - 1.1*cm, W, 1.1*cm, fill=1, stroke=0)
    canvas.setFont('Helvetica-Bold', 7)
    canvas.setFillColor(RL_PURPLE)
    canvas.drawString(2*cm, H - 0.7*cm, 'PREPSPARK  ·  AI CANDIDATE EVALUATION REPORT')
    name = _session_meta.get('candidate', '')
    if name:
        canvas.setFillColor(RL_MUTED)
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(W - 2*cm, H - 0.7*cm, name)
    # Bottom stripe
    canvas.setFillColor(RL_SURFACE)
    canvas.rect(0, 0, W, 0.9*cm, fill=1, stroke=0)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(RL_DIM)
    canvas.drawString(2*cm, 0.35*cm, f'Generated {datetime.now().strftime("%d %b %Y, %H:%M")}')
    canvas.drawRightString(W - 2*cm, 0.35*cm, f'Page {doc.page}')
    canvas.restoreState()


# ── Section builders ──

def _add_title_page(story, styles, session_info: dict, report: dict, analytics: dict):
    story.append(Spacer(1, 2.5*cm))

    # Eyebrow label
    story.append(Paragraph(
        'AI CANDIDATE EVALUATION REPORT',
        ParagraphStyle('eye', fontName='Helvetica-Bold', fontSize=9,
                       textColor=RL_PURPLE, letterSpacing=2, leading=14, spaceAfter=10)
    ))

    story.append(Paragraph(session_info.get('candidate_name', 'Candidate'), styles['Title']))
    story.append(Paragraph(f"Applying for: {session_info.get('target_role', 'Unknown Role')}", styles['Subtitle']))

    if session_info.get('company_name'):
        story.append(Paragraph(session_info['company_name'], styles['Subtitle']))

    story.append(Spacer(1, 1.5*cm))
    _hr(story, color=RL_PURPLE, thickness=1.5)
    story.append(Spacer(1, 8*mm))

    # Meta row
    date_str = ''
    if session_info.get('start_time'):
        try:
            date_str = datetime.fromisoformat(session_info['start_time']).strftime('%d %B %Y')
        except Exception:
            date_str = session_info['start_time']

    meta_rows = [
        [Paragraph('Interview Date', styles['Label']),
         Paragraph(date_str or '—', styles['BodyMuted'])],
        [Paragraph('Session ID', styles['Label']),
         Paragraph(f"#{session_info.get('session_id', '—')}", styles['BodyMuted'])],
        [Paragraph('Total Questions', styles['Label']),
         Paragraph(str(session_info.get('total_questions', len(session_info.get('responses', [])))), styles['BodyMuted'])],
        [Paragraph('Language', styles['Label']),
         Paragraph(session_info.get('language', 'en').upper(), styles['BodyMuted'])],
    ]
    meta_t = Table(meta_rows, colWidths=[4.5*cm, 11*cm])
    meta_t.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (0, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, RL_DIM),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 2*cm))

    # Verdict box
    rec = _to_str(report.get('recommendation') or 'More Practice Recommended')
    rec_color, rec_label = _recommendation_color(rec)

    verdict_table = Table(
        [[Paragraph(rec_label, ParagraphStyle('vl',
            fontName='Helvetica-Bold', fontSize=13,
            textColor=rec_color, leading=16)),
          Paragraph(rec, ParagraphStyle('vr',
            fontName='Helvetica', fontSize=9,
            textColor=RL_MUTED, leading=13, alignment=TA_RIGHT))]],
        colWidths=[9*cm, 7*cm]
    )
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), RL_SURFACE),
        ('BOX',        (0, 0), (-1, -1), 1.5, rec_color),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING',   (0, 0), (-1, -1), 16),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 16),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(verdict_table)

    story.append(Spacer(1, 2*cm))

    # Executive summary
    exec_sum = _to_str(report.get('executive_summary', ''))
    if exec_sum:
        story.append(Paragraph('Executive Summary', styles['SectionHeading']))
        story.append(Paragraph(exec_sum, styles['Body']))


def _add_candidate_overview(story, styles, session_info: dict, analytics: dict):
    _section_heading(story, styles, '1. Candidate Overview')

    date_str = ''
    if session_info.get('start_time'):
        try:
            date_str = datetime.fromisoformat(session_info['start_time']).strftime('%d %B %Y, %H:%M')
        except Exception:
            date_str = session_info['start_time']

    data = [
        ('Candidate Name',    session_info.get('candidate_name', '—')),
        ('Role Applied For',  session_info.get('target_role', '—')),
        ('Company',           session_info.get('company_name', '—')),
        ('Interview Date',    date_str or '—'),
        ('Total Questions',   str(session_info.get('total_questions', '—'))),
        ('Session ID',        f"#{session_info.get('session_id', '—')}"),
    ]
    story.append(_kv_table(data))


def _add_resume_summary(story, styles, analytics: dict, report: dict):
    _section_heading(story, styles, '2. Resume Summary')

    skills = analytics.get('skills_from_resume', [])
    if skills:
        story.append(Paragraph('Key Skills Extracted', styles['Label']))
        chips = '  ·  '.join(skills[:16])
        story.append(Paragraph(chips, styles['BodyMuted']))
        story.append(Spacer(1, 6))

    projects = analytics.get('projects_detected', [])
    if projects:
        story.append(Paragraph('Projects Detected', styles['Label']))
        for p in projects[:5]:
            story.append(Paragraph(f'• {p}', styles['BulletItem']))
        story.append(Spacer(1, 6))

    exp_summary = _to_str(analytics.get('experience_summary', '')) or _to_str(report.get('technical_depth', ''))
    if exp_summary:
        story.append(Paragraph('Experience Summary', styles['Label']))
        story.append(Paragraph(exp_summary[:500], styles['Body']))

    if not (skills or projects or exp_summary):
        story.append(Paragraph('No resume was provided for this session.', styles['BodyMuted']))


def _add_jd_match(story, styles, analytics: dict, report: dict):
    _section_heading(story, styles, '3. Job Description Match')

    jd_match = analytics.get('jd_match', {})

    # Score table
    score_data = [
        ('Required Skills Match',  f"{jd_match.get('required_skills_pct',  '—')}%"),
        ('Preferred Skills Match', f"{jd_match.get('preferred_skills_pct', '—')}%"),
        ('Experience Match',       f"{jd_match.get('experience_pct',       '—')}%"),
        ('Overall Fit Score',      f"{jd_match.get('overall_fit_pct',      '—')}%"),
    ]
    story.append(_kv_table(score_data, col_widths=(6*cm, 10*cm)))
    story.append(Spacer(1, 6))

    matched = analytics.get('skills_matched', [])
    if matched:
        story.append(Paragraph('Matched Skills', styles['Label']))
        story.append(Paragraph('  ·  '.join(matched[:12]), styles['BodyMuted']))
        story.append(Spacer(1, 4))

    missing = analytics.get('skills_missing', [])
    if missing:
        story.append(Paragraph('Missing / Undemonstrated Skills', styles['Label']))
        story.append(Paragraph('  ·  '.join(missing[:10]), ParagraphStyle('miss',
            fontName='Helvetica', fontSize=9, textColor=RL_RED, leading=14)))
        story.append(Spacer(1, 4))

    jd_analysis = _to_str(report.get('jd_fit_analysis', ''))
    if jd_analysis:
        story.append(Paragraph('Analysis', styles['Label']))
        story.append(Paragraph(jd_analysis[:600], styles['Body']))

    if not (matched or missing or jd_analysis):
        story.append(Paragraph('No job description was provided for this session.', styles['BodyMuted']))


def _add_interview_performance(story, styles, responses: list, analytics: dict):
    _section_heading(story, styles, '4. Interview Performance')

    if not responses:
        story.append(Paragraph('No responses recorded.', styles['BodyMuted']))
        return

    # Per-question scores table
    header_style = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8,
                                  textColor=RL_TEXT, leading=11)
    cell_style   = ParagraphStyle('td', fontName='Helvetica', fontSize=8,
                                  textColor=RL_MUTED, leading=12)

    table_data = [[
        Paragraph('#', header_style),
        Paragraph('Type', header_style),
        Paragraph('Question', header_style),
        Paragraph('Score', header_style),
    ]]

    aq_by_q = {a.get('q_index', i+1): a for i, a in enumerate(analytics.get('answer_quality', []))}

    for r in responses:
        qi    = r.get('question_index', '?')
        qtype = (r.get('question_type') or 'technical').capitalize()
        qtxt  = (r.get('question') or '')[:80] + ('…' if len(r.get('question','')) > 80 else '')
        score = r.get('ai_score', 0)

        score_color = RL_GREEN if score >= 7 else RL_ORANGE if score >= 5 else RL_RED
        score_p     = Paragraph(f'{score}/10',
                                ParagraphStyle('sc', fontName='Helvetica-Bold', fontSize=9,
                                               textColor=score_color))
        table_data.append([
            Paragraph(str(qi), cell_style),
            Paragraph(qtype, cell_style),
            Paragraph(qtxt, cell_style),
            score_p,
        ])

    t = Table(table_data, colWidths=[1*cm, 2.5*cm, 11*cm, 2*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), RL_SURFACE),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [RL_BG, RL_SURFACE]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, RL_PURPLE),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, RL_DIM),
        ('VALIGN',    (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)

    # Strengths / areas for improvement
    story.append(Spacer(1, 8))
    strengths = report_data_holder.get('strengths', []) if report_data_holder else []
    areas     = report_data_holder.get('areas_for_improvement', []) if report_data_holder else []

    # Normalise: LLM may return a plain string instead of a list
    if isinstance(strengths, str): strengths = [s.strip() for s in strengths.split('\n') if s.strip()]
    if isinstance(areas, str):     areas     = [a.strip() for a in areas.split('\n')     if a.strip()]

    if strengths or areas:
        col1 = []
        if strengths:
            col1.append(Paragraph('Strengths', ParagraphStyle('sh', fontName='Helvetica-Bold',
                                   fontSize=9, textColor=RL_GREEN, spaceAfter=4)))
            for s in strengths:
                col1.append(Paragraph(f'✓  {_to_str(s)}', ParagraphStyle('si', fontName='Helvetica',
                                       fontSize=8.5, textColor=RL_TEXT, leading=13, leftIndent=4)))

        col2 = []
        if areas:
            col2.append(Paragraph('Areas to Improve', ParagraphStyle('ah', fontName='Helvetica-Bold',
                                   fontSize=9, textColor=RL_ORANGE, spaceAfter=4)))
            for a in areas:
                col2.append(Paragraph(f'→  {_to_str(a)}', ParagraphStyle('ai', fontName='Helvetica',
                                       fontSize=8.5, textColor=RL_TEXT, leading=13, leftIndent=4)))

        sa_table = Table([[col1, col2]], colWidths=[8*cm, 8*cm])
        sa_table.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ]))
        story.append(sa_table)


# Global holder so _add_interview_performance can access report
report_data_holder = None


def _add_emotion_analysis(story, styles, responses: list, report: dict):
    _section_heading(story, styles, '5. Emotion & Behavioural Analysis')

    # Per-question emotion + audio table
    header_style = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8,
                                  textColor=RL_TEXT, leading=11)
    cell_style   = ParagraphStyle('td', fontName='Helvetica', fontSize=8,
                                  textColor=RL_MUTED, leading=12)

    table_data = [[
        Paragraph('#', header_style),
        Paragraph('Dominant Emotion', header_style),
        Paragraph('Eye Contact', header_style),
        Paragraph('WPM', header_style),
        Paragraph('Jitter', header_style),
    ]]

    for r in responses:
        vm = r.get('video_metrics', {})
        am = r.get('audio_metrics', {})
        if isinstance(vm, str):
            try: vm = json.loads(vm)
            except: vm = {}
        if isinstance(am, str):
            try: am = json.loads(am)
            except: am = {}

        emotion    = (vm.get('dominant_emotion') or 'neutral').capitalize()
        eye_pct    = vm.get('eye_contact_percent', '—')
        wpm        = am.get('wpm', '—')
        jitter     = am.get('jitter_percent', '—')
        em_color   = EMOTION_COLOR.get(emotion.lower(), C_MUTED)

        em_p = Paragraph(emotion, ParagraphStyle('em', fontName='Helvetica-Bold',
                                                  fontSize=8, textColor=colors.HexColor(em_color)))
        table_data.append([
            Paragraph(str(r.get('question_index', '?')), cell_style),
            em_p,
            Paragraph(f'{eye_pct}%' if eye_pct != '—' else '—', cell_style),
            Paragraph(str(wpm), cell_style),
            Paragraph(f'{jitter}%' if jitter != '—' else '—', cell_style),
        ])

    t = Table(table_data, colWidths=[1*cm, 4.5*cm, 3.5*cm, 3*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), RL_SURFACE),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [RL_BG, RL_SURFACE]),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, RL_PURPLE),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, RL_DIM),
    ]))
    story.append(t)

    beh_signals = _to_str(report.get('behavioural_signals', ''))
    if beh_signals:
        story.append(Spacer(1, 8))
        story.append(Paragraph('Behavioural Analysis', styles['Label']))
        story.append(Paragraph(beh_signals[:600], styles['Body']))

    comm_style = _to_str(report.get('communication_style', ''))
    if comm_style:
        story.append(Spacer(1, 4))
        story.append(Paragraph('Communication Style', styles['Label']))
        story.append(Paragraph(comm_style[:500], styles['Body']))


def _embed_graphs(story, styles, graphs: dict):
    """Lays out the 6 graphs in a 2-column grid."""
    graph_meta = [
        ('skill_radar',          'Skill Match Radar Chart',            8.0),
        ('jd_match_bar',         'Resume vs Job Description Match',    8.5),
        ('emotion_timeline',     'Emotion Timeline',                   9.5),
        ('answer_quality',       'Answer Quality Breakdown',           8.5),
        ('emotion_distribution', 'Emotion Distribution',               7.0),
        ('confidence_progress',  'Interview Confidence Progress',      9.5),
    ]

    caption_style = ParagraphStyle('cap', fontName='Helvetica', fontSize=7.5,
                                   textColor=RL_DIM, leading=10, alignment=TA_CENTER,
                                   spaceBefore=2, spaceAfter=8)

    # Pair graphs into rows of 2
    pairs = [(graph_meta[i], graph_meta[i+1] if i+1 < len(graph_meta) else None)
             for i in range(0, len(graph_meta), 2)]

    for left, right in pairs:
        cells = []
        for meta in (left, right):
            if meta is None:
                cells.append('')
                continue
            key, caption, w_cm = meta
            png = graphs.get(key)
            img = _embed_png(png, max_width_cm=w_cm) if png else None
            if img:
                cells.append([img, Paragraph(caption, caption_style)])
            else:
                cells.append(Paragraph(f'[{caption} unavailable]', caption_style))

        row_table = Table([cells], colWidths=[9*cm, 9*cm])
        row_table.setStyle(TableStyle([
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ]))
        story.append(KeepTogether(row_table))
        story.append(Spacer(1, 6))


def _add_final_recommendation(story, styles, report: dict, analytics: dict):
    _section_heading(story, styles, '7. Final Recommendation')

    rec       = _to_str(report.get('recommendation') or 'More Practice Recommended')
    rec_color, rec_label = _recommendation_color(rec)

    # Large verdict box
    rec_box = Table([[Paragraph(rec_label, ParagraphStyle('rb',
                         fontName='Helvetica-Bold', fontSize=16,
                         textColor=rec_color, leading=20, alignment=TA_CENTER))]],
                    colWidths=[16*cm])
    rec_box.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), RL_SURFACE),
        ('BOX',           (0, 0), (-1, -1), 2, rec_color),
        ('TOPPADDING',    (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(rec_box)
    story.append(Spacer(1, 12))

    coaching = _to_str(report.get('coaching_tips', ''), sep='\n')
    if coaching:
        story.append(Paragraph('Coaching Tips', styles['SectionHeading']))
        # Render as bullet points if multi-line, otherwise as prose
        lines = [l.strip() for l in coaching.split('\n') if l.strip()]
        if len(lines) > 1:
            for line in lines:
                story.append(Paragraph(f'• {line}', styles['BulletItem']))
        else:
            story.append(Paragraph(coaching, styles['Body']))

    rr = _to_str(report.get('resume_vs_reality', ''))
    if rr:
        story.append(Spacer(1, 8))
        story.append(Paragraph('Resume vs Reality', styles['Label']))
        story.append(Paragraph(rr[:600], styles['Body']))

    story.append(Spacer(1, 2*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=RL_DIM))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f'This report was generated automatically by PrepSpark AI. '
        f'It is intended for practice and coaching purposes only.',
        ParagraphStyle('disc', fontName='Helvetica', fontSize=7.5,
                       textColor=RL_DIM, leading=11, alignment=TA_CENTER)
    ))


# ─────────────────────────────────────────────
# MASTER PDF BUILDER
# ─────────────────────────────────────────────

def build_pdf(session_info: dict, analytics: dict,
              report: dict, responses: list,
              graphs: dict) -> bytes:
    """
    Assembles the full A4 PDF.
    session_info must contain: candidate_name, target_role, session_id,
                               start_time, language, total_questions.
    Returns raw PDF bytes.
    """
    global report_data_holder
    report_data_holder = report

    _session_meta['candidate'] = session_info.get('candidate_name', '')

    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.6*cm, bottomMargin=1.4*cm,
    )
    S = _styles()
    story = []

    _add_title_page(story, S, session_info, report, analytics)
    story.append(PageBreak())
    _add_candidate_overview(story, S, session_info, analytics)
    _add_resume_summary(story, S, analytics, report)
    story.append(PageBreak())
    _add_jd_match(story, S, analytics, report)
    story.append(PageBreak())
    _add_interview_performance(story, S, responses, analytics)
    story.append(PageBreak())
    _add_emotion_analysis(story, S, responses, report)
    story.append(PageBreak())

    story.append(Paragraph('6. Visual Analytics', S['SectionHeading']))
    _hr(story, RL_PURPLE, 0.8)
    _embed_graphs(story, S, graphs)

    story.append(PageBreak())
    _add_final_recommendation(story, S, report, analytics)

    doc.build(story,
              onFirstPage=_page_header_footer,
              onLaterPages=_page_header_footer)

    return buf.getvalue()