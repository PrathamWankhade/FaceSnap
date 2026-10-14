import numpy as np
import cv2
from scipy import signal
from scipy.fft import fft, fftfreq
from app.config import LIVENESS_FRAME_COUNT, LIVENESS_HEARTBEAT_MIN, LIVENESS_HEARTBEAT_MAX, LIVENESS_SCORE_THRESHOLD


class LivenessService:
    def __init__(self):
        self.frame_count = LIVENESS_FRAME_COUNT
        self.fps_target = 30

    def detect_liveness(self, frames_bytes):
        if len(frames_bytes) < 10:
            return {"live": False, "score": 0.0, "reason": "Not enough frames"}

        frames = self._decode_frames(frames_bytes)
        if len(frames) < 10:
            return {"live": False, "score": 0.0, "reason": "Could not decode enough frames"}

        rppg_score = self._compute_rppg(frames)
        blink_score = self._detect_blinks(frames)
        motion_score = self._detect_motion(frames)

        combined = 0.5 * rppg_score + 0.3 * blink_score + 0.2 * motion_score
        live = combined >= LIVENESS_SCORE_THRESHOLD

        return {
            "live": bool(live),
            "score": float(round(combined, 3)),
            "rppg_score": float(round(rppg_score, 3)),
            "blink_score": float(round(blink_score, 3)),
            "motion_score": float(round(motion_score, 3)),
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

    def _compute_rppg(self, frames):
        try:
            skin_signals = []
            for frame in frames:
                h, w = frame.shape[:2]
                center_crop = frame[h//4:3*h//4, w//4:3*w//4]
                skin_signal = self._extract_skin_signal(center_crop)
                skin_signals.append(skin_signal)
            skin_signals = np.array(skin_signals)
            skin_signals = self._detrend(skin_signals)
            if skin_signals.size < 10:
                return 0.0
            bvp = self._pos_algorithm(skin_signals)
            if bvp is None or len(bvp) < 4:
                return 0.0
            peak_power = self._compute_peak_power(bvp)
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

    def _pos_algorithm(self, skin_signals):
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
        sos = signal.butter(4, [0.8, 3.0], btype='band', fs=self.fps_target, output='sos')
        filtered = signal.sosfilt(sos, projection)
        return filtered

    def _compute_peak_power(self, bvp):
        n = len(bvp)
        if n < 10:
            return 0.0
        yf = fft(bvp)
        xf = fftfreq(n, 1.0 / self.fps_target)
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
