# Virtual Interviewer

An AI-powered virtual interviewer application that conducts job interviews, analyzes candidate performance using advanced video and audio processing, and provides detailed, actionable feedback using Google's Gemini LLM.

## 🚀 Features

- **Interactive AI Interview**: Conducts dynamic interviews where questions adapt based on the candidate's responses and the target role.
- **Multimodal Analysis**:
  - **Video Analysis**: Uses MediaPipe and OpenCV to track head pose, eye gaze, and facial expressions to evaluate engagement and confidence.
  - **Audio Analysis**: Utilizes OpenAI Whisper for accurate speech-to-text transcription and Librosa for pitch and tone analysis.
- **Intelligent Feedback**: Fuses audio and visual data to generate comprehensive feedback on soft skills, technical content, and communication style.
- **Automated Reports**: Generates detailed performance reports for both candidates and recruiters.

## 🛠️ Tech Stack

- **Framework**: Flask (Python)
- **AI Models & Libraries**:
  - **LLM**: Google Gemini (GenAI)
  - **Computer Vision**: MediaPipe, OpenCV, DeepFace/FER (via ONNX)
  - **Audio Processing**: OpenAI Whisper, Librosa, PyDub
- **Database**: SQLite
- **Tools**: `uv` (Manager), `ffmpeg`

## 📦 Installation

Prerequisites: Python 3.11+

1. **Clone the repository**
   ```bash
   git clone https://github.com/Ramana-Giri/virtual-interviewer.git
   cd virtual-interviewer
   ```

2. **Install Dependencies**
   This project uses `pyproject.toml`. You can install dependencies using `pip` or `uv`.

   ```bash
   # Create and activate virtual environment
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Mac/Linux
   source .venv/bin/activate

   # Install packages
   pip install .
   ```

3. **Configure Environment**
   Create a `.env` file in the root directory and add necessary API keys:
   ```env
   GOOGLE_API_KEY=your_google_gemini_api_key
   ```

## 🚦 Usage

1. **Start the Application**
   ```bash
   python app.py
   ```
   The backend server will launch at `http://localhost:5000`.

2. **API Endpoints**

   - **Start Interview**
     - `POST /start_interview`
     - Body: `{ "name": "Name", "role": "Job Role" }`
   
   - **Submit Answer**
     - `POST /submit_response`
     - Form Data: `video` (file), `session_id`, `question_index`, `question_text`
   
   - **Get Report**
     - `GET /generate_report?session_id=<id>`

## 📂 Project Structure

```
virtual-interviewer/
├── app.py                 # Main Flask application
├── database.py            # SQLite database interactions
├── services/              # Core Logic modules
│   ├── audio_service.py   # Audio transcription & analysis
│   ├── video_service.py   # Video processing (CV)
│   ├── llm_service.py     # Gemini AI integration
│   └── timeline_service.py# Data fusion
├── uploads/               # Temp storage for video files
├── pyproject.toml         # Project dependencies
└── README.md              # Project documentation
```
