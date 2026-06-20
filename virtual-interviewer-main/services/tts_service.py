import os
import io
from dotenv import load_dotenv

load_dotenv()


class TTSService:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mode = "openai" if self.openai_key else "gtts"
        print(f"🔊 TTS Service initialized — using {'OpenAI TTS' if self.mode == 'openai' else 'gTTS (free fallback)'}.")

    def synthesize(self, text: str, voice: str = "onyx",
                   language: str = "en") -> bytes | None:
        """
        Converts text to MP3 audio bytes.

        Args:
            text:     The question/sentence to speak.
            voice:    OpenAI voice name (onyx sounds professional/authoritative).
                      Options: alloy, echo, fable, onyx, nova, shimmer
            language: ISO 639-1 language code (e.g. 'hi', 'ta', 'en').
                      Used by gTTS. OpenAI TTS auto-detects from the text
                      so this has no effect when OpenAI TTS is active.

        Returns:
            MP3 bytes on success, None on failure.
        """
        if self.mode == "openai":
            # OpenAI TTS auto-detects the language from the Unicode text content.
            # No language param is needed — Hindi/Tamil text will be spoken correctly.
            return self._synthesize_openai(text, voice, language)
        else:
            return self._synthesize_gtts(text, language)

    def _synthesize_openai(self, text: str, voice: str,
                            language: str = "en") -> bytes | None:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            response = client.audio.speech.create(
                model="tts-1",          # tts-1-hd for higher quality (slower)
                voice=voice,
                input=text,
                response_format="mp3"
            )
            return response.content
        except Exception as e:
            print(f"❌ OpenAI TTS Error: {e}. Falling back to gTTS.")
            return self._synthesize_gtts(text, language)

    def _synthesize_gtts(self, text: str, language: str = "en") -> bytes | None:
        try:
            from gtts import gTTS
            # gTTS uses the same 2-letter ISO 639-1 codes we store in the session.
            # If an unsupported code is passed, fall back to English silently.
            try:
                tts = gTTS(text=text, lang=language, slow=False)
            except ValueError:
                print(f"⚠️  gTTS: unsupported language '{language}', falling back to English.")
                tts = gTTS(text=text, lang='en', slow=False)

            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return buf.read()
        except Exception as e:
            print(f"❌ gTTS Error: {e}")
            return None


# --- TEST ---
if __name__ == "__main__":
    svc = TTSService()

    tests = [
        ("en", "Hello! Welcome to your technical interview. Please tell me about yourself."),
        ("hi", "नमस्ते! अपने बारे में बताइए और आपकी पृष्ठभूमि क्या है?"),
        ("ta", "வணக்கம்! உங்களைப் பற்றி சொல்லுங்கள், உங்கள் பின்னணி என்ன?"),
    ]

    for lang, text in tests:
        print(f"\n🧪 Testing language: {lang}")
        audio = svc.synthesize(text, language=lang)
        if audio:
            path = f"test_tts_{lang}.mp3"
            with open(path, "wb") as f:
                f.write(audio)
            print(f"✅ Saved: {path} ({len(audio)} bytes)")
        else:
            print(f"❌ TTS failed for language: {lang}")