import os
import time
import json
import subprocess
import numpy as np
import parselmouth
from parselmouth.praat import call
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class AudioService:
    def __init__(self):
        print("⏳ Initializing Audio Service (Groq + Parselmouth)...")
        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY"),
            timeout=360.0
        )

    def extract_audio_from_video(self, video_path):
        """
        Extracts audio from ANY video format (mp4, webm, mkv) using ffmpeg directly.
        Chrome records in WebM/VP9/Opus — moviepy can't handle it, but ffmpeg can.
        """
        print("Extracting audio from video file...")
        # Always output to .wav regardless of input extension
        base = os.path.splitext(video_path)[0]
        audio_path = base + "_audio.wav"

        cmd = [
            "ffmpeg",
            "-y",                   # Overwrite without asking
            "-i", video_path,       # Input file (any format)
            "-vn",                  # No video
            "-acodec", "pcm_s16le", # WAV PCM 16-bit
            "-ar", "16000",         # 16kHz sample rate (Whisper optimal)
            "-ac", "1",             # Mono
            audio_path
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace")
                print(f"❌ ffmpeg error (code {result.returncode}):\n{err}")
                return None

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                print("❌ ffmpeg produced empty or missing audio file.")
                return None

            print("✅ Audio extraction successful!")
            return audio_path

        except subprocess.TimeoutExpired:
            print("❌ ffmpeg timed out.")
            return None
        except FileNotFoundError:
            print("❌ ffmpeg not found. Please install ffmpeg and add it to PATH.")
            return None
        except Exception as e:
            print(f"❌ Audio Extraction Error: {e}")
            return None

    def analyze(self, video_path, language: str = 'en'):
        """
        Analyzes audio from the given video path.

        Args:
            video_path: Path to the video file.
            language:   ISO 639-1 language code (e.g. 'hi', 'ta', 'en').
                        Pass 'auto' to let Whisper detect automatically —
                        useful for code-switching (Hinglish, Tanglish, etc.).
        """
        print(f"🎙️ Analyzing Audio: {video_path} | Language: {language}")

        # 1. Extract .wav
        audio_path = self.extract_audio_from_video(video_path)
        if not audio_path:
            # Return a safe fallback so the rest of the pipeline doesn't crash
            return {
                "transcript": "",
                "groq_json": {},
                "global_metrics": {
                    "wpm": 0, "avg_pitch_hz": 0, "pitch_variance": 0,
                    "jitter_percent": 0, "duration_seconds": 0
                },
                "frame_log": [],
                "error": "Audio extraction failed"
            }

        print("Starting transcription...")

        # 2. Groq Transcription (Whisper Large v3)
        transcript_text = ""
        groq_json = {}
        try:
            with open(audio_path, "rb") as file:
                # Build kwargs — only pass language when it's not 'auto'
                # Whisper Large v3 auto-detects when language is omitted.
                # Passing a specific language improves accuracy and speed
                # for single-language speakers (e.g. pure Tamil or pure Hindi).
                transcription_kwargs = {
                    "file": (os.path.basename(audio_path), file.read()),
                    "model": "whisper-large-v3",
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["word"],
                }
                if language and language.lower() != 'auto':
                    transcription_kwargs["language"] = language

                transcription = self.client.audio.transcriptions.create(
                    **transcription_kwargs
                )
            transcript_text = transcription.text or ""
            groq_json = transcription.to_dict() if hasattr(transcription, 'to_dict') else {}
            print(f"✅ Groq transcription success: '{transcript_text[:60]}...'")
        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            # Don't crash — continue with empty transcript

        # 3. Acoustic Metrics
        global_metrics = self._get_acoustic_metrics(audio_path, transcript_text)

        # 4. Frame-Level Metrics
        frame_log = self._get_frame_metrics(audio_path)

        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)

        return {
            "transcript": transcript_text,
            "groq_json": groq_json,
            "global_metrics": global_metrics,
            "frame_log": frame_log
        }

    def _get_acoustic_metrics(self, audio_path, transcript):
        """Global Averages for Jitter, Pitch, WPM"""
        print("Getting acoustic metrics...")
        try:
            sound = parselmouth.Sound(audio_path)
            duration = sound.get_total_duration()

            word_count = len(transcript.split()) if transcript else 0
            wpm = (word_count / duration) * 60 if duration > 0 else 0

            pitch = sound.to_pitch()
            pitch_values = pitch.selected_array['frequency']
            pitch_values = pitch_values[pitch_values != 0]

            if len(pitch_values) == 0:
                return {
                    "wpm": int(wpm), "avg_pitch_hz": 0, "pitch_variance": 0,
                    "jitter_percent": 0, "duration_seconds": round(duration, 2)
                }

            avg_pitch = np.mean(pitch_values)
            pitch_std = np.std(pitch_values)

            point_process = call(sound, "To PointProcess (periodic, cc)", 75, 500)
            jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100

            print("✅ Acoustic metrics done.")
            return {
                "wpm": int(wpm),
                "avg_pitch_hz": round(float(avg_pitch), 2),
                "pitch_variance": round(float(pitch_std), 2),
                "jitter_percent": round(float(jitter), 2),
                "duration_seconds": round(duration, 2)
            }
        except Exception as e:
            print(f"❌ Acoustic metrics error: {e}")
            return {
                "wpm": 0, "avg_pitch_hz": 0, "pitch_variance": 0,
                "jitter_percent": 0, "duration_seconds": 0
            }

    def _get_frame_metrics(self, audio_path):
        """Slices audio into 100ms chunks to sync with video analysis."""
        print("Getting frame metrics...")
        try:
            sound = parselmouth.Sound(audio_path)
            pitch_obj = sound.to_pitch(time_step=0.1)
            intensity_obj = sound.to_intensity(time_step=0.1)

            frames = []
            duration = sound.get_total_duration()

            for t in np.arange(0, duration, 0.1):
                p = pitch_obj.get_value_at_time(t)
                p = float(p) if (p is not None and not np.isnan(p)) else 0.0

                v = intensity_obj.get_value(t)
                v = float(v) if (v is not None and not np.isnan(v)) else 0.0

                frames.append({
                    "timestamp": round(float(t), 2),
                    "pitch": round(p, 1),
                    "volume": round(v, 1)
                })

            return frames
        except Exception as e:
            print(f"❌ Frame metrics error: {e}")
            return []


if __name__ == '__main__':
    test_video = "uploads/sample.mp4"
    if not os.path.exists(test_video):
        print(f"❌ File '{test_video}' not found.")
    else:
        print(f"🚀 Testing AudioService on {test_video}...")
        start = time.time()
        service = AudioService()
        result = service.analyze(test_video, language='hi')   # test with Hindi
        print("\n" + "=" * 60)
        print(json.dumps({k: v for k, v in result.items() if k != 'frame_log'}, indent=2))
        print(f"⏱ Total: {time.time() - start:.1f}s")