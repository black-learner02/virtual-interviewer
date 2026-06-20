import numpy as np

class TimelineService:
    def __init__(self):
        print("⏳ Initializing Timeline Fusion Engine...")

    def fuse(self, audio_result, video_result):
        """
        Merges Text (Groq) + Vision (OpenCV) + Voice (Parselmouth)
        into a single Event Timeline.
        """
        print("🔗 Fusing Data Streams...")

        timeline_events = []

        # 1. Get the Time Anchors (Words or Segments)
        groq = audio_result.get('groq_json', {})

        # Prefer "words" (High Precision), fall back to "segments" (Low Precision)
        if 'words' in groq:
            anchors = groq['words']
            mode = "word"
        elif 'segments' in groq:
            anchors = groq['segments']
            mode = "segment"
        else:
            print("⚠️ No timestamps found in transcription.")
            return []

        video_log = video_result.get('frame_log', [])
        audio_log = audio_result.get('frame_log', [])

        # 2. Iterate through every spoken moment
        for item in anchors:
            text = item['word'] if mode == "word" else item['text']
            start_t = item['start']
            end_t = item['end']

            # A. SLICE: Get sensors during this specific word/sentence
            v_frames = [f for f in video_log if start_t <= f['timestamp'] <= end_t]
            a_frames = [f for f in audio_log if start_t <= f['timestamp'] <= end_t]

            if not v_frames: continue

            # B. ANALYZE: Calculate the "Micro-Vibe"

            # --- Vision Metrics ---
            # 1. Head Movement
            # Safety check for empty lists to prevent NaN
            avg_pitch = np.mean([f['pitch'] for f in v_frames]) if v_frames else 0
            avg_yaw = np.mean([f['yaw'] for f in v_frames]) if v_frames else 0

            head_action = "Static"
            if avg_pitch > 10:
                head_action = "Nodding (Agreeing)"
            elif avg_pitch < -10:
                head_action = "Chin Up (Confidence/Arrogance)"
            elif abs(avg_yaw) > 10:
                head_action = "Shaking Head (Negation)"

            # 2. Gaze
            gaze_counts = {}
            for f in v_frames:
                gaze_counts[f['gaze']] = gaze_counts.get(f['gaze'], 0) + 1
            dominant_gaze = max(gaze_counts, key=gaze_counts.get) if gaze_counts else "Screen"

            # 3. Emotion
            emotions = [f['emotion'] for f in v_frames if f['emotion'] != "Neutral"]
            micro_expression = max(set(emotions), key=emotions.count) if emotions else "Neutral"

            # --- Audio Metrics ---
            # 4. Tone (CRASH FIX HERE 🛠️)
            # Filter for voiced frames only (pitch > 0)
            valid_pitches = [f['pitch'] for f in a_frames if f['pitch'] > 0]

            if valid_pitches:
                avg_audio_pitch = np.mean(valid_pitches)
            else:
                avg_audio_pitch = 0  # Default to 0 if silence

            # C. CONSTRUCT EVENT (The "Insight")
            is_significant = (
                    head_action != "Static" or
                    dominant_gaze != "Screen" or
                    micro_expression in ["Happy", "Surprise", "Fear", "Disgust"]
            )

            # If we are in "segment" mode (sentences), we always log it because it's content
            if mode == "segment" or is_significant:
                event = {
                    "timestamp": f"{start_t:.1f}s - {end_t:.1f}s",
                    "spoken": text.strip(),
                    "behavior": {
                        "posture": head_action,
                        "eye_contact": dominant_gaze,
                        "expression": micro_expression,
                        "voice_pitch": f"{int(avg_audio_pitch)}Hz"  # Safe now!
                    }
                }
                timeline_events.append(event)

        # 3. PAUSE ANALYSIS
        for i in range(len(anchors) - 1):
            curr_end = anchors[i]['end']
            next_start = anchors[i + 1]['start']
            gap = next_start - curr_end

            if gap > 1.5:
                silent_v_frames = [f for f in video_log if curr_end <= f['timestamp'] <= next_start]
                if not silent_v_frames: continue

                gaze_away = sum(1 for f in silent_v_frames if f['gaze'] != "Screen")
                gaze_state = "Staring Blankly" if gaze_away < len(silent_v_frames) / 2 else "Looking Away (Thinking)"

                timeline_events.append({
                    "timestamp": f"{curr_end:.1f}s - {next_start:.1f}s",
                    "event": "LONG_PAUSE",
                    "duration": f"{gap:.1f}s",
                    "behavior": gaze_state
                })

        timeline_events.sort(key=lambda x: float(x['timestamp'].split('s')[0]))

        return timeline_events

# --- TEST BLOCK ---
if __name__ == "__main__":
    import json

    # Mock Data to test the logic without running full video processing
    print("🚀 Testing Timeline Logic...")

    mock_audio = {
        "groq_json": {
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "world", "start": 0.6, "end": 1.0}
            ]
        },
        "frame_log": [{"timestamp": 0.2, "pitch": 120, "volume": 50}]
    }

    mock_video = {
        "frame_log": [
            {"timestamp": 0.2, "pitch": 15, "yaw": 0, "roll": 0, "gaze": "Screen", "emotion": "Happy"},
            {"timestamp": 0.8, "pitch": 0, "yaw": 20, "roll": 0, "gaze": "Up", "emotion": "Neutral"}
        ]
    }

    svc = TimelineService()
    result = svc.fuse(mock_audio, mock_video)
    print(json.dumps(result, indent=2))