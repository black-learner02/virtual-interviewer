import cv2
import mediapipe as mp
import numpy as np
import math
import os


# --- STABILIZER ---
class Stabilizer:
    def __init__(self, alpha=0.15):
        self.state = None
        self.alpha = alpha

    def update(self, measurement):
        if self.state is None:
            self.state = measurement
        else:
            self.state = (measurement * self.alpha) + (self.state * (1 - self.alpha))
        return self.state


class VideoService:
    def __init__(self):
        print("⏳ Loading Video Sensors...")

        # 1. Config & Thresholds (CALIBRATED FROM DEBUG VIDEO)
        self.BLINK_THRESH = 0.23
        self.SMOOTH_FACTOR = 0.1

        # GAZE CALIBRATION:
        # Your resting gaze is ~0.45.
        # Looking Left drops to ~0.39. Looking Right goes to ~0.58.
        # We set the safe zone slightly left-shifted.
        self.H_MIN = 0.37
        self.H_MAX = 0.49

        # 0.35 - 0.65 is usually standard for vertical
        self.V_MIN, self.V_MAX = 0.35, 0.65

        # 2. MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 3. 3D Reference Model
        self.face_3d = np.array([
            [0.0, 0.0, 0.0],  # Nose Tip
            [0.0, 330.0, 65.0],  # Chin
            [-225.0, -170.0, 135.0],  # Left Eye Left
            [225.0, -170.0, 135.0],  # Right Eye Right
            [-150.0, 150.0, 125.0],  # Left Mouth
            [150.0, 150.0, 125.0]  # Right Mouth
        ], dtype=np.float64)

        self.PnP_INDICES = [1, 199, 33, 263, 61, 291]

        # 4. Emotion Model (ONNX)
        model_path = os.path.join("services", "emotion-ferplus-8.onnx")
        self.has_emotion_net = False
        if os.path.exists(model_path):
            try:
                self.emotion_net = cv2.dnn.readNetFromONNX(model_path)
                self.has_emotion_net = True
                print("   ✅ Emotion Model Loaded")
            except:
                pass
        self.EMOTIONS = ['Neutral', 'Happy', 'Surprise', 'Sad', 'Anger', 'Disgust', 'Fear', 'Contempt']

    def analyze(self, video_path):
        print(f"🎥 Processing Video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30

        stats = {
            "frames_analyzed": 0,
            "blinks": 0,
            "gaze": {"Screen": 0, "Up": 0, "Down": 0, "Left": 0, "Right": 0},
            "emotions": {e: 0 for e in self.EMOTIONS},
            "head_pose": {"nod_frames": 0, "shake_frames": 0, "tilt_frames": 0},
            "eyebrow_variance": 0.0
        }

        frame_log = []

        stabs = {
            'pitch': Stabilizer(self.SMOOTH_FACTOR),
            'yaw': Stabilizer(self.SMOOTH_FACTOR),
            'roll': Stabilizer(self.SMOOTH_FACTOR),
            'g_h': Stabilizer(0.2),  # Slightly more smoothing for gaze
            'g_v': Stabilizer(0.2)
        }

        blink_active = False
        brow_raise_values = []
        current_emotion = "Neutral"

        while cap.isOpened():
            success, image = cap.read()
            if not success: break

            # Skip every 2nd frame
            current_frame_idx = stats["frames_analyzed"]
            stats["frames_analyzed"] += 1
            if current_frame_idx % 2 != 0: continue

            timestamp = round(current_frame_idx * (1 / fps), 2)

            h, w, c = image.shape
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_image)

            frame_data = {
                "timestamp": timestamp,
                "pitch": 0, "yaw": 0, "roll": 0,
                "gaze": "Screen", "blink": False, "emotion": current_emotion
            }

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                mesh_points = np.array([np.multiply([p.x, p.y], [w, h]).astype(int) for p in landmarks])

                # --- A. 3D HEAD POSE ---
                pitch, yaw, roll = self._get_head_pose(landmarks, w, h, stabs)
                frame_data.update({"pitch": int(pitch), "yaw": int(yaw), "roll": int(roll)})

                if abs(pitch) > 15: stats["head_pose"]["nod_frames"] += 1
                if abs(yaw) > 15: stats["head_pose"]["shake_frames"] += 1
                if abs(roll) > 10: stats["head_pose"]["tilt_frames"] += 1

                # --- B. GAZE (Fixed Logic) ---
                direction = self._get_gaze_direction(mesh_points, stabs)
                stats["gaze"][direction] += 1
                frame_data["gaze"] = direction

                # --- C. BLINKS ---
                ear = self._get_ear(landmarks)
                if ear < self.BLINK_THRESH:
                    frame_data["blink"] = True
                    if not blink_active:
                        stats["blinks"] += 1
                        blink_active = True
                else:
                    blink_active = False

                # --- D. BROWS ---
                brow_val = self._get_brow_raise(landmarks)
                brow_raise_values.append(brow_val)

                # --- E. EMOTION (Every 5th frame for better capture) ---
                if self.has_emotion_net and stats["frames_analyzed"] % 5 == 0:
                    current_emotion = self._detect_emotion_sensitive(image, landmarks)
                    stats["emotions"][current_emotion] += 1
                frame_data["emotion"] = current_emotion

            frame_log.append(frame_data)

        cap.release()

        # --- SUMMARY ---
        duration_min = max((stats["frames_analyzed"] * 2 / fps) / 60, 0.01)

        summary = {
            "blink_rate": round(stats["blinks"] / duration_min, 1),
            "gaze_screen_pct": int((stats["gaze"]["Screen"] / max(len(frame_log), 1)) * 100),
            "dominant_emotion": max(stats["emotions"], key=stats["emotions"].get),
            "head_posture": {
                "nodding_pct": int((stats["head_pose"]["nod_frames"] / max(len(frame_log), 1)) * 100),
                "shaking_pct": int((stats["head_pose"]["shake_frames"] / max(len(frame_log), 1)) * 100)
            },
            "expressiveness": round(np.std(brow_raise_values) * 1000, 2) if brow_raise_values else 0
        }

        return {
            "summary": summary,
            "frame_log": frame_log
        }

    # --- HELPERS ---
    def _get_head_pose(self, landmarks, w, h, stabs):
        face_2d = []
        for idx in self.PnP_INDICES:
            lm = landmarks[idx]
            face_2d.append([int(lm.x * w), int(lm.y * h)])
        face_2d = np.array(face_2d, dtype=np.float64)

        focal_length = 1 * w
        cam_matrix = np.array([[focal_length, 0, w / 2], [0, focal_length, h / 2], [0, 0, 1]])
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        success, rvec, tvec = cv2.solvePnP(self.face_3d, face_2d, cam_matrix, dist_matrix)
        rmat, _ = cv2.Rodrigues(rvec)
        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

        return (stabs['pitch'].update(angles[0]),
                stabs['yaw'].update(angles[1]),
                stabs['roll'].update(angles[2]))

    def _get_gaze_direction(self, points, stabs):
        eye_left, eye_right = points[33], points[133]
        eye_top, eye_bottom = points[159], points[145]
        iris = points[468]

        h_total = np.linalg.norm(eye_left - eye_right)
        v_total = np.linalg.norm(eye_top - eye_bottom)

        if h_total == 0 or v_total == 0: return "Screen"

        raw_h = np.linalg.norm(eye_left - iris) / h_total
        raw_v = np.linalg.norm(eye_top - iris) / v_total

        sh = stabs['g_h'].update(raw_h)
        sv = stabs['g_v'].update(raw_v)

        # GAZE DIRECTION LOGIC (Calibrated)
        if self.H_MIN < sh < self.H_MAX and self.V_MIN < sv < self.V_MAX: return "Screen"

        # INVERTED LABELS FIX:
        # Low Ratio (<0.40) = User looking Screen Left (Their Right)
        if sh < self.H_MIN: return "Left"  # Was Right
        if sh > self.H_MAX: return "Right"  # Was Left

        if sv < self.V_MIN: return "Up"
        return "Down"

    def _get_ear(self, landmarks):
        def dist(i1, i2):
            return math.sqrt((landmarks[i1].x - landmarks[i2].x) ** 2 + (landmarks[i1].y - landmarks[i2].y) ** 2)

        return (dist(160, 144) + dist(158, 153)) / (2 * dist(33, 133))

    def _get_brow_raise(self, landmarks):
        brow_h = math.sqrt((landmarks[66].x - landmarks[159].x) ** 2 + (landmarks[66].y - landmarks[159].y) ** 2)
        eye_w = math.sqrt((landmarks[33].x - landmarks[133].x) ** 2 + (landmarks[33].y - landmarks[133].y) ** 2)
        return brow_h / eye_w if eye_w > 0 else 0

    def _detect_emotion_sensitive(self, image, landmarks):
        try:
            h, w = image.shape[:2]
            x_min = int(min([l.x for l in landmarks]) * w)
            y_max = int(max([l.y for l in landmarks]) * h)
            face = image[max(0, int(min([l.y for l in landmarks]) * h) - 20):min(h, y_max + 20),
            max(0, x_min - 20):min(w, int(max([l.x for l in landmarks]) * w) + 20)]
            blob = cv2.dnn.blobFromImage(cv2.resize(cv2.cvtColor(face, cv2.COLOR_BGR2GRAY), (64, 64)), 1.0, (64, 64))
            self.emotion_net.setInput(blob)
            scores = self.emotion_net.forward()[0]
            softmax = np.exp(scores) / np.sum(np.exp(scores))

            # SENSITIVE THRESHOLDING
            # Indices: 0=Neutral, 1=Happy, 2=Surprise, 3=Sad, 4=Anger...

            if softmax[1] > 0.25: return "Happy"  # If 25% happy, say Happy
            if softmax[2] > 0.30: return "Surprise"
            if softmax[4] > 0.30: return "Anger"
            if softmax[3] > 0.35: return "Sad"

            return "Neutral"
        except:
            return "Neutral"


# --- TEST BLOCK ---
if __name__ == '__main__':
    import json

    # Use the sample video to verify gaze changes
    test_video = "D:/PANIMALAR/FINAL YEAR PROJECT DOCS/virtual_interviewer_git_recovered/uploads/sample_compressed.mp4"
    if os.path.exists(test_video):
        print(f"🚀 Running Calibrated Analysis on {test_video}...")
        svc = VideoService()
        res = svc.analyze(test_video)

        print("\n📊 NEW SUMMARY:")
        print(json.dumps(res['summary'], indent=2))

        # Print frames where Gaze is NOT Screen
        print("\n👀 NON-SCREEN GAZE EVENTS:")
        non_screen = [f for f in res['frame_log'] if f['gaze'] != "Screen"]
        if non_screen:
            print(json.dumps(non_screen[:5], indent=2))
        else:
            print("No gaze aversion detected (Check H_MIN/H_MAX again if this is wrong).")

        for _ in res['frame_log']:
            print(_)