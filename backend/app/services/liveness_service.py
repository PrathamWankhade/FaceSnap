import numpy as np
import cv2
from scipy import signal
from scipy.fft import fft, fftfreq
from app.config import (
    LIVENESS_FPS_TARGET,
    LIVENESS_FRAME_COUNT,
    LIVENESS_HEARTBEAT_MIN,
    LIVENESS_HEARTBEAT_MAX,
    LIVENESS_RPPG_PASS,
    LIVENESS_SCORE_THRESHOLD,
)

# The pulse band ends at 3 Hz, so sampling below 8 FPS cannot represent it.
MIN_FPS = 8.0
MAX_FPS = 60.0


class LivenessService:
    def __init__(self):
        self.frame_count = LIVENESS_FRAME_COUNT
        self.fps_target = LIVENESS_FPS_TARGET
        self._face_cascade = None

    def detect_liveness(self, frames_bytes, fps=None):
        """Score a short frame burst for signs of a live face.

        ``fps`` should be the *measured* capture rate. Mobile/webcam captures
        rarely hit a nominal interval exactly, and rPPG is sensitive to the
        sample rate, so the caller passes the observed interval.
        """
        if len(frames_bytes) < 10:
            return {"live": False, "score": 0.0, "reason": "Not enough frames"}

        frames = self._decode_frames(frames_bytes)
        if len(frames) < 10:
            return {"live": False, "score": 0.0, "reason": "Could not decode enough frames"}

        try:
            effective_fps = float(fps) if fps else float(self.fps_target)
        except (TypeError, ValueError):
            effective_fps = float(self.fps_target)
        effective_fps = max(MIN_FPS, min(MAX_FPS, effective_fps))

        rppg_score = self._compute_rppg(frames, effective_fps)
        blink_score = self._detect_blinks(frames)
        motion_score = self._detect_motion(frames)

        combined = 0.5 * rppg_score + 0.3 * blink_score + 0.2 * motion_score
        # Either a strong pulse alone, or a decent combined score across
        # independent signals, marks the capture as live.
        live = combined >= LIVENESS_SCORE_THRESHOLD or rppg_score >= LIVENESS_RPPG_PASS

        return {
            "live": bool(live),
            "score": float(round(combined, 3)),
            "rppg_score": float(round(rppg_score, 3)),
            "blink_score": float(round(blink_score, 3)),
            "motion_score": float(round(motion_score, 3)),
            "fps": float(round(effective_fps, 1)),
        }

    def _decode_frames(self, frames_bytes):
        frames = []
        for fb in frames_bytes:
            try:
                nparr = np.frombuffer(fb, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    frames.append(img)
            except Exception:
                continue
        return frames

    def _get_face_cascade(self):
        if self._face_cascade is None:
            self._face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        return self._face_cascade

    def _face_roi(self, frames):
        """Locate a stable skin region from the middle frame.

        Sampling a face-sized region rather than the whole centre crop keeps
        background motion and lighting changes out of the colour signal.
        """
        try:
            frame = frames[len(frames) // 2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._get_face_cascade().detectMultiScale(gray, 1.1, 4)
            if len(faces) == 0:
                return None
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            # Cheeks/forehead band, inset from the detected box.
            x1 = max(0, int(x + 0.15 * w))
            x2 = int(x + 0.85 * w)
            y1 = max(0, int(y + 0.30 * h))
            y2 = int(y + 0.85 * h)
            if x2 - x1 < 16 or y2 - y1 < 16:
                return None
            return x1, y1, x2, y2
        except Exception:
            return None

    def _compute_rppg(self, frames, fps):
        try:
            roi = self._face_roi(frames)
            skin_signals = []
            for frame in frames:
                h, w = frame.shape[:2]
                if roi is not None:
                    x1, y1, x2, y2 = roi
                    crop = frame[y1:min(y2, h), x1:min(x2, w)]
                else:
                    crop = frame[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
                if crop.size == 0:
                    continue
                skin_signals.append(self._extract_skin_signal(crop))
            skin_signals = np.array(skin_signals)
            if skin_signals.size == 0:
                return 0.0
            # A static image (printed photo, paused/looped video) has no
            # temporal colour variation. Without this guard, floating-point
            # noise gets normalised and the FFT falsely reports a pulse.
            # Measure variation over time *per channel* (channel means differ
            # from each other, so a global std would be misleading).
            if float(np.std(skin_signals, axis=0).max()) < 0.05:
                return 0.0
            skin_signals = self._detrend(skin_signals)
            if skin_signals.size < 10:
                return 0.0
            bvp = self._pos_algorithm(skin_signals, fps)
            if bvp is None or len(bvp) < 4:
                return 0.0
            peak_power = self._compute_peak_power(bvp, fps)
            return min(1.0, peak_power * 2.0)
        except Exception as e:
            print(f"rPPG error: {e}")
            return 0.0

    @staticmethod
    def _extract_skin_signal(roi):
        r_channel = roi[:, :, 2].astype(np.float32).mean()
        g_channel = roi[:, :, 1].astype(np.float32).mean()
        b_channel = roi[:, :, 0].astype(np.float32).mean()
        return np.array([r_channel, g_channel, b_channel])

    @staticmethod
    def _detrend(signals, lamb=100):
        if signals.ndim == 1:
            signals = signals.reshape(-1, 1)
        n = signals.shape[0]
        I = np.eye(n)
        D2 = np.diff(I, 2, axis=0)
        trend = np.linalg.inv(I + lamb * D2.T @ D2) @ signals
        return signals - trend

    def _pos_algorithm(self, skin_signals, fps):
        T = skin_signals.shape[0]
        if T < 10:
            return None
        temporal_mean = np.mean(skin_signals, axis=1)
        temporal_mean[temporal_mean == 0] = 1e-10
        normalized = skin_signals / temporal_mean[:, np.newaxis]
        projection = normalized @ np.array([-1, 2, -1])
        projection = projection - np.mean(projection)
        if np.std(projection) > 0:
            projection = projection / np.std(projection)
        sos = signal.butter(
            4,
            [LIVENESS_HEARTBEAT_MIN, LIVENESS_HEARTBEAT_MAX],
            btype="band",
            fs=fps,
            output="sos",
        )
        filtered = signal.sosfilt(sos, projection)
        return filtered

    def _compute_peak_power(self, bvp, fps):
        n = len(bvp)
        if n < 10:
            return 0.0
        if float(np.std(bvp)) < 1e-9:
            return 0.0
        yf = fft(bvp)
        xf = fftfreq(n, 1.0 / fps)
        pos_mask = xf > 0
        xf = xf[pos_mask]
        yf = np.abs(yf[pos_mask])
        heart_mask = (xf >= LIVENESS_HEARTBEAT_MIN) & (xf <= LIVENESS_HEARTBEAT_MAX)
        if not np.any(heart_mask):
            return 0.0
        heart_power = np.sum(yf[heart_mask])
        total_power = np.sum(yf)
        ratio = heart_power / total_power if total_power > 0 else 0.0
        return ratio

    def _detect_blinks(self, frames):
        if len(frames) < 5:
            return 0.0
        try:
            cascade = getattr(cv2, 'CascadeClassifier', None)
            if cascade is None:
                return 0.0
            face_cascade = cascade(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            eyes_cascade = cascade(cv2.data.haarcascades + "haarcascade_eye.xml")
            ear_values = []
            for frame in frames[::2]:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                if len(faces) == 0:
                    ear_values.append(0.0)
                    continue
                (fx, fy, fw, fh) = faces[0]
                face_roi = gray[fy:fy+fh, fx:fx+fw]
                eyes = eyes_cascade.detectMultiScale(face_roi, 1.1, 4)
                ear = len(eyes) / 2.0
                ear_values.append(min(1.0, ear))
            if len(ear_values) < 3:
                return 0.0
            ear_std = np.std(ear_values)
            score = min(1.0, ear_std * 3.0)
            return score
        except Exception:
            return 0.0

    def _detect_motion(self, frames):
        if len(frames) < 5:
            return 0.0
        try:
            grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
            diffs = []
            for i in range(1, len(grays), 2):
                diff = cv2.absdiff(grays[i], grays[i-1])
                diffs.append(np.mean(diff))
            if not diffs:
                return 0.0
            avg_motion = np.mean(diffs)
            score = min(1.0, avg_motion / 10.0)
            return score
        except Exception as e:
            print(f"Motion detection error: {e}")
            return 0.0


liveness_service = LivenessService()
